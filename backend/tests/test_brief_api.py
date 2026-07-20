"""M1 /api/brief — the Today page's read path over data/sweeps/, plus the visit log.

Synthetic sweep folders + a synthetic roster file only (never the real data/sweeps or
sweeps/topics.json): JSON days, legacy md-only days, malformed-json fallback, latest-date
selection, .raw.txt skipping, config-roster titles/ordering/pause semantics (M2), and the
brief_visits habit-metric write. House rules under test: never a 500 on missing data; a
topic is never silently dropped; failed-validation raw output never reaches the page; a
broken roster file degrades the titles, never the brief.
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


# The synthetic stand-in for sweeps/topics.json — mirrors the M0 pilot roster so the
# pre-M2 assertions (titles, pilot ordering) keep meaning what they always meant.
PILOT_ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "fantasy-football", "title": "Fantasy football", "paused": False},
    {"slug": "market-tech-news", "title": "Market & tech news", "paused": False},
]


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _env(tmp_path, monkeypatch, name: str, roster=PILOT_ROSTER):
    """Fresh store + fresh sweeps dir + synthetic roster file, all isolated under tmp_path."""
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    roster_file = tmp_path / name / "topics.json"
    roster_file.write_text(json.dumps(roster), encoding="utf-8")
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("ROSTER_FILE", str(roster_file))
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


def test_brief_unreadable_json_degrades_to_md_fallback_not_500(tmp_path, monkeypatch):
    """Bug #7: a permission-denied <topic>.json (bad perms, mid-swap replacement) must
    degrade that one topic to the md fallback — never take down the whole Today page.
    Every other read in the module already catches OSError; this is the read that serves."""
    sweeps = _env(tmp_path, monkeypatch, "unreadablejson")
    day = _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "ai-llms.md": LEGACY_MD.replace("fantasy-football", "ai-llms"),
        },
    )
    (day / "ai-llms.json").chmod(0o000)
    from app.config import get_settings

    try:
        resp = _client().get("/api/brief")
        assert resp.status_code == 200
        topic = resp.json()["topics"][0]
        assert topic["error"] is not None and "ai-llms.json" in topic["error"]
        assert topic["raw_markdown"] is not None
        assert topic["items"] == []
    finally:
        (day / "ai-llms.json").chmod(0o644)
        get_settings.cache_clear()


def test_brief_unreadable_md_in_fallback_degrades_not_500(tmp_path, monkeypatch):
    """Bug #7's second site: the designated fallback path itself. An md-only day whose
    .md can't be read must fall through to the 'no readable brief' card, not 500."""
    sweeps = _env(tmp_path, monkeypatch, "unreadablemd")
    day = _write_day(sweeps, "2026-07-14", {"ai-llms.md": LEGACY_MD})
    (day / "ai-llms.md").chmod(0o000)
    from app.config import get_settings

    try:
        resp = _client().get("/api/brief")
        assert resp.status_code == 200
        topic = resp.json()["topics"][0]
        assert topic["error"] is not None and "no readable brief" in topic["error"]
        assert topic["raw_markdown"] is None
        assert topic["items"] == []
    finally:
        (day / "ai-llms.md").chmod(0o644)
        get_settings.cache_clear()


def test_brief_skips_raw_txt_failures(tmp_path, monkeypatch):
    """A sweep that failed validation left only .raw.txt — it must not reach the page.

    With no other day to fall back to, the whole day is unservable and the brief
    honestly reports no data at all (latest_sweep_date skips contentless dirs)."""
    sweeps = _env(tmp_path, monkeypatch, "rawtxt")
    _write_day(sweeps, "2026-07-14", {"ai-llms.raw.txt": "unvalidated model output"})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["date"] is None
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


# -- the roster config file (M2) ---------------------------------------------------


def test_brief_missing_roster_file_humanizes_not_500(tmp_path, monkeypatch):
    """No sweeps/topics.json → humanized titles and a working brief, never a crash."""
    sweeps = _env(tmp_path, monkeypatch, "noroster")
    monkeypatch.setenv("ROSTER_FILE", str(tmp_path / "noroster" / "does-not-exist.json"))
    from app.config import get_settings

    get_settings.cache_clear()
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    try:
        res = _client().get("/api/brief")
        assert res.status_code == 200
        topic = res.json()["topics"][0]
        assert topic["title"] == "Ai llms"  # humanized fallback, not the roster title
        assert topic["top_line"] == VALID_BRIEF["top_line"]
    finally:
        get_settings.cache_clear()


