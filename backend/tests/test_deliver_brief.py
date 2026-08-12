"""sweeps/deliver_brief.py — the brief-delivery script and its degrade contract.

Like test_audio_brief_script.py, this is a repo-root pipeline tool (stdlib, system
python3) exercised as a subprocess the way sweep.sh runs it — always synthetic day dirs
under tmp_path, never the real data/sweeps. No test ever sends anything real: SMTP points
at an unroutable address (with DELIVERY_SMTP_PASSWORD set so the Keychain is never
consulted), and osascript is replaced via DELIVERY_OSASCRIPT with a recording stub — the
HEARTBEAT_NOTIFIER pattern. House rules under test: delivery is a bonus (missing config,
disabled channels, and missing mp3 are clean exit 0), channels are independent, and the
per-day/per-channel ledger makes launchd's on-wake re-fire a no-op.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "sweeps" / "deliver_brief.py"
DATE = "2026-07-15"

OSA_STUB = """#!/bin/sh
printf '%s\\n' "$@" >> "$OSA_LOG"
cat > /dev/null
exit 0
"""

OSA_FAILING = """#!/bin/sh
cat > /dev/null
echo "execution error: Messages got an error" >&2
exit 1
"""


def _brief(top_line: str, headline: str = "") -> str:
    items = []
    if headline:
        items.append(
            {
                "headline": headline,
                "attribution": "Somewhere, July 14, 2026",
                "digest": "First sentence. Second sentence.",
                "why_it_matters": "It matters.",
                "sources": [{"title": "Src", "url": "https://example.com/s"}],
            }
        )
    return json.dumps({"top_line": top_line, "items": items})


def _setup(tmp_path, config: dict | str | None, with_mp3: bool = True, files: dict | None = None):
    """A synthetic sweeps tree + config + roster; returns the paths _run needs."""
    sweeps = tmp_path / "sweeps"
    day = sweeps / DATE
    day.mkdir(parents=True)
    default_files = {"ai-llms.json": _brief("AI line.", "AI headline")}
    for fname, text in (files if files is not None else default_files).items():
        (day / fname).write_text(text, encoding="utf-8")
    if with_mp3:
        (day / "brief.mp3").write_bytes(b"\xff\xfbfake-mp3-bytes")
    roster = tmp_path / "topics.json"
    roster.write_text(
        json.dumps([{"slug": "ai-llms", "title": "AI / LLMs", "paused": False}]), encoding="utf-8"
    )
    cfg = tmp_path / "delivery.json"
    if isinstance(config, str):
        cfg.write_text(config, encoding="utf-8")
    elif config is not None:
        cfg.write_text(json.dumps(config), encoding="utf-8")
    return sweeps, roster, cfg, tmp_path / "ledger.jsonl"


def _run(sweeps, roster, cfg, ledger, *extra, env=None):
    full_env = {
        "PATH": "/usr/bin:/bin",
        # Unroutable: connection refused immediately — a test that reaches SMTP fails loudly.
        "DELIVERY_SMTP_HOST": "127.0.0.1",
        "DELIVERY_SMTP_PORT": "1",
        "DELIVERY_SMTP_PASSWORD": "test-app-password",
        **(env or {}),
    }
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--date",
            DATE,
            "--sweeps-dir",
            str(sweeps),
            "--roster",
            str(roster),
            "--config",
            str(cfg),
            "--ledger",
            str(ledger),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=full_env,
        timeout=60,
    )


def _osa_stub(tmp_path, body: str = OSA_STUB) -> tuple[str, Path]:
    stub = tmp_path / "osascript-stub"
    stub.write_text(body, encoding="utf-8")
    stub.chmod(0o755)
    return str(stub), tmp_path / "osa.log"


def _ledger_rows(ledger: Path) -> list[dict]:
    if not ledger.is_file():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


EMAIL_ONLY = {"email": {"enabled": True, "to": "kyle@example.com", "from": "kyle@example.com"}}
IMESSAGE_ONLY = {"imessage": {"enabled": True, "to": "+13125550100"}}
BOTH = {**EMAIL_ONLY, **IMESSAGE_ONLY}


# -- clean no-op exits -------------------------------------------------------------


def test_missing_config_is_a_clean_noop(tmp_path):
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=None)
    r = _run(sweeps, roster, cfg, ledger)
    assert r.returncode == 0, r.stderr
    assert "nothing to send" in r.stdout
    assert _ledger_rows(ledger) == []


def test_unparseable_config_is_a_clean_noop(tmp_path):
    sweeps, roster, cfg, ledger = _setup(tmp_path, config="{not json")
    r = _run(sweeps, roster, cfg, ledger)
    assert r.returncode == 0, r.stderr
    assert "nothing to send" in r.stdout


def test_disabled_and_recipientless_channels_are_a_clean_noop(tmp_path):
    """The shipped default: imessage enabled but 'to' empty must self-disable."""
    config = {
        "email": {"enabled": False, "to": "kyle@example.com"},
        "imessage": {"enabled": True, "to": ""},
    }
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=config)
    r = _run(sweeps, roster, cfg, ledger)
    assert r.returncode == 0, r.stderr
    assert "nothing to send" in r.stdout
    assert _ledger_rows(ledger) == []


def test_missing_mp3_is_a_clean_noop(tmp_path):
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=BOTH, with_mp3=False)
    r = _run(sweeps, roster, cfg, ledger)
    assert r.returncode == 0, r.stderr
    assert "no brief.mp3" in r.stdout
    assert _ledger_rows(ledger) == []


# -- iMessage channel (osascript stub) ---------------------------------------------


def test_imessage_sends_handle_and_caption_text_only(tmp_path):
    """Text only, no file argv — macOS silently drops AppleScript file sends, so the
    script must never pretend to attach the mp3."""
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=IMESSAGE_ONLY)
    stub, osa_log = _osa_stub(tmp_path)
    r = _run(sweeps, roster, cfg, ledger, env={"DELIVERY_OSASCRIPT": stub, "OSA_LOG": str(osa_log)})
    assert r.returncode == 0, r.stderr
    argv = osa_log.read_text(encoding="utf-8").splitlines()
    assert argv[0] == "-"  # script arrives on stdin, never interpolated
    assert argv[1] == "+13125550100"
    assert "Home Base brief" in argv[2] and "AI / LLMs" in argv[2]
    assert len(argv) == 3  # handle + caption only — no mp3 path
    assert "Listen:" not in argv[2]  # no base_url configured → no link line
    rows = _ledger_rows(ledger)
    assert [(row["channel"], row["ok"], row["date"]) for row in rows] == [("imessage", True, DATE)]


def test_imessage_caption_carries_audio_link_when_base_url_set(tmp_path):
    config = {**IMESSAGE_ONLY, "base_url": "https://mac.tail.ts.net/"}
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=config)
    stub, osa_log = _osa_stub(tmp_path)
    r = _run(sweeps, roster, cfg, ledger, env={"DELIVERY_OSASCRIPT": stub, "OSA_LOG": str(osa_log)})
    assert r.returncode == 0, r.stderr
    argv = osa_log.read_text(encoding="utf-8").splitlines()
    # trailing slash normalized, date pinned, on its own line
    assert argv[3] == f"Listen: https://mac.tail.ts.net/api/brief/audio?date={DATE}"


def test_build_html_today_link_honest_about_base_url():
    """Direct unit check: base_url present → tailnet href; absent → no localhost lie."""
    import sys as _sys

    _sys.path.insert(0, str(SCRIPT.parent))
    import deliver_brief

    topics = [{"slug": "a", "title": "A", "top_line": "Line.", "items": []}]
    with_url = deliver_brief.build_html(topics, DATE, "https://mac.tail.ts.net")
    assert 'href="https://mac.tail.ts.net"' in with_url
    without = deliver_brief.build_html(topics, DATE)
    assert "localhost" not in without and "href" not in without.split("</ul>")[-1]


def test_imessage_failure_exits_nonzero_with_error_row(tmp_path):
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=IMESSAGE_ONLY)
    stub, _ = _osa_stub(tmp_path, OSA_FAILING)
    r = _run(sweeps, roster, cfg, ledger, env={"DELIVERY_OSASCRIPT": stub})
    assert r.returncode == 1
    assert "imessage failed" in r.stderr
    rows = _ledger_rows(ledger)
    assert len(rows) == 1 and rows[0]["ok"] is False and "Messages" in rows[0]["detail"]


# -- email channel (unroutable SMTP, no real send ever) ----------------------------


def test_email_smtp_down_exits_nonzero_and_other_channel_still_sends(tmp_path):
    """Channel independence: a dead SMTP must not block the iMessage send."""
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=BOTH)
    stub, osa_log = _osa_stub(tmp_path)
    r = _run(sweeps, roster, cfg, ledger, env={"DELIVERY_OSASCRIPT": stub, "OSA_LOG": str(osa_log)})
    assert r.returncode == 1
    assert "email failed" in r.stderr
    assert osa_log.is_file()  # the iMessage channel was still attempted and succeeded
    by_channel = {row["channel"]: row["ok"] for row in _ledger_rows(ledger)}
    assert by_channel == {"email": False, "imessage": True}


def test_email_without_password_names_the_keychain_fix(tmp_path):
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=EMAIL_ONLY)
    # No DELIVERY_SMTP_PASSWORD and a stubbed `security` lookup that finds nothing.
    fake_security = tmp_path / "bin"
    fake_security.mkdir()
    (fake_security / "security").write_text("#!/bin/sh\nexit 44\n", encoding="utf-8")
    (fake_security / "security").chmod(0o755)
    r = _run(
        sweeps,
        roster,
        cfg,
        ledger,
        env={"PATH": f"{fake_security}:/usr/bin:/bin", "DELIVERY_SMTP_PASSWORD": ""},
    )
    assert r.returncode == 1
    assert "add-generic-password" in r.stderr  # the error message teaches the setup step


# -- idempotency -------------------------------------------------------------------


def test_second_run_skips_and_force_resends(tmp_path):
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=IMESSAGE_ONLY)
    stub, osa_log = _osa_stub(tmp_path)
    env = {"DELIVERY_OSASCRIPT": stub, "OSA_LOG": str(osa_log)}
    first = _run(sweeps, roster, cfg, ledger, env=env)
    assert first.returncode == 0, first.stderr
    second = _run(sweeps, roster, cfg, ledger, env=env)
    assert second.returncode == 0, second.stderr
    assert "already delivered" in second.stdout
    assert len(_ledger_rows(ledger)) == 1  # the re-fire wrote nothing
    forced = _run(sweeps, roster, cfg, ledger, "--force", env=env)
    assert forced.returncode == 0, forced.stderr
    assert len(_ledger_rows(ledger)) == 2


def test_regenerated_mp3_resends_without_force(tmp_path):
    """F1: a late-finishing topic regenerates brief.mp3 on the on-wake re-fire — the
    completed brief must re-send once; the bare (date, channel) key would skip it forever."""
    import os
    import time

    sweeps, roster, cfg, ledger = _setup(tmp_path, config=IMESSAGE_ONLY)
    stub, osa_log = _osa_stub(tmp_path)
    env = {"DELIVERY_OSASCRIPT": stub, "OSA_LOG": str(osa_log)}
    assert _run(sweeps, roster, cfg, ledger, env=env).returncode == 0
    assert len(_ledger_rows(ledger)) == 1
    # Regenerate the mp3 well after the delivery row's second-resolution ts.
    mp3 = sweeps / DATE / "brief.mp3"
    newer = time.time() + 120
    os.utime(mp3, (newer, newer))
    again = _run(sweeps, roster, cfg, ledger, env=env)
    assert again.returncode == 0, again.stderr
    assert "already delivered" not in again.stdout
    assert len(_ledger_rows(ledger)) == 2


def test_failed_channel_retries_on_the_next_run(tmp_path):
    """An ok:false row must NOT count as delivered — the on-wake re-fire is the retry."""
    sweeps, roster, cfg, ledger = _setup(tmp_path, config=IMESSAGE_ONLY)
    failing, _ = _osa_stub(tmp_path, OSA_FAILING)
    assert _run(sweeps, roster, cfg, ledger, env={"DELIVERY_OSASCRIPT": failing}).returncode == 1
    stub, osa_log = _osa_stub(tmp_path)
    retry = _run(sweeps, roster, cfg, ledger, env={"DELIVERY_OSASCRIPT": stub, "OSA_LOG": str(osa_log)})
    assert retry.returncode == 0, retry.stderr
    oks = [row["ok"] for row in _ledger_rows(ledger)]
    assert oks == [False, True]
