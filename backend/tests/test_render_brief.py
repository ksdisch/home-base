"""sweeps/render_brief.py — the write-time trust gate between ``claude -p`` and the page.

Loaded via importlib straight from the repo's sweeps/ dir: the script is stdlib-only and
lives outside the backend package on purpose (the runner must never need the venv), but its
validation IS the M1 trust invariant, so it gets tested with the backend suite.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "sweeps" / "render_brief.py"
_spec = importlib.util.spec_from_file_location("render_brief", MODULE_PATH)
render_brief = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_brief)

GOOD = {
    "top_line": "One release worth your time.",
    "context_note": "  Dead-offseason window.  ",
    "items": [
        {
            "headline": " OpenAI lifts caps ",
            "attribution": "Bleeping Computer, July 12, 2026",
            "digest": "OpenAI lifted the cap.",
            "why_it_matters": "Budget math changes.",
            "sources": [
                {"title": "Bleeping Computer", "url": "https://example.com/a"},
                {"title": "Digital Trends", "url": "https://example.com/b"},
            ],
        }
    ],
}


# -- extract_json ladder ---------------------------------------------------------


def test_extract_exact_json():
    assert render_brief.extract_json(json.dumps(GOOD))["top_line"] == GOOD["top_line"]


def test_extract_fenced_json():
    fenced = "```json\n" + json.dumps(GOOD) + "\n```"
    assert render_brief.extract_json(fenced)["top_line"] == GOOD["top_line"]


def test_extract_json_with_preamble_chatter():
    wrapped = "Here is the brief you asked for:\n" + json.dumps(GOOD) + "\nHope that helps!"
    assert render_brief.extract_json(wrapped)["top_line"] == GOOD["top_line"]


def test_extract_garbage_raises():
    try:
        render_brief.extract_json("no json here at all")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_extract_top_level_list_raises():
    try:
        render_brief.extract_json("[1, 2, 3]")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


# -- validate: the hard rules ------------------------------------------------------


def test_validate_good_is_clean():
    assert render_brief.validate(GOOD) == []


def test_validate_flags_missing_fields_and_sources():
    bad = {
        "top_line": "",
        "items": [
            {"headline": "x", "attribution": "a", "digest": "d", "why_it_matters": "w", "sources": []},
            {"headline": "y", "attribution": "a", "digest": "d", "why_it_matters": "w",
             "sources": [{"title": "t", "url": "notaurl"}]},
            {"headline": "", "attribution": "a", "digest": "d", "why_it_matters": "w",
             "sources": [{"title": "t", "url": "https://ok.example"}]},
        ],
    }
    problems = "\n".join(render_brief.validate(bad))
    assert "top_line" in problems
    assert "items[0].sources" in problems  # the ≥1-real-URL hard rule
    assert "items[1].sources[0].url" in problems
    assert "items[2].headline" in problems


def test_validate_items_must_be_list():
    assert render_brief.validate({"top_line": "x", "items": "nope"}) != []


# -- normalize + render -------------------------------------------------------------


def test_normalize_wraps_and_strips():
    brief = render_brief.normalize(GOOD, "ai-llms", "2026-07-14", "2026-07-14 07:05 CDT")
    assert brief["topic"] == "ai-llms"
    assert brief["date"] == "2026-07-14"
    assert brief["as_of"] == "2026-07-14 07:05 CDT"
    assert brief["items"][0]["headline"] == "OpenAI lifts caps"  # stripped
    assert brief["context_note"] == "Dead-offseason window."


def test_normalize_blank_note_becomes_none():
    src = {**GOOD, "context_note": "   "}
    assert render_brief.normalize(src, "t", "d", "a")["context_note"] is None


def test_render_markdown_matches_gradeable_shape():
    brief = render_brief.normalize(GOOD, "ai-llms", "2026-07-14", "2026-07-14 07:05 CDT")
    md = render_brief.render_markdown(brief)
    assert md.splitlines()[0] == "# ai-llms — as of 2026-07-14 07:05 CDT"
    assert "**One release worth your time.**" in md
    assert "Dead-offseason window." in md
    assert "### OpenAI lifts caps — Bleeping Computer, July 12, 2026" in md
    assert "**Why it matters:** Budget math changes." in md
    assert (
        "**Sources:** [Bleeping Computer](https://example.com/a) · "
        "[Digital Trends](https://example.com/b)" in md
    )


# -- main(): end-to-end file behaviour ----------------------------------------------


def _run_main(monkeypatch, tmp_path, raw_text: str, topic: str = "ai-llms") -> int:
    raw = tmp_path / "raw.txt"
    raw.write_text(raw_text, encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "render_brief.py",
            "--topic", topic,
            "--date", "2026-07-14",
            "--as-of", "2026-07-14 07:05 CDT",
            "--raw", str(raw),
            "--out-dir", str(out),
        ],
    )
    return render_brief.main()


def test_main_valid_writes_json_and_md(monkeypatch, tmp_path):
    rc = _run_main(monkeypatch, tmp_path, json.dumps(GOOD))
    assert rc == 0
    out = tmp_path / "out"
    data = json.loads((out / "ai-llms.json").read_text(encoding="utf-8"))
    assert data["topic"] == "ai-llms"
    assert (out / "ai-llms.md").read_text(encoding="utf-8").startswith("# ai-llms — as of ")
    assert not (out / "ai-llms.raw.txt").exists()


def test_main_invalid_keeps_raw_and_fails(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, "total garbage, not json")
    assert rc == 1
    out = tmp_path / "out"
    assert (out / "ai-llms.raw.txt").read_text(encoding="utf-8") == "total garbage, not json"
    assert not (out / "ai-llms.json").exists()
    assert not (out / "ai-llms.md").exists()
    assert "invalid sweep JSON" in capsys.readouterr().err
