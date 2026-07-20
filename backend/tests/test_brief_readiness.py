"""Readiness v0 (docs/ideas/readiness-brief.md) — the 'Coming up' forward projection.

The strip inverts the brief's tense: a deterministic, read-time projection of which of
today's stories are still in motion, computed from the same prior-day sweep JSON the M3
developing badge walks. House rules under test: identity is the badge's own normalized
headline/source-URL match (strip and badge can never disagree); an honest insufficient
state below two prior renderable mornings (a badge may exist off one prior day — the
strip still abstains); fresh items are never projected; a garbled history file degrades
to fewer matches, never a failure; the strip rides only the LIVE brief.
"""

import json

TODAY = "2026-07-16"  # served date is a pure string — no clock in the projection

ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "celtics", "title": "Boston Celtics", "paused": False},
    {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False},
]


def _env(tmp_path, monkeypatch, name: str):
    """Fresh store + sweeps dir + synthetic roster file, isolated under tmp_path."""
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    roster_file = tmp_path / name / "topics.json"
    roster_file.write_text(json.dumps(ROSTER), encoding="utf-8")
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("ROSTER_FILE", str(roster_file))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    return sweeps


def _teardown():
    from app.config import get_settings

    get_settings.cache_clear()


def _write_day(sweeps, day: str, slug: str, items: list[tuple[str, str]]) -> None:
    """One valid <slug>.json for ``day``; items are (headline, source_url) pairs."""
    d = sweeps / day
    d.mkdir(exist_ok=True)
    payload = {
        "topic": slug,
        "date": day,
        "as_of": f"{day} 07:05 CDT",
        "top_line": "Top line.",
        "context_note": None,
        "items": [
            {
                "headline": headline,
                "attribution": "Source, July 2026",
                "digest": f"digest of {headline}",
                "why_it_matters": "w",
                "sources": [{"title": "S", "url": url}],
            }
            for headline, url in items
        ],
    }
    (d / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")


def _build(sweeps, date: str = TODAY):
    from app.sweeps import build_readiness, load_brief_topics

    topics = load_brief_topics(sweeps, date, ROSTER)
    return build_readiness(sweeps, date, topics), topics


# -- the projection ------------------------------------------------------------


def test_readiness_projects_multiday_trajectories(tmp_path, monkeypatch):
    """The full read: a story seen 3 of the last mornings outranks one seen 2; identity
    matches by headline OR source URL (the badge's own keys, so item_id/first_seen agree
    with the annotated items); a fresh item is never projected."""
    sweeps = _env(tmp_path, monkeypatch, "full")
    try:
        # 07-13 renderable but unrelated; the caps story runs 07-14, 07-15, today.
        _write_day(sweeps, "2026-07-13", "ai-llms", [("Old unrelated", "https://x.com/old")])
        _write_day(sweeps, "2026-07-14", "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        _write_day(sweeps, "2026-07-15", "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        # The Tatum story matches yesterday by URL only — different headline.
        _write_day(sweeps, "2026-07-15", "celtics", [("Tatum contract chatter", "https://x.com/b")])
        _write_day(
            sweeps,
            TODAY,
            "ai-llms",
            [("OpenAI lifts caps", "https://x.com/a"), ("Brand new thing", "https://x.com/f")],
        )
        _write_day(sweeps, TODAY, "celtics", [("Tatum extension talks", "https://x.com/b")])

        r, topics = _build(sweeps)

        assert r["generated_at"]
        assert r["window_days"] == 7
        assert r["history_days"] == 3
        assert r["sufficient"] is True
        assert [(i["slug"], i["headline"], i["days_seen"], i["first_seen"]) for i in r["items"]] == [
            ("ai-llms", "OpenAI lifts caps", 3, "2026-07-14"),
            ("celtics", "Tatum extension talks", 2, "2026-07-15"),
        ]
        assert [i["title"] for i in r["items"]] == ["AI / LLMs", "Boston Celtics"]
        # item_id is the served day's read-time anchor — the annotated item's own id.
        by_slug = {t["slug"]: t for t in topics}
        caps = next(
            i for i in by_slug["ai-llms"]["items"] if i["headline"] == "OpenAI lifts caps"
        )
        assert r["items"][0]["item_id"] == caps["id"]
    finally:
        _teardown()


def test_readiness_ranking_prefers_days_then_density_then_slug(tmp_path, monkeypatch):
    """Ties break honestly and deterministically: equal days_seen ranks the denser streak
    (later first_seen) first, and a full tie falls back to slug order."""
    sweeps = _env(tmp_path, monkeypatch, "rank")
    try:
        # celtics: seen yesterday (dense 2-day streak). ai-llms + chiefs: seen once six
        # days ago (sparse), identical shape → full tie broken by slug.
        _write_day(sweeps, "2026-07-10", "ai-llms", [("Sparse alpha", "https://x.com/sa")])
        _write_day(sweeps, "2026-07-10", "chiefs", [("Sparse kansas", "https://x.com/sk")])
        _write_day(sweeps, "2026-07-15", "celtics", [("Dense boston", "https://x.com/db")])
        _write_day(sweeps, TODAY, "ai-llms", [("Sparse alpha", "https://x.com/sa")])
        _write_day(sweeps, TODAY, "chiefs", [("Sparse kansas", "https://x.com/sk")])
        _write_day(sweeps, TODAY, "celtics", [("Dense boston", "https://x.com/db")])

        r, _ = _build(sweeps)

        assert [(i["slug"], i["days_seen"], i["first_seen"]) for i in r["items"]] == [
            ("celtics", 2, "2026-07-15"),
            ("ai-llms", 2, "2026-07-10"),
            ("chiefs", 2, "2026-07-10"),
        ]
    finally:
        _teardown()


def test_readiness_caps_at_five(tmp_path, monkeypatch):
    """Six qualifying trajectories render the top five — the strip is a rehearsal, not a
    second feed. Full ties within one topic fall back to headline order."""
    sweeps = _env(tmp_path, monkeypatch, "cap")
    try:
        stories = [
            ("Alpha", "https://x.com/1"),
            ("Bravo", "https://x.com/2"),
            ("Charlie", "https://x.com/3"),
            ("Delta", "https://x.com/4"),
            ("Echo", "https://x.com/5"),
            ("Foxtrot", "https://x.com/6"),
        ]
        _write_day(sweeps, "2026-07-14", "ai-llms", stories)
        _write_day(sweeps, "2026-07-15", "ai-llms", [("Filler", "https://x.com/f")])
        _write_day(sweeps, TODAY, "ai-llms", stories)

        r, _ = _build(sweeps)

        assert [i["headline"] for i in r["items"]] == [
            "Alpha",
            "Bravo",
            "Charlie",
            "Delta",
            "Echo",
        ]
    finally:
        _teardown()


def test_readiness_cold_start_is_honest(tmp_path, monkeypatch):
    """Below two prior renderable mornings nothing is projected — even when a developing
    badge legitimately exists off a single prior day, the strip abstains and history_days
    says why (never a trend invented from one morning of archive)."""
    sweeps = _env(tmp_path, monkeypatch, "cold")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        r, _ = _build(sweeps)
        assert r["sufficient"] is False
        assert r["history_days"] == 0
        assert r["items"] == []

        _write_day(sweeps, "2026-07-15", "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        r, topics = _build(sweeps)
        # The badge fires off one prior day — the strip still abstains.
        assert topics[0]["items"][0]["developing"] is True
        assert r["sufficient"] is False
        assert r["history_days"] == 1
        assert r["items"] == []
    finally:
        _teardown()


def test_readiness_quiet_day_carries_no_items(tmp_path, monkeypatch):
    """Enough history but nothing multi-day in motion → sufficient with an empty list
    (the honest quiet morning), and a raw-markdown fallback topic is tolerated."""
    sweeps = _env(tmp_path, monkeypatch, "quiet")
    try:
        _write_day(sweeps, "2026-07-14", "ai-llms", [("Gone story", "https://x.com/g")])
        _write_day(sweeps, "2026-07-15", "ai-llms", [("Other gone", "https://x.com/o")])
        _write_day(sweeps, TODAY, "ai-llms", [("Brand new thing", "https://x.com/n")])
        # An md-only topic for the served day — no items key on its fallback dict.
        (sweeps / TODAY / "celtics.md").write_text(
            f"# celtics — as of {TODAY} 07:05 CDT\nLegacy body.", encoding="utf-8"
        )

        r, _ = _build(sweeps)

        assert r["sufficient"] is True
        assert r["history_days"] == 2
        assert r["items"] == []
    finally:
        _teardown()


def test_readiness_unreadable_history_degrades_to_fewer_matches(tmp_path, monkeypatch):
    """A garbled prior-day file still counts as a morning (renderability is the archive's
    bar) but contributes no matches — fewer days_seen, never an exception."""
    sweeps = _env(tmp_path, monkeypatch, "degrade")
    try:
        _write_day(sweeps, "2026-07-14", "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        day = sweeps / "2026-07-15"
        day.mkdir()
        (day / "ai-llms.json").write_text("{not json", encoding="utf-8")
        _write_day(sweeps, TODAY, "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])

        r, _ = _build(sweeps)

        assert r["sufficient"] is True
        assert r["history_days"] == 2
        assert [(i["days_seen"], i["first_seen"]) for i in r["items"]] == [(2, "2026-07-14")]
    finally:
        _teardown()


# -- API wiring ----------------------------------------------------------------


def test_brief_carries_readiness_on_the_live_view_only(tmp_path, monkeypatch):
    """GET /api/brief (no ?date=) carries the projection for the served morning; a ?date=
    archive view never wears it (the projection is a now-thing, not part of the record)."""
    sweeps = _env(tmp_path, monkeypatch, "api")
    try:
        _write_day(sweeps, "2026-07-14", "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        _write_day(sweeps, "2026-07-15", "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])
        _write_day(sweeps, TODAY, "ai-llms", [("OpenAI lifts caps", "https://x.com/a")])

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        body = client.get("/api/brief").json()
        assert body["readiness"] is not None
        assert body["readiness"]["sufficient"] is True
        assert body["readiness"]["window_days"] == 7
        assert [i["headline"] for i in body["readiness"]["items"]] == ["OpenAI lifts caps"]

        archived = client.get("/api/brief", params={"date": "2026-07-15"}).json()
        assert archived["readiness"] is None
    finally:
        _teardown()


def test_brief_without_a_served_day_carries_no_readiness(tmp_path, monkeypatch):
    """An empty archive has no morning to project for — has_data is false and the field
    stays None (the page-level no-sweeps story, not a cold-start strip)."""
    _env(tmp_path, monkeypatch, "empty")
    try:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        body = client.get("/api/brief").json()
        assert body["has_data"] is False
        assert body["readiness"] is None
    finally:
        _teardown()