def test_brief_invalid_roster_json_degrades_not_500(tmp_path, monkeypatch):
    """A hand-edit that breaks topics.json must degrade titles, never the brief."""
    sweeps = _env(tmp_path, monkeypatch, "badroster")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    # The roster file is re-read per request, so breaking it now is enough.
    (tmp_path / "badroster" / "topics.json").write_text("{not json", encoding="utf-8")
    from app.config import get_settings

    try:
        res = _client().get("/api/brief")
        assert res.status_code == 200
        topic = res.json()["topics"][0]
        assert topic["title"] == "Ai llms"
        assert topic["items"][0]["headline"] == "OpenAI lifts caps"
    finally:
        get_settings.cache_clear()


def test_brief_paused_topic_with_data_still_displays(tmp_path, monkeypatch):
    """Pausing gates the sweep, not the page — existing files still render in roster order."""
    roster = [
        {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
        {"slug": "fantasy-football", "title": "Fantasy football", "paused": True},
    ]
    sweeps = _env(tmp_path, monkeypatch, "paused", roster=roster)
    _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "fantasy-football.json": json.dumps({**VALID_BRIEF, "topic": "fantasy-football"}),
        },
    )
    from app.config import get_settings

    try:
        topics = _client().get("/api/brief").json()["topics"]
        assert [t["slug"] for t in topics] == ["ai-llms", "fantasy-football"]
        assert topics[1]["title"] == "Fantasy football"  # roster title, despite the pause
        assert topics[1]["error"] is None
    finally:
        get_settings.cache_clear()


def test_brief_roster_file_defines_titles_and_order(tmp_path, monkeypatch):
    """Roster order wins over alphabetical; roster titles win over humanizing."""
    roster = [
        {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False},
        {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    ]
    sweeps = _env(tmp_path, monkeypatch, "rosterorder", roster=roster)
    _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "chiefs.json": json.dumps({**VALID_BRIEF, "topic": "chiefs"}),
            "zzz-custom.json": json.dumps({**VALID_BRIEF, "topic": "zzz-custom"}),
        },
    )
    from app.config import get_settings

    try:
        topics = _client().get("/api/brief").json()["topics"]
        assert [t["slug"] for t in topics] == ["chiefs", "ai-llms", "zzz-custom"]
        assert topics[0]["title"] == "Kansas City Chiefs"
        assert topics[2]["title"] == "Zzz custom"  # unknown slug still humanizes
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


# -- read-time dedup: "developing" labels (M3) -------------------------------------


def _dev_item(headline: str, url: str, digest: str = "d") -> dict:
    return {
        "headline": headline,
        "attribution": "a",
        "digest": digest,
        "why_it_matters": "w",
        "sources": [{"title": "S", "url": url}],
    }


def test_brief_flags_repeat_as_developing(tmp_path, monkeypatch):
    """A story that ran on an earlier day is labelled developing + first_seen; a fresh one isn't."""
    sweeps = _env(tmp_path, monkeypatch, "dev_repeat")
    repeat = _dev_item("OpenAI lifts caps", "https://example.com/a")
    fresh = _dev_item("Brand new thing ships", "https://example.com/z")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps({"top_line": "t", "items": [repeat]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [repeat, fresh]})})
    from app.config import get_settings

    try:
        items = {it["headline"]: it for it in _client().get("/api/brief").json()["topics"][0]["items"]}
        assert items["OpenAI lifts caps"]["developing"] is True
        assert items["OpenAI lifts caps"]["first_seen"] == "2026-07-13"
        assert items["Brand new thing ships"]["developing"] is False
        assert items["Brand new thing ships"]["first_seen"] is None
    finally:
        get_settings.cache_clear()


def test_brief_developing_matches_on_shared_source_url(tmp_path, monkeypatch):
    """A reworded headline is still caught as developing when it shares a source URL
    (tracking params like utm_* are noise, not identity)."""
    sweeps = _env(tmp_path, monkeypatch, "dev_url")
    day1 = _dev_item("DeepSeek eyes IPO", "https://techcrunch.com/deepseek-ipo")
    day2 = _dev_item("DeepSeek: what the IPO means", "https://techcrunch.com/deepseek-ipo?utm_source=x")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day1]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day2]})})
    from app.config import get_settings

    try:
        item = _client().get("/api/brief").json()["topics"][0]["items"][0]
        assert item["developing"] is True
        assert item["first_seen"] == "2026-07-13"
    finally:
        get_settings.cache_clear()


