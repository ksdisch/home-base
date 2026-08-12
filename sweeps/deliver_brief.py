#!/usr/bin/env python3
"""Deliver the day's rendered brief to Kyle — email (Gmail SMTP) + iMessage (Messages.app).

Runs after the sweep (sweep.sh chains it best-effort, like the audio brief): when
data/sweeps/<date>/brief.mp3 exists, sends it as an email attachment with an HTML
headline summary, and as an iMessage from this Mac's own Messages account (no Twilio,
no third party — both channels are self-addressed per sweeps/delivery.json). The
iMessage is TEXT ONLY — the caption plus a tap-to-play tailnet link to the audio
(config key ``base_url``): modern macOS silently drops file attachments sent through
Messages' AppleScript (the send succeeds, the file never appears), so the MP3 itself
travels by email and the text carries the link. Channels
are independent: one failing never blocks the other. Idempotent per day and channel:
a successful ledger row in backend/data/brief-delivery.jsonl at or after the mp3's
mtime makes launchd's on-wake re-fire a no-op — but a REGENERATED mp3 (a late-finishing
topic completing the brief) re-sends once; --force re-sends deliberately.

Design note: this is Home Base's first outbound send. It stays below the "Overnight
email-send bar" (docs/ideas/overnight-chief-of-staff.md) because nothing here can ever
reach a third party — recipients come from delivery.json, which holds Kyle's own
addresses, and there is no LLM anywhere in the path.

  python3 sweeps/deliver_brief.py                  # today, default paths
  python3 sweeps/deliver_brief.py --force          # re-send even if already delivered

The Gmail app password lives in the macOS Keychain (never in the repo):
  security add-generic-password -s homebase-brief-smtp -a <gmail-address> -w '<app-password>'

Env: DELIVERY_CONFIG_FILE (default sweeps/delivery.json) · DELIVERY_SMTP_HOST
(smtp.gmail.com) · DELIVERY_SMTP_PORT (465) · DELIVERY_SMTP_PASSWORD (when set it wins
over the Keychain, so tests never shell out to `security`) ·
DELIVERY_KEYCHAIN_SERVICE (homebase-brief-smtp) · DELIVERY_OSASCRIPT
(osascript — tests point it at a stub, the HEARTBEAT_NOTIFIER pattern).
Stdlib only; system python3, no venv.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
import subprocess
import sys
from datetime import date as date_cls
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import audio_brief  # sweeps/audio_brief.py — roster/topic loaders + the ear script

ROOT = Path(__file__).resolve().parent.parent

_SMTP_TIMEOUT = 60
_OSASCRIPT_TIMEOUT = 120

# osascript reads this from stdin ("-") with the handle/body as argv — no string
# interpolation into the script, so a weird headline can never break out of a quote.
# Text only, deliberately: `send <file>` silently no-ops on modern macOS (exit 0, no
# bubble), so an attachment here would just lie about having been delivered.
_IMESSAGE_APPLESCRIPT = """\
on run argv
    set theHandle to item 1 of argv
    set theBody to item 2 of argv
    tell application "Messages"
        set theService to 1st account whose service type = iMessage
        set theBuddy to participant theHandle of theService
        send theBody to theBuddy
    end tell
end run
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_config(config_file: Path) -> dict:
    """Tolerant like every sweeps/ loader: unreadable or mis-shaped → {} (all disabled)."""
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _channel(cfg: dict, name: str) -> dict | None:
    """The channel's config when it is enabled and has a non-empty recipient, else None."""
    entry = cfg.get(name)
    if not isinstance(entry, dict) or not entry.get("enabled"):
        return None
    to = entry.get("to")
    if not isinstance(to, str) or not to.strip():
        return None
    return {**entry, "to": to.strip()}


