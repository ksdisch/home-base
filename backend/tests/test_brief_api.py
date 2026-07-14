"""M1 /api/brief — the Today page's read path over data/sweeps/, plus the visit log.

Synthetic sweep folders only (never the real data/sweeps): JSON days, legacy md-only days,
malformed-json fallback, latest-date selection, .raw.txt skipping, roster ordering, and the
brief_visits habit-metric write. House rules under test: never a 500 on missing data; a
topic is never silently dropped; failed-validation raw output never reaches the page.
"""

from __future__ import annotations

import json
import re
import sqlite3

VALID_BRIEF = {
    "topic": "ai-llms",
    "date": "2026-07-14",
    "as_of": "2026-07-14 07:05 CDT",
    "top_line": "One release actually worth your time.",
    "context_note": None,
    "items": [
        {
            "headline": "OpenAI lifts caps",
            "attribution": "Bleeping Computer, July 13, 2026",
            "digest": "OpenAI removed the rolling 5-hour cap.",
            "why_it_matters": "Shapes your agent session budget.",
            "sources": [{"title": "Bleeping Computer", "url": "https://example.com/a"}],
        }
    ],
}

LEGACY_MD = """# fantasy-football — as of 2026-07-13 16:47 CDT

**Quiet camp-eve Monday.**

### Colts telegraph lighter Taylor workload — PFR, July 11
Digest here.
**Why it matters:** Volume stays.
**Sources:** [PFR](https://example.com/pfr)
"""


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _env(tmp_path, monkeypatch, name: str):
    """Fresh store + fresh sweeps dir, both isolated under tmp_path."""
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    return sweeps


def _write_day(sweeps, date: str, files: dict[str, str]):
    day = sweeps / date
    day.mkdir(parents=True, exist_ok=True)
    for fname, text in files.items():
        (day / fname).write_text(text, encoding="utf-8")
    return day


# -- empty / missing ------------------------------------------------------------


def test_brief_no_sweeps_dir_degrades(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, "nodir")
    monkeypatch.setenv("SWEEPS_DIR", str(tmp_path / "nodir" / "does-not-exist"))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is False
        assert body["date"] is None
        assert body["topics"] == []
    finally:
        get_settings.cache_clear()


def test_brief_empty_sweeps_dir_degrades(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, "empty")
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is False
        assert body["date"] is None
    finally:
        get_settings.cache_clear()


# -- structured JSON days ---------------------------------------------------------


def test_brief_serves_latest_json_day(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "latest")
    _write_day(sweeps, "2026-07-13", {"fantasy-football.md": LEGACY_MD})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is True
        assert body["date"] == "2026-07-14"
        assert len(body["topics"]) == 1
        topic = body["topics"][0]
        assert topic["slug"] == "ai-llms"
        assert topic["title"] == "AI / LLMs"
        assert topic["as_of"] == "2026-07-14 07:05 CDT"
        assert topic["top_line"] == VALID_BRIEF["top_line"]
        assert topic["raw_markdown"] is None
        assert topic["error"] is None
        item = topic["items"][0]
        assert item["headline"] == "OpenAI lifts caps"
        assert item["sources"][0]["url"] == "https://example.com/a"
    finally:
        get_settings.cache_clear()


def test_brief_json_wins_over_md_render(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "jsonwins")
    _write_day(
        sweeps,
        "2026-07-14",
        {"ai-llms.json": json.dumps(VALID_BRIEF), "ai-llms.md": "# rendered view\nignored"},
    )
    from app.config import get_settings

    try:
        topic = _client().get("/api/brief").json()["topics"][0]
        assert topic["top_line"] == VALID_BRIEF["top_line"]
        assert topic["raw_markdown"] is None
    finally:
        get_settings.cache_clear()


# -- fallbacks: a topic is never silently dropped ---------------------------------