def test_brief_dedup_url_identity_keeps_the_query_string(tmp_path, monkeypatch):
    """Bug #6: watch?v=AAA and watch?v=ZZZ are different stories — the query string is part
    of URL identity, so distinct query-keyed URLs must not collide into a false 'developing'
    (the docstring invariant: conservative, a fresh item is never mislabeled)."""
    sweeps = _env(tmp_path, monkeypatch, "dev_query")
    day1 = _dev_item("Highlight reel: game one", "https://youtube.com/watch?v=AAA")
    day2 = _dev_item("Postgame presser: game two", "https://youtube.com/watch?v=ZZZ")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day1]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day2]})})
    from app.config import get_settings

    try:
        item = _client().get("/api/brief").json()["topics"][0]["items"][0]
        assert item["developing"] is False
        assert item["first_seen"] is None
    finally:
        get_settings.cache_clear()


def test_brief_developing_is_per_topic(tmp_path, monkeypatch):
    """History is matched within a topic — the same headline under a different topic doesn't flag."""
    sweeps = _env(tmp_path, monkeypatch, "dev_pertopic")
    shared = _dev_item("Same headline everywhere", "https://example.com/x")
    _write_day(sweeps, "2026-07-13", {"fantasy-football.json": json.dumps({"top_line": "t", "items": [shared]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [shared]})})
    from app.config import get_settings

    try:
        topics = {t["slug"]: t for t in _client().get("/api/brief").json()["topics"]}
        assert topics["ai-llms"]["items"][0]["developing"] is False
    finally:
        get_settings.cache_clear()


def test_brief_developing_ignores_history_beyond_lookback(tmp_path, monkeypatch):
    """Only the last week counts — a recurrence from >7 days earlier is treated as fresh."""
    sweeps = _env(tmp_path, monkeypatch, "dev_window")
    item = _dev_item("Old recurring story", "https://example.com/old")
    _write_day(sweeps, "2026-07-01", {"ai-llms.json": json.dumps({"top_line": "t", "items": [item]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [item]})})
    from app.config import get_settings

    try:
        it = _client().get("/api/brief").json()["topics"][0]["items"][0]
        assert it["developing"] is False
    finally:
        get_settings.cache_clear()


# -- FR13: the developing badge can finally name what changed ----------------------
# A developing item carries prior_digest — the digest as it read on first_seen day,
# verbatim bytes already on disk (no new generative surface). Matched by the same
# identity keys that made it developing, so the lookup can't disagree with the badge.


def test_brief_developing_item_carries_the_first_seen_digest_verbatim(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "dev_prior")
    day1 = _dev_item("DeepSeek eyes IPO", "https://techcrunch.com/deepseek-ipo",
                     digest="DeepSeek is exploring a Hong Kong listing.")
    day2 = _dev_item("DeepSeek: what the IPO means", "https://techcrunch.com/deepseek-ipo",
                     digest="Bankers named; the listing now targets Q4.")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day1]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day2]})})
    from app.config import get_settings

    try:
        it = _client().get("/api/brief").json()["topics"][0]["items"][0]
        assert it["developing"] is True
        assert it["first_seen"] == "2026-07-13"
        assert it["prior_digest"] == "DeepSeek is exploring a Hong Kong listing."
    finally:
        get_settings.cache_clear()


def test_brief_prior_digest_absent_when_the_first_appearance_had_none(tmp_path, monkeypatch):
    """The label must never overpromise: developing stays set, prior_digest stays null
    when the first appearance carried an empty digest — nothing verbatim to show."""
    sweeps = _env(tmp_path, monkeypatch, "dev_prior_empty")
    day1 = _dev_item("Quiet first sighting", "https://example.com/q", digest="")
    day2 = _dev_item("Quiet first sighting", "https://example.com/q", digest="Now with substance.")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day1]})})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps({"top_line": "t", "items": [day2]})})
    from app.config import get_settings

    try:
        it = _client().get("/api/brief").json()["topics"][0]["items"][0]
        assert it["developing"] is True
        assert it.get("prior_digest") is None
    finally:
        get_settings.cache_clear()


