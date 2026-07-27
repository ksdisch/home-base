"""M4 sweeps/audio_brief.py — the ear-script builder and its degrade contract.

The script is a repo-root pipeline tool (stdlib, system python3), not part of the app
package, so it's exercised as a subprocess the way sweep.sh runs it. Always synthetic day
dirs under tmp_path — never the real data/sweeps; the render-path tests point at an
unroutable Kokoro URL and assert the failure/skip contract instead of ever doing TTS.
House rules under test: audio is a bonus (bad topics are skipped, empty days are a clean
exit 0, a down Kokoro exits non-zero without leaving a file); the freshness check must
short-circuit before any network I/O; the spoken script carries no markdown or URLs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "sweeps" / "audio_brief.py"
# Connection-refused immediately; if the script ever tried to render, it would exit 1.
UNROUTABLE = "http://127.0.0.1:1/v1/audio/speech"


def _brief(top_line: str, headline: str = "", digest: str = "") -> str:
    items = []
    if headline:
        items.append(
            {
                "headline": headline,
                "attribution": "Somewhere, July 14, 2026",
                "digest": digest or "First sentence of the digest. Second sentence.",
                "why_it_matters": "It matters.",
                "sources": [{"title": "Src", "url": "https://example.com/s"}],
            }
        )
    return json.dumps({"top_line": top_line, "items": items})


def _setup(tmp_path, date="2026-07-15", roster=None, files=None):
    sweeps = tmp_path / "sweeps"
    day = sweeps / date
    day.mkdir(parents=True)
    for fname, text in (files or {}).items():
        (day / fname).write_text(text, encoding="utf-8")
    roster_file = tmp_path / "topics.json"
    roster_file.write_text(json.dumps(roster if roster is not None else []), encoding="utf-8")
    return sweeps, roster_file


def _run(sweeps, roster_file, *extra, date="2026-07-15"):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--date",
            date,
            "--sweeps-dir",
            str(sweeps),
            "--roster",
            str(roster_file),
            *extra,
        ],
        capture_output=True,
        text=True,
    )


# -- the ear script ---------------------------------------------------------------


def test_script_roster_order_speakable_titles_opener_closer(tmp_path):
    """Roster order beats alphabetical; '/', '&', and parentheticals never reach the ear."""
    roster = [
        {"slug": "market-tech-news", "title": "Market & tech news", "paused": False},
        {"slug": "ai-llms", "title": "AI / LLMs", "paused": True},  # paused still narrates
        {"slug": "indiana", "title": "Indiana Hoosiers (FB + BB)", "paused": False},
    ]
    sweeps, roster_file = _setup(
        tmp_path,
        roster=roster,
        files={
            "ai-llms.json": _brief("AI line.", "AI headline"),
            "market-tech-news.json": _brief("Market line.", "Market headline"),
            "indiana.json": _brief("Indiana line.", "Indiana headline"),
            "zz-extra.json": _brief("Extra line.", "Extra headline"),  # not in the roster
        },
    )
    r = _run(sweeps, roster_file, "--print-script")
    assert r.returncode == 0, r.stderr
    script = r.stdout
    assert "Wednesday, July 15" in script  # honest dated opener
    assert script.strip().endswith("on the Today page.")
    order = [script.index("Market and tech news"), script.index("AI and LLMs"), script.index("Indiana Hoosiers"), script.index("Zz extra")]
    assert order == sorted(order)
    for eye_artifact in ("&", "/", "(FB", "(BB"):
        head = script.split("Market line.")[0]  # the spoken-titles region of topic 1
        assert eye_artifact not in head


def test_script_strips_markdown_and_urls(tmp_path):
    sweeps, roster_file = _setup(
        tmp_path,
        files={
            "ai-llms.json": _brief(
                "A **bold** [linked](https://example.com/x) top line.",
                "Headline with [TSMC](https://tsmc.example) inside",
                "Digest cites https://raw.example.com/path directly. Second sentence.",
            )
        },
    )
    r = _run(sweeps, roster_file, "--print-script")
    assert r.returncode == 0, r.stderr
    assert "TSMC" in r.stdout and "linked" in r.stdout
    for eye_artifact in ("**", "](", "https://", "http://"):
        assert eye_artifact not in r.stdout


def test_script_survives_abbreviation_sentence_splits(tmp_path):
    """'The No. 1 recruit…' must narrate as a whole sentence, not a dangling 'The No.'."""
    sweeps, roster_file = _setup(
        tmp_path,
        files={
            "ai-llms.json": _brief(
                "Top line.",
                "A headline",
                "The No. 1 recruit picked Kansas on Friday. Unrelated second sentence.",
            )
        },
    )
    r = _run(sweeps, roster_file, "--print-script")
    assert "The No. 1 recruit picked Kansas on Friday." in r.stdout
    assert "Unrelated second sentence" not in r.stdout


def test_script_skips_unparseable_topics_but_keeps_the_rest(tmp_path):
    sweeps, roster_file = _setup(
        tmp_path,
        files={
            "good.json": _brief("Good line.", "Good headline"),
            "broken.json": "{not json at all",
            "md-only.md": "# md-only — as of stamp\n\nlegacy",
        },
    )
    r = _run(sweeps, roster_file, "--print-script")
    assert r.returncode == 0, r.stderr
    assert "Good line." in r.stdout
    assert "broken" not in r.stdout and "md-only" not in r.stdout


def test_script_trims_headlines_from_the_end_to_fit_the_word_budget(tmp_path):
    """Over budget: later topics lose their 'top story' sentence; every top line survives."""
    long_digest = ("word " * 70).strip() + "."
    files = {
        f"topic-{i}.json": _brief(f"Top line number {i} with a few extra words in it.", f"Headline {i}", long_digest)
        for i in range(1, 9)
    }
    roster = [{"slug": f"topic-{i}", "title": f"Topic {i}", "paused": False} for i in range(1, 9)]
    sweeps, roster_file = _setup(tmp_path, roster=roster, files=files)
    r = _run(sweeps, roster_file, "--print-script")
    assert r.returncode == 0, r.stderr
    script = r.stdout
    assert len(script.split()) <= 700
    for i in range(1, 9):  # no topic is ever dropped
        assert f"Top line number {i}" in script
    assert "Headline 1" in script  # trimming starts from the END
    assert "Headline 8" not in script


# -- empty / missing days ---------------------------------------------------------


def test_no_day_folder_is_a_clean_noop(tmp_path):
    sweeps, roster_file = _setup(tmp_path)
    r = _run(sweeps, roster_file, date="2026-07-01")
    assert r.returncode == 0
    assert "nothing to narrate" in r.stdout


def test_day_with_no_usable_json_is_a_clean_noop(tmp_path):
    sweeps, roster_file = _setup(tmp_path, files={"only.md": "# legacy md day"})
    r = _run(sweeps, roster_file, "--kokoro-url", UNROUTABLE)
    assert r.returncode == 0
    assert "nothing to do" in r.stdout
    assert not (sweeps / "2026-07-15" / "brief.mp3").exists()


# -- render contract (no real TTS ever) --------------------------------------------


def test_kokoro_down_exits_nonzero_and_leaves_no_file(tmp_path):
    sweeps, roster_file = _setup(tmp_path, files={"ai-llms.json": _brief("Line.", "Headline")})
    r = _run(sweeps, roster_file, "--kokoro-url", UNROUTABLE)
    assert r.returncode == 1
    assert "Kokoro" in r.stderr
    day = sweeps / "2026-07-15"
    assert not (day / "brief.mp3").exists()
    assert not list(day.glob("*.tmp"))  # no half-written artifacts either


def test_fresh_mp3_skips_before_any_network_io(tmp_path):
    """brief.mp3 newer than every <topic>.json → exit 0 'skipping' even though the Kokoro
    URL is unroutable — proof the freshness check short-circuits the render entirely."""
    sweeps, roster_file = _setup(tmp_path, files={"ai-llms.json": _brief("Line.", "Headline")})
    day = sweeps / "2026-07-15"
    mp3 = day / "brief.mp3"
    mp3.write_bytes(b"\xff\xfbexisting")
    newest = max(p.stat().st_mtime for p in day.glob("*.json")) + 60
    os.utime(mp3, (newest, newest))
    r = _run(sweeps, roster_file, "--kokoro-url", UNROUTABLE)
    assert r.returncode == 0, r.stderr
    assert "skipping" in r.stdout
    assert mp3.read_bytes() == b"\xff\xfbexisting"


def test_stale_mp3_attempts_a_rerender(tmp_path):
    """A <topic>.json newer than the mp3 (late-finishing topic) must NOT skip — with Kokoro
    unroutable that surfaces as the render failure, proving the regenerate was attempted."""
    sweeps, roster_file = _setup(tmp_path, files={"ai-llms.json": _brief("Line.", "Headline")})
    day = sweeps / "2026-07-15"
    mp3 = day / "brief.mp3"
    mp3.write_bytes(b"\xff\xfbstale")
    oldest = min(p.stat().st_mtime for p in day.glob("*.json")) - 60
    os.utime(mp3, (oldest, oldest))
    r = _run(sweeps, roster_file, "--kokoro-url", UNROUTABLE)
    assert r.returncode == 1
    assert mp3.read_bytes() == b"\xff\xfbstale"  # the failed rerender never clobbers the old file


# -- FR4 audio chapters -----------------------------------------------------------
# build_script's own word math yields per-topic start offsets essentially for free; the
# script writes them to brief.chapters.json beside the mp3 so the page can render seek
# chips over the single 5-minute track.


def test_chapters_json_written_with_word_offset_starts(tmp_path):
    """Chapters land even when Kokoro is down — written before the render, since the API
    only serves them when the mp3 exists (an orphan file is inert). One entry per narrated
    topic in script order, DISPLAY titles (chips must match the page, not the speakable
    rewrite), offsets from the same WORDS_PER_MINUTE the duration line already trusts."""
    sweeps, roster_file = _setup(
        tmp_path,
        roster=[
            {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
            {"slug": "fantasy-football", "title": "Fantasy football", "paused": False},
        ],
        files={
            "ai-llms.json": _brief("One release worth your time.", "OpenAI lifts caps"),
            "fantasy-football.json": _brief("Quiet camp-eve Monday.", "Colts telegraph workload"),
        },
    )
    r = _run(sweeps, roster_file, "--kokoro-url", UNROUTABLE)
    assert r.returncode == 1  # the mp3 contract is unchanged
    chapters = json.loads(
        (sweeps / "2026-07-15" / "brief.chapters.json").read_text(encoding="utf-8")
    )
    assert [c["slug"] for c in chapters] == ["ai-llms", "fantasy-football"]
    assert chapters[0]["title"] == "AI / LLMs"  # display title, not "AI and LLMs"
    # The opener is a fixed 13 words; topic one starts right after it.
    assert chapters[0]["start_seconds"] == pytest.approx(13 / 155 * 60, abs=0.06)
    assert 0 < chapters[0]["start_seconds"] < chapters[1]["start_seconds"]
    assert not list((sweeps / "2026-07-15").glob("*.tmp"))  # atomic like the mp3


def test_pipeline_artifacts_are_never_narrated_as_topics(tmp_path):
    """Bug #1's audio lane: load_topics built its slug set from every *.json in the day
    folder — including the brief.chapters.json this very script writes there.

    Today that file is a JSON *list*, so the ``data["top_line"]`` read raises and the
    artifact is skipped by accident of shape. A dict-shaped one removes the accident: the
    guard has to be the dotted stem (as sweeps/actions_queue.py already reads it), or the
    narration can open a segment for a file that is not a topic.
    """
    sweeps, roster_file = _setup(
        tmp_path,
        files={
            "ai-llms.json": _brief("One release worth your time.", "OpenAI lifts caps"),
            "brief.chapters.json": json.dumps(
                {"top_line": "Chapter offsets, read aloud.", "items": []}
            ),
        },
    )
    r = _run(sweeps, roster_file, "--print-script")
    assert r.returncode == 0, r.stderr
    assert "Chapter offsets" not in r.stdout
    assert "across 1 topics" in r.stderr


def test_print_script_writes_no_chapters(tmp_path):
    sweeps, roster_file = _setup(tmp_path, files={"ai-llms.json": _brief("Line.", "Headline")})
    r = _run(sweeps, roster_file, "--print-script")
    assert r.returncode == 0, r.stderr
    assert not (sweeps / "2026-07-15" / "brief.chapters.json").exists()


def test_trim_zeroed_topics_still_get_chapters(tmp_path):
    """The trim ladder only drops a late topic's 'top story' sentence — its intro line
    always survives, so every narrated topic keeps a real chapter offset."""
    long_digest = ("word " * 70).strip() + "."
    files = {
        f"topic-{i}.json": _brief(f"Top line number {i} here.", f"Headline {i}", long_digest)
        for i in range(1, 9)
    }
    roster = [{"slug": f"topic-{i}", "title": f"Topic {i}", "paused": False} for i in range(1, 9)]
    sweeps, roster_file = _setup(tmp_path, roster=roster, files=files)
    r = _run(sweeps, roster_file, "--kokoro-url", UNROUTABLE)
    assert r.returncode == 1
    chapters = json.loads(
        (sweeps / "2026-07-15" / "brief.chapters.json").read_text(encoding="utf-8")
    )
    assert [c["slug"] for c in chapters] == [f"topic-{i}" for i in range(1, 9)]
    starts = [c["start_seconds"] for c in chapters]
    assert starts == sorted(starts) and len(set(starts)) == len(starts)