def test_brief_legacy_md_only_day_falls_back_to_raw(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "legacy")
    _write_day(sweeps, "2026-07-13", {"fantasy-football.md": LEGACY_MD})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is True
        topic = body["topics"][0]
        assert topic["title"] == "Fantasy football"
        assert topic["as_of"] == "2026-07-13 16:47 CDT"
        assert topic["items"] == []
        assert topic["error"] is None
        assert topic["raw_markdown"].startswith("**Quiet camp-eve Monday.**")
        assert "as of 2026-07-13" not in topic["raw_markdown"]  # header consumed into as_of
    finally:
        get_settings.cache_clear()


def test_brief_bad_json_falls_back_to_md_with_error(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "badjson")
    _write_day(
        sweeps,
        "2026-07-14",
        {"ai-llms.json": "{not valid json", "ai-llms.md": LEGACY_MD.replace("fantasy-football", "ai-llms")},
    )
    from app.config import get_settings

    try:
        topic = _client().get("/api/brief").json()["topics"][0]
        assert topic["error"] is not None and "ai-llms.json" in topic["error"]
        assert topic["raw_markdown"] is not None
        assert topic["items"] == []
    finally:
        get_settings.cache_clear()


def test_brief_bad_json_without_md_still_lists_topic(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "badalone")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": '{"top_line": 42}'})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is True
        topic = body["topics"][0]
        assert topic["error"] is not None
        assert topic["raw_markdown"] is None
        assert topic["items"] == []
    finally:
        get_settings.cache_clear()


def test_brief_skips_raw_txt_failures(tmp_path, monkeypatch):
    """A sweep that failed validation left only .raw.txt — it must not reach the page."""
    sweeps = _env(tmp_path, monkeypatch, "rawtxt")
    _write_day(sweeps, "2026-07-14", {"ai-llms.raw.txt": "unvalidated model output"})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["date"] == "2026-07-14"
        assert body["topics"] == []
        assert body["has_data"] is False
    finally:
        get_settings.cache_clear()


def test_brief_roster_order_then_unknowns(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "order")
    day = {
        "market-tech-news.json": json.dumps({**VALID_BRIEF, "topic": "market-tech-news"}),
        "ai-llms.json": json.dumps(VALID_BRIEF),
        "zzz-custom.json": json.dumps({**VALID_BRIEF, "topic": "zzz-custom"}),
        "fantasy-football.json": json.dumps({**VALID_BRIEF, "topic": "fantasy-football"}),
    }
    _write_day(sweeps, "2026-07-14", day)
    from app.config import get_settings

    try:
        topics = _client().get("/api/brief").json()["topics"]
        assert [t["slug"] for t in topics] == [
            "ai-llms",
            "fantasy-football",
            "market-tech-news",
            "zzz-custom",
        ]
        assert topics[-1]["title"] == "Zzz custom"  # humanized fallback title
    finally:
        get_settings.cache_clear()


def test_brief_non_string_as_of_is_coerced_not_500(tmp_path, monkeypatch):
    """A hand-edited json with a numeric as_of must not 500 the whole brief."""
    sweeps = _env(tmp_path, monkeypatch, "asof")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({**VALID_BRIEF, "as_of": 123})})
    from app.config import get_settings

    try:
        res = _client().get("/api/brief")
        assert res.status_code == 200
        assert res.json()["topics"][0]["as_of"] == "123"
    finally:
        get_settings.cache_clear()


# -- the visit log (the habit metric) ----------------------------------------------


def test_brief_visit_logged(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, "visits")
    from app.config import get_settings

    try:
        client = _client()
        body = client.post("/api/brief/visit").json()
        assert body["ok"] is True
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", body["day"])
        assert body["visited_at"].startswith(body["day"])

        client.post("/api/brief/visit")
        conn = sqlite3.connect(get_settings().db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM brief_visits").fetchone()[0]
            days = conn.execute("SELECT COUNT(DISTINCT day) FROM brief_visits").fetchone()[0]
        finally:
            conn.close()
        assert total == 2  # every load logged…
        assert days == 1  # …the metric is distinct days
    finally:
        get_settings.cache_clear()