# -- audio brief (M4) -------------------------------------------------------------
# The mp3 is written by the sweep pipeline (sweeps/audio_brief.py), never the backend —
# these tests plant the file directly and only exercise the read path.


def test_brief_audio_available_flag_flips_with_mp3(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "audioflag")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        assert _client().get("/api/brief").json()["audio_available"] is False
        (sweeps / "2026-07-14" / "brief.mp3").write_bytes(b"\xff\xfbfake-mp3-bytes")
        assert _client().get("/api/brief").json()["audio_available"] is True
    finally:
        get_settings.cache_clear()


def test_brief_audio_serves_the_latest_days_mp3(tmp_path, monkeypatch):
    """Two days, both with audio — the endpoint streams the served (newest) day's bytes."""
    sweeps = _env(tmp_path, monkeypatch, "audiolatest")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (sweeps / "2026-07-13" / "brief.mp3").write_bytes(b"OLD-DAY-AUDIO")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (sweeps / "2026-07-14" / "brief.mp3").write_bytes(b"NEW-DAY-AUDIO")
    from app.config import get_settings

    try:
        r = _client().get("/api/brief/audio")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("audio/mpeg")
        assert r.content == b"NEW-DAY-AUDIO"
    finally:
        get_settings.cache_clear()


def test_brief_audio_404_never_serves_a_stale_days_mp3(tmp_path, monkeypatch):
    """Audio exists only for an OLDER day: the flag stays off and the endpoint 404s —
    yesterday's narration must never play over today's brief."""
    sweeps = _env(tmp_path, monkeypatch, "audiostale")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (sweeps / "2026-07-13" / "brief.mp3").write_bytes(b"YESTERDAY")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        assert _client().get("/api/brief").json()["audio_available"] is False
        assert _client().get("/api/brief/audio").status_code == 404
    finally:
        get_settings.cache_clear()


def test_brief_audio_404_when_no_sweeps_exist(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, "audionone")
    from app.config import get_settings

    try:
        assert _client().get("/api/brief/audio").status_code == 404
    finally:
        get_settings.cache_clear()


# -- newest-dir servability: an in-progress/failed day must not hide a good brief ---
# (P1 bug #1, docs/bug-hunt/2026-07-19-post-m7.md — sweep.sh mkdir-p's the day folder
# minutes before the first topic lands, and a fully failed sweep leaves only .raw.txt.)


def test_brief_empty_newest_dir_serves_prior_day(tmp_path, monkeypatch):
    """During the wake window (day dir created, no topic landed yet) yesterday's
    complete brief must keep serving instead of an empty has_data=false page."""
    sweeps = _env(tmp_path, monkeypatch, "emptynewest")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (sweeps / "2026-07-14").mkdir()
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["date"] == "2026-07-13"
        assert body["has_data"] is True
        assert body["topics"][0]["slug"] == "ai-llms"
    finally:
        get_settings.cache_clear()


def test_brief_all_failed_newest_dir_serves_prior_day(tmp_path, monkeypatch):
    """A day where every topic failed validation (only .raw.txt) is unservable — it
    must not hide the previous complete brief for the rest of the day."""
    sweeps = _env(tmp_path, monkeypatch, "failednewest")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    _write_day(sweeps, "2026-07-14", {"ai-llms.raw.txt": "unvalidated model output"})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["date"] == "2026-07-13"
        assert body["has_data"] is True
    finally:
        get_settings.cache_clear()


def test_brief_audio_follows_served_day_past_empty_newest_dir(tmp_path, monkeypatch):
    """Audio tracks the served day: when the empty newest dir is skipped, the flag and
    the stream both come from the day actually on the page."""
    sweeps = _env(tmp_path, monkeypatch, "audiofollow")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (sweeps / "2026-07-13" / "brief.mp3").write_bytes(b"SERVED-DAY-AUDIO")
    (sweeps / "2026-07-14").mkdir()
    from app.config import get_settings

    try:
        assert _client().get("/api/brief").json()["audio_available"] is True
        r = _client().get("/api/brief/audio")
        assert r.status_code == 200
        assert r.content == b"SERVED-DAY-AUDIO"
    finally:
        get_settings.cache_clear()


