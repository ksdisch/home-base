#!/usr/bin/env python3
"""Render the day's brief as one condensed spoken MP3 via local Kokoro TTS (M4).

Reads the validated data/sweeps/<date>/<topic>.json files (roster order first, same as the
page) and builds a deterministic "morning drive" script — per topic: a speakable title, the
top line, and one top-story digest sentence the top line didn't already cover (the digest's
first sentence is the headline in fuller prose, so the headline itself is never read on top
of it; a fully covered story narrates nothing) — targeting ~600–700 words
(≈4–5 minutes, under Kokoro's single-request comfort zone). POSTs it to the OpenAI-compatible
/v1/audio/speech endpoint the com.voicemode.kokoro LaunchAgent keeps running locally and
writes data/sweeps/<date>/brief.mp3 atomically.

Best-effort by contract: sweep.sh calls this after the topic loop and tolerates a non-zero
exit — Kokoro being down must never fail a sweep (the text brief is the product, the MP3 is
a bonus). Idempotent: skips itself when brief.mp3 is already newer than every <topic>.json,
so launchd's on-wake re-fire is a no-op but a late-finishing topic triggers a regenerate.
Stdlib only; runs with the system python3, no venv.

  python3 sweeps/audio_brief.py                    # today, default paths
  python3 sweeps/audio_brief.py --print-script     # show the ear script, render nothing
  python3 sweeps/audio_brief.py --force            # re-render even if the mp3 is fresh

Env: KOKORO_URL (default http://127.0.0.1:8880/v1/audio/speech) · NARRATE_VOICE (am_adam) ·
NARRATE_SPEED (1.0).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Past ~750 words a single Kokoro request may strain; the trim ladder keeps us under this.
MAX_WORDS = 700
WORDS_PER_MINUTE = 155  # duration estimate only

_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL_IN_TEXT = re.compile(r"https?://\S+")
_PARENTHETICAL = re.compile(r"\([^)]*\)")
_WS = re.compile(r"\s+")


def load_roster(roster_file: Path) -> list[dict]:
    """Ordered [{slug, title}] from sweeps/topics.json — tolerant like the backend's loader.

    Paused topics stay in the order: the pause flag gates sweeping, never what's on disk.
    """
    try:
        data = json.loads(roster_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    roster = []
    for entry in data:
        if isinstance(entry, dict) and isinstance(entry.get("slug"), str) and entry["slug"].strip():
            title = entry.get("title")
            roster.append(
                {
                    "slug": entry["slug"].strip(),
                    "title": title.strip() if isinstance(title, str) and title.strip() else None,
                }
            )
    return roster


def speakable_title(title: str) -> str:
    """A display title made pronounceable: drop parentheticals, speak '/' and '&' as 'and'."""
    t = _PARENTHETICAL.sub("", title)
    t = t.replace("/", " and ").replace("&", " and ")
    return _WS.sub(" ", t).strip()


def strip_markup(text: str) -> str:
    """Markdown/eye-artifacts → speech: [text](url) keeps the text, raw URLs vanish."""
    text = _MD_LINK.sub(r"\1", text)
    text = _URL_IN_TEXT.sub("", text)
    text = text.replace("**", "").replace("*", "").replace("`", "")
    return _WS.sub(" ", text).strip()


# A "sentence" ending in one of these is a false split ("The No. 1 recruit…", "Oct. 8").
_ABBREV_END = re.compile(
    r"\b(?:No|vs|Mr|Mrs|Ms|Dr|St|Jr|Sr|Gen|Col|Rep|Sen|Gov|U\.S"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|a\.m|p\.m)\.$",
    re.IGNORECASE,
)


def split_sentences(text: str) -> list[str]:
    """Sentences for the ear — merges abbreviation false-splits, never yields a stub."""
    sentences: list[str] = []
    out = ""
    for part in re.split(r"(?<=[.!?])\s+", text.strip()):
        out = f"{out} {part}".strip()
        if len(out) >= 20 and not _ABBREV_END.search(out):
            sentences.append(out)
            out = ""
    if out:
        sentences.append(out)
    return sentences


# Coverage compares only words that carry meaning; these plus anything under 3 letters
# would otherwise let "the … and … with" count as overlap.
_WORD = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset(
    "the and for that with this from his her its was are were has have had "
    "will not but into over after out under about their they them".split()
)
_COVERED_RATIO = 0.7


def significant_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) >= 3 and w not in _STOPWORDS}


def top_story_sentence(top_line: str, item: dict) -> str:
    """The one 'top story' sentence that adds facts the top line didn't already carry.

    The digest's first sentence is virtually always the headline rewritten in fuller
    prose, so the digest — never the headline — is what gets read; the headline only
    fills in for a digest-less item. A sentence is "already covered" when ≥70% of its
    significant words appear in the top line; a sentence too short to judge (under 3
    significant words) always counts as new. A fully covered item narrates nothing —
    silence beats an echo.
    """
    covered = significant_words(top_line)

    def novel(sentence: str) -> bool:
        words = significant_words(sentence)
        if len(words) < 3:
            return True
        return len(words & covered) / len(words) < _COVERED_RATIO

    digest = strip_markup(str(item.get("digest", "")))
    for sentence in split_sentences(digest):
        if novel(sentence):
            return sentence
    if not digest:
        head = strip_markup(str(item.get("headline", "")))
        if head and novel(head):
            return head if head.endswith((".", "!", "?")) else f"{head}."
    return ""


def human_date(date_iso: str) -> str:
    d = date.fromisoformat(date_iso)
    return f"{d:%A}, {d:%B} {d.day}"


def load_topics(day_dir: Path, roster: list[dict]) -> list[dict]:
    """Every usable <slug>.json for the day, page order (roster first, leftovers appended).

    md-only or unparseable topics are simply skipped — they still render on the page via its
    raw-markdown fallback; the audio cut only narrates validated briefs. Dotted stems are
    pipeline artifacts, never topics — including the brief.chapters.json this script writes
    into the same folder (bug #1).
    """
    present = {p.stem for p in day_dir.glob("*.json") if "." not in p.stem}
    roster_slugs = [t["slug"] for t in roster]
    ordered = [s for s in roster_slugs if s in present]
    ordered += sorted(present - set(roster_slugs))
    titles = {t["slug"]: t["title"] for t in roster if t["title"]}

    topics = []
    for slug in ordered:
        try:
            data = json.loads((day_dir / f"{slug}.json").read_text(encoding="utf-8"))
            top_line = str(data["top_line"]).strip()
            items = data.get("items") or []
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
            continue
        if not top_line:
            continue
        title = titles.get(slug) or slug.replace("-", " ").capitalize()
        topics.append({"slug": slug, "title": title, "top_line": top_line, "items": items})
    return topics


def build_script(topics: list[dict], date_iso: str) -> tuple[str, list[dict]]:
    """The deterministic ear script: opener, one compact segment per topic, closer.

    Trim ladder when over MAX_WORDS: drop the top-story sentences from the last topic
    backwards (top lines always survive) — deterministic, never reorders or drops a topic.

    Also returns the FR4 chapter list [{slug, title, start_seconds}] — each topic's start
    offset from the cumulative word count of everything spoken before it, converted with
    the same WORDS_PER_MINUTE the duration line trusts. Computed after the trim ladder
    settles so offsets match the script that actually renders. Titles are the display
    titles (the page's), not the speakable rewrite — chips must read like the page.
    """
    opener = f"Good morning. It's {human_date(date_iso)}, and this is your Home Base brief."
    closer = "That's the brief. The full stories, sources, and your notes are on the Today page."

    segments = []
    for i, topic in enumerate(topics):
        lead = "First up:" if i == 0 else "Next up:"
        intro = f"{lead} {speakable_title(topic['title'])}. {strip_markup(topic['top_line'])}"
        extra = ""
        if topic["items"] and isinstance(topic["items"][0], dict):
            sentence = top_story_sentence(strip_markup(topic["top_line"]), topic["items"][0])
            if sentence:
                extra = f"The top story: {sentence}"
        segments.append({"intro": intro, "extra": extra})

    def assemble() -> str:
        parts = [opener]
        for seg in segments:
            parts.append(f"{seg['intro']} {seg['extra']}".strip())
        parts.append(closer)
        return "\n\n".join(parts)

    script = assemble()
    for seg in reversed(segments):
        if len(script.split()) <= MAX_WORDS:
            break
        seg["extra"] = ""
        script = assemble()

    chapters = []
    words = len(opener.split())
    for topic, seg in zip(topics, segments):
        chapters.append(
            {
                "slug": topic["slug"],
                "title": topic["title"],
                "start_seconds": round(words / WORDS_PER_MINUTE * 60, 1),
            }
        )
        words += len(f"{seg['intro']} {seg['extra']}".strip().split())
    return script, chapters


def is_fresh(out_path: Path, day_dir: Path) -> bool:
    """True when the mp3 already exists and is newer than every <topic>.json of the day."""
    if not out_path.is_file():
        return False
    json_mtimes = [p.stat().st_mtime for p in day_dir.glob("*.json")]
    return bool(json_mtimes) and out_path.stat().st_mtime >= max(json_mtimes)


def render(script: str, url: str, voice: str, speed: float, out_path: Path) -> int:
    """POST the script to Kokoro, atomically write the MP3, return its byte size."""
    payload = json.dumps(
        {"model": "kokoro", "voice": voice, "input": script, "response_format": "mp3", "speed": speed}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as resp:
        audio = resp.read()
    if len(audio) < 1000:
        raise RuntimeError(f"Kokoro returned implausibly small audio ({len(audio)} bytes)")
    tmp = out_path.with_name(out_path.name + ".tmp")
    tmp.write_bytes(audio)
    os.replace(tmp, out_path)
    return len(audio)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD day to narrate")
    ap.add_argument("--sweeps-dir", default=str(ROOT / "data" / "sweeps"), dest="sweeps_dir")
    ap.add_argument("--roster", default=str(Path(__file__).resolve().parent / "topics.json"))
    ap.add_argument("--out", default=None, help="mp3 path (default <sweeps-dir>/<date>/brief.mp3)")
    ap.add_argument("--voice", default=os.environ.get("NARRATE_VOICE", "am_adam"))
    ap.add_argument(
        "--kokoro-url",
        dest="kokoro_url",
        default=os.environ.get("KOKORO_URL", "http://127.0.0.1:8880/v1/audio/speech"),
    )
    ap.add_argument("--speed", type=float, default=float(os.environ.get("NARRATE_SPEED", "1.0")))
    ap.add_argument("--print-script", action="store_true", dest="print_script")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    day_dir = Path(args.sweeps_dir) / args.date
    out_path = Path(args.out) if args.out else day_dir / "brief.mp3"

    if not day_dir.is_dir():
        print(f"audio brief: no sweep folder for {args.date} — nothing to narrate")
        return 0

    if not args.print_script and not args.force and is_fresh(out_path, day_dir):
        print(f"audio brief: {out_path} is already newer than every brief — skipping")
        return 0

    topics = load_topics(day_dir, load_roster(Path(args.roster)))
    if not topics:
        print(f"audio brief: no narratable <topic>.json briefs for {args.date} — nothing to do")
        return 0

    script, chapters = build_script(topics, args.date)
    words = len(script.split())
    minutes = words / WORDS_PER_MINUTE

    if args.print_script:
        print(script)
        print(f"[{words} words ≈ {minutes:.1f} min across {len(topics)} topics]", file=sys.stderr)
        return 0

    # FR4: chapter offsets beside the mp3, written atomically BEFORE the render on
    # purpose — a down Kokoro still lands them, and the API only serves chapters when the
    # mp3 actually exists, so an orphan file is inert. Best-effort like everything here:
    # a failed write warns and never blocks the narration.
    chapters_path = out_path.with_name(out_path.stem + ".chapters.json")
    try:
        tmp = chapters_path.with_name(chapters_path.name + ".tmp")
        tmp.write_text(json.dumps(chapters), encoding="utf-8")
        os.replace(tmp, chapters_path)
    except OSError as e:
        print(f"!! audio brief: couldn't write {chapters_path} ({e}) — chips skipped", file=sys.stderr)

    try:
        size = render(script, args.kokoro_url, args.voice, args.speed, out_path)
    except (urllib.error.URLError, OSError, RuntimeError) as e:
        print(
            f"!! audio brief: Kokoro render failed against {args.kokoro_url} ({e}) — "
            "is the com.voicemode.kokoro agent running?",
            file=sys.stderr,
        )
        return 1

    print(
        f"audio brief: {out_path} ({size} bytes, {words} words ≈ {minutes:.1f} min, "
        f"{len(topics)} topics, voice={args.voice})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