def _delivered_channels(ledger: Path, day: str, mp3_mtime: float) -> set[str]:
    """Channels whose newest successful row is no older than the mp3 itself.

    The bare (date, channel) key isn't enough: a half-finished 06:00 sweep delivers a
    partial brief, then the on-wake re-fire finishes the missing topics and audio_brief
    regenerates the mp3 — that completed brief must re-send once. So a channel only
    counts as delivered when an ok:true row's ts is at or after the mp3's mtime
    (ledger ts is second-resolution, hence the int() floor); same-mp3 re-fires stay
    no-ops. Rows with a missing/mangled ts count as not delivered — retry over skip.
    """
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return set()
    done = set()
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not (isinstance(row, dict) and row.get("date") == day and row.get("ok") is True):
            continue
        channel = row.get("channel")
        if not isinstance(channel, str):
            continue
        try:
            ts = (
                datetime.strptime(row["ts"], "%Y-%m-%dT%H:%M:%SZ")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except (KeyError, TypeError, ValueError):
            continue
        if ts >= int(mp3_mtime):
            done.add(channel)
    return done


def _append_row(ledger: Path, row: dict) -> None:
    """Best-effort ledger append — a full disk must not turn a sent brief into a failure."""
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError as e:
        print(f"!! deliver: couldn't append to {ledger} ({e}) — delivery itself succeeded", file=sys.stderr)


def audio_link(cfg: dict, day: str) -> str:
    """The tap-to-play tailnet URL for the day's audio, or "" when base_url is unset."""
    base = cfg.get("base_url")
    if not isinstance(base, str) or not base.strip():
        return ""
    return f"{base.strip().rstrip('/')}/api/brief/audio?date={day}"


def build_html(topics: list[dict], date_iso: str, base_url: str = "") -> str:
    """A minimal HTML digest: per topic, the top line plus source-linked headlines."""
    parts = [f"<p>Your Home Base brief for <strong>{html.escape(audio_brief.human_date(date_iso))}</strong>. The MP3 is attached.</p>"]
    for topic in topics:
        parts.append(f"<h3>{html.escape(topic['title'])}</h3>")
        parts.append(f"<p><em>{html.escape(audio_brief.strip_markup(topic['top_line']))}</em></p>")
        items = [i for i in topic["items"] if isinstance(i, dict)]
        if items:
            lis = []
            for item in items:
                head = html.escape(audio_brief.strip_markup(str(item.get("headline", ""))))
                if not head:
                    continue
                sources = item.get("sources") or []
                url = ""
                if sources and isinstance(sources[0], dict):
                    url = str(sources[0].get("url", ""))
                if url.startswith("http"):
                    lis.append(f'<li><a href="{html.escape(url, quote=True)}">{head}</a></li>')
                else:
                    lis.append(f"<li>{head}</li>")
            if lis:
                parts.append("<ul>" + "".join(lis) + "</ul>")
    if base_url:
        parts.append(
            f'<p>Full stories, sources, and notes are on the <a href="{html.escape(base_url, quote=True)}">Today page</a>.</p>'
        )
    else:
        parts.append("<p>Full stories, sources, and notes are on the Today page.</p>")
    return "<html><body>" + "".join(parts) + "</body></html>"


def _smtp_password(from_addr: str) -> str | None:
    """DELIVERY_SMTP_PASSWORD when set (tests), else the macOS Keychain item."""
    env_password = os.environ.get("DELIVERY_SMTP_PASSWORD")
    if env_password:
        return env_password
    service = os.environ.get("DELIVERY_KEYCHAIN_SERVICE", "homebase-brief-smtp")
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    password = proc.stdout.strip()
    return password or None


def send_email(channel: dict, mp3: Path, topics: list[dict], ear_script: str, day: str, base_url: str = "") -> None:
    """Build and send the brief email; raises RuntimeError/OSError on any failure."""
    from_addr = str(channel.get("from") or channel["to"])
    password = _smtp_password(from_addr)
    if not password:
        raise RuntimeError(
            "no SMTP app password — add one with: security add-generic-password "
            f"-s {os.environ.get('DELIVERY_KEYCHAIN_SERVICE', 'homebase-brief-smtp')} -a {from_addr} -w '<app-password>'"
        )

    msg = EmailMessage()
    msg["Subject"] = f"Home Base brief — {audio_brief.human_date(day)}"
    msg["From"] = from_addr
    msg["To"] = channel["to"]
    msg.set_content(ear_script or f"Your Home Base brief for {day} is attached.")
    msg.add_alternative(build_html(topics, day, base_url), subtype="html")
    msg.add_attachment(
        mp3.read_bytes(),
        maintype="audio",
        subtype="mpeg",
        filename=f"brief-{day}.mp3",
    )

    host = os.environ.get("DELIVERY_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("DELIVERY_SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=_SMTP_TIMEOUT) as smtp:
        smtp.login(from_addr, password)
        smtp.send_message(msg)


def send_imessage(channel: dict, caption: str) -> None:
    """Send the caption text via Messages.app; raises RuntimeError on any failure."""
    osascript = os.environ.get("DELIVERY_OSASCRIPT", "osascript")
    try:
        proc = subprocess.run(
            [osascript, "-", channel["to"], caption],
            input=_IMESSAGE_APPLESCRIPT,
            capture_output=True,
            text=True,
            timeout=_OSASCRIPT_TIMEOUT,
        )
    except FileNotFoundError:
        raise RuntimeError(f"{osascript} not found") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{osascript} timed out after {_OSASCRIPT_TIMEOUT}s") from None
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()[:300]
        raise RuntimeError(f"Messages send failed — {detail or 'no error output'}")


def build_caption(topics: list[dict], day: str, link: str = "") -> str:
    titles = " · ".join(t["title"] for t in topics)
    base = f"🎧 Home Base brief for {audio_brief.human_date(day)}"
    caption = f"{base} — {len(topics)} topics: {titles}" if titles else base
    return f"{caption}\nListen: {link}" if link else caption


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=date_cls.today().isoformat(), help="YYYY-MM-DD day to deliver")
    ap.add_argument("--sweeps-dir", default=str(ROOT / "data" / "sweeps"), dest="sweeps_dir")
    ap.add_argument("--roster", default=str(Path(__file__).resolve().parent / "topics.json"))
    ap.add_argument(
        "--config",
        default=os.environ.get(
            "DELIVERY_CONFIG_FILE", str(Path(__file__).resolve().parent / "delivery.json")
        ),
    )
    ap.add_argument(
        "--ledger",
        default=str(ROOT / "backend" / "data" / "brief-delivery.jsonl"),
        help="JSONL delivery ledger (backend data — data/sweeps stays backend-read-only)",
    )
    ap.add_argument("--force", action="store_true", help="re-send even if already delivered")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    channels = {name: _channel(cfg, name) for name in ("email", "imessage")}
    enabled = {name: ch for name, ch in channels.items() if ch}
    if not enabled:
        print("deliver: no delivery channels enabled — nothing to send")
        return 0

    day_dir = Path(args.sweeps_dir) / args.date
    mp3 = day_dir / "brief.mp3"
    if not mp3.is_file():
        print(f"deliver: no brief.mp3 for {args.date} — nothing to send")
        return 0

    ledger = Path(args.ledger)
    done = set() if args.force else _delivered_channels(ledger, args.date, mp3.stat().st_mtime)
    pending = {name: ch for name, ch in enabled.items() if name not in done}
    if not pending:
        print(f"deliver: brief already delivered for {args.date} — skipping (use --force to re-send)")
        return 0

    topics = audio_brief.load_topics(day_dir, audio_brief.load_roster(Path(args.roster)))
    ear_script, _ = audio_brief.build_script(topics, args.date) if topics else ("", [])
    base_url = cfg.get("base_url") if isinstance(cfg.get("base_url"), str) else ""
    link = audio_link(cfg, args.date)
    caption = build_caption(topics, args.date, link)
    if "imessage" in pending and not link:
        print(
            "!! deliver: imessage has no base_url configured — the text goes out with no "
            "way to reach the audio (set base_url in delivery.json)",
            file=sys.stderr,
        )

    failures = 0
    for name, channel in pending.items():
        try:
            if name == "email":
                send_email(channel, mp3, topics, ear_script, args.date, base_url.strip())
            else:
                send_imessage(channel, caption)
        except (OSError, RuntimeError, smtplib.SMTPException) as e:
            failures += 1
            print(f"!! deliver: {name} failed ({e})", file=sys.stderr)
            _append_row(
                ledger,
                {"ts": _utc_now(), "date": args.date, "channel": name, "ok": False, "detail": str(e)[:300]},
            )
            continue
        if name == "email":
            sent_what = f"{mp3.name}, {mp3.stat().st_size} bytes"
        else:
            sent_what = "text + audio link" if link else "text only (no base_url)"
        print(f"deliver: {name} sent to {channel['to']} ({sent_what})")
        _append_row(
            ledger,
            {"ts": _utc_now(), "date": args.date, "channel": name, "ok": True, "detail": sent_what},
        )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