# -- missing-topic honesty (QU12): a topic that didn't run is named, not just absent ---
# (docs/ideas/topic-didnt-run-banner.md — server-side diff of the active roster against
# the slugs that produced a renderable file for the served day. Complements P1 bug #1:
# that fix covers the whole-day case, this covers the per-topic one.)


def test_brief_reports_missing_active_topics(tmp_path, monkeypatch):
    """Active roster topics with no renderable file for the served day land in
    missing_topics (roster order, roster titles); a topic that produced ANY renderable
    file — even a legacy .md fallback — is present, not missing."""
    sweeps = _env(tmp_path, monkeypatch, "missing")
    _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "market-tech-news.md": LEGACY_MD.replace("fantasy-football", "market-tech-news"),
        },
    )
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is True
        assert body["missing_topics"] == [
            {"slug": "fantasy-football", "title": "Fantasy football"}
        ]
    finally:
        get_settings.cache_clear()


def test_brief_missing_excludes_paused_topics(tmp_path, monkeypatch):
    """A paused roster entry that produced nothing is a legitimate absence, never a
    'didn't run' — the pause flag is the exclusion predicate."""
    roster = [
        {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
        {"slug": "st-louis-blues", "title": "St. Louis Blues", "paused": True},
    ]
    sweeps = _env(tmp_path, monkeypatch, "missingpaused", roster=roster)
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        assert _client().get("/api/brief").json()["missing_topics"] == []
    finally:
        get_settings.cache_clear()


def test_brief_missing_empty_when_every_active_topic_ran(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "missingnone")
    _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "fantasy-football.json": json.dumps({**VALID_BRIEF, "topic": "fantasy-football"}),
            "market-tech-news.json": json.dumps({**VALID_BRIEF, "topic": "market-tech-news"}),
        },
    )
    from app.config import get_settings

    try:
        assert _client().get("/api/brief").json()["missing_topics"] == []
    finally:
        get_settings.cache_clear()


def test_brief_missing_includes_raw_txt_only_topic(tmp_path, monkeypatch):
    """A topic whose sweep failed validation (only .raw.txt on disk) produced nothing
    renderable — it must be named as missing, not silently vanish from the page."""
    sweeps = _env(tmp_path, monkeypatch, "missingraw")
    _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "fantasy-football.raw.txt": "unvalidated model output",
            "market-tech-news.json": json.dumps({**VALID_BRIEF, "topic": "market-tech-news"}),
        },
    )
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["missing_topics"] == [
            {"slug": "fantasy-football", "title": "Fantasy football"}
        ]
    finally:
        get_settings.cache_clear()


def test_brief_missing_empty_when_no_sweeps_at_all(tmp_path, monkeypatch):
    """No servable day → the page-level has_data=false state already tells the story;
    per-topic missing chatter would be noise on top of it."""
    _env(tmp_path, monkeypatch, "missingnodata")
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is False
        assert body["missing_topics"] == []
    finally:
        get_settings.cache_clear()


# -- FR4 audio chapters -----------------------------------------------------------
# sweeps/audio_brief.py writes brief.chapters.json (word-count seek offsets) beside the
# mp3; /api/brief surfaces it so the page can render chapter chips. Chips are a bonus:
# they can never break the morning read, and they only ride an actually-present mp3.

CHAPTERS = [
    {"slug": "ai-llms", "title": "AI / LLMs", "start_seconds": 5.0},
    {"slug": "fantasy-football", "title": "Fantasy football", "start_seconds": 95.5},
]


def test_brief_serves_audio_chapters_beside_the_mp3(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "chapters")
    day = _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (day / "brief.mp3").write_bytes(b"\xff\xfbfake")
    (day / "brief.chapters.json").write_text(json.dumps(CHAPTERS), encoding="utf-8")
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["audio_available"] is True
        assert body["audio_chapters"] == CHAPTERS
    finally:
        get_settings.cache_clear()


def test_brief_without_chapters_file_serves_empty_list(tmp_path, monkeypatch):
    """A pre-FR4 day: mp3 but no chapters file — player yes, chips no, never a 500."""
    sweeps = _env(tmp_path, monkeypatch, "nochapters")
    day = _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (day / "brief.mp3").write_bytes(b"\xff\xfbfake")
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["audio_available"] is True
        assert body["audio_chapters"] == []
    finally:
        get_settings.cache_clear()


def test_brief_mangled_chapters_degrade_to_empty(tmp_path, monkeypatch):
    """Garbage json → []; a wrong-shape entry is filtered while the good one survives."""
    sweeps = _env(tmp_path, monkeypatch, "badchapters")
    day = _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (day / "brief.mp3").write_bytes(b"\xff\xfbfake")
    (day / "brief.chapters.json").write_text("{{{ not json", encoding="utf-8")
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["audio_available"] is True
        assert body["audio_chapters"] == []

        mixed = [
            {"slug": "x"},  # no title/start — dropped
            {"slug": "ok", "title": "OK", "start_seconds": "soon"},  # non-numeric — dropped
            CHAPTERS[0],
        ]
        (day / "brief.chapters.json").write_text(json.dumps(mixed), encoding="utf-8")
        body = _client().get("/api/brief").json()
        assert body["audio_chapters"] == [CHAPTERS[0]]
    finally:
        get_settings.cache_clear()


def test_brief_chapters_without_mp3_stay_hidden(tmp_path, monkeypatch):
    """A failed Kokoro render leaves chapters beside no mp3 (written before the render by
    design) — the API must treat the pair as absent, not advertise seeks into nothing."""
    sweeps = _env(tmp_path, monkeypatch, "orphanchapters")
    day = _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (day / "brief.chapters.json").write_text(json.dumps(CHAPTERS), encoding="utf-8")
    from app.config import get_settings

    try:
        body = _client().get("/api/brief").json()
        assert body["audio_available"] is False
        assert body["audio_chapters"] == []
    finally:
        get_settings.cache_clear()


# -- QU1: yesterday's brief, one tap back ------------------------------------------
# ?date= opens the never-pruned data/sweeps/<date>/ archive the design always promised
# was the durable record — read-only time travel; no param keeps today's behavior byte
# for byte, plus prev/next neighbors so the history is walkable.


def test_brief_serves_an_archived_day_with_notes_joined_and_neighbors(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "archive")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        old = client.get("/api/brief?date=2026-07-13").json()
        assert old["date"] == "2026-07-13"
        assert old["has_data"] is True
        assert old["prev_date"] is None
        assert old["next_date"] == "2026-07-14"
        # A note attached to the archived morning joins onto its item there…
        item_id = old["topics"][0]["items"][0]["id"]
        r = client.post(
            "/api/brief/notes",
            json={
                "item_id": item_id,
                "topic_slug": "ai-llms",
                "brief_date": "2026-07-13",
                "item_headline": "OpenAI lifts caps",
                "body": "archived thought",
            },
        )
        assert r.status_code == 200
        old = client.get("/api/brief?date=2026-07-13").json()
        assert old["topics"][0]["items"][0]["notes"][0]["body"] == "archived thought"
        # …and today's payload names its prev neighbor (no param → behavior unchanged).
        today = client.get("/api/brief").json()
        assert today["date"] == "2026-07-14"
        assert today["prev_date"] == "2026-07-13"
        assert today["next_date"] is None
    finally:
        get_settings.cache_clear()


def test_brief_unknown_or_garbage_date_is_a_404(tmp_path, monkeypatch):
    """The link promised an archived morning; a day with nothing renderable (or nonsense
    in the param) gets an honest 404, never a silent fall-back to today."""
    sweeps = _env(tmp_path, monkeypatch, "archive404")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        assert client.get("/api/brief?date=2026-07-01").status_code == 404
        assert client.get("/api/brief?date=not-a-date").status_code == 404
    finally:
        get_settings.cache_clear()


def test_brief_archived_day_hides_audio_even_when_its_mp3_exists(tmp_path, monkeypatch):
    """No historical audio in v1: GET /brief/audio only serves the latest day, so an
    archived payload advertising a player would be a broken promise."""
    sweeps = _env(tmp_path, monkeypatch, "archiveaudio")
    day = _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (day / "brief.mp3").write_bytes(b"\xff\xfbold")
    (day / "brief.chapters.json").write_text(json.dumps(CHAPTERS), encoding="utf-8")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        body = _client().get("/api/brief?date=2026-07-13").json()
        assert body["date"] == "2026-07-13"
        assert body["audio_available"] is False
        assert body["audio_chapters"] == []
    finally:
        get_settings.cache_clear()
