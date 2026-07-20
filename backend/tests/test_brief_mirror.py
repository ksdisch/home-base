"""Mirror v0 (docs/ideas/the-mirror.md) — the 'You this week' strip's read-time aggregator.

The Mirror inverts the telescope: a deterministic reflection of the last 7 LOCAL days of
Kyle's own logged behavior — brief_visits + brief_notes + news_events (SQLite), the
brief-chat.jsonl ledger, and the roster's pause flags. House rules under test: no LLM and
no writes; an honest insufficient state below the signal floor (never a pattern fabricated
from three data points); a broken source zeroes that source, never a 500; the strip rides
only the LIVE brief (an archived ?date= payload carries no mirror).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

# A fixed "now": Thursday 2026-07-16 → the 7-day window is 07-10..07-16. Seeded UTC
# timestamps sit at noon mid-window, so their local day stays in-window in any timezone
# (the habit suite's trick).
NOW = datetime(2026, 7, 16, 9, 30)

ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "celtics", "title": "Boston Celtics", "paused": True},
    {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False},
]

# Renderable single-topic brief for the ?date= archive pin (test_brief_api's shape).
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


def _env(tmp_path, monkeypatch, name: str, roster=ROSTER):
    """Fresh store + sweeps dir + synthetic roster file, isolated under tmp_path."""
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


def _teardown():
    from app.config import get_settings

    get_settings.cache_clear()


def _seed(
    *,
    visits: list[str] = (),
    notes: list[tuple[str, str]] = (),  # (topic_slug, created_at UTC)
    news: list[tuple[str, str]] = (),  # (category_slug, created_at UTC)
) -> None:
    from app.config import get_settings

    conn = sqlite3.connect(str(get_settings().db_path))
    try:
        for day in visits:
            conn.execute(
                "INSERT INTO brief_visits (day, visited_at) VALUES (?, ?)",
                (day, day + "T07:00:00"),
            )
        for slug, ts in notes:
            conn.execute(
                "INSERT INTO brief_notes (item_id, topic_slug, brief_date, item_headline, "
                "body, created_at) VALUES ('abc123def456', ?, '2026-07-14', 'h', 'note', ?)",
                (slug, ts),
            )
        for slug, ts in news:
            conn.execute(
                "INSERT INTO news_events (kind, category_slug, item_id, headline, source, "
                "url, created_at) VALUES ('click', ?, 'i1', 'h', 's', 'u', ?)",
                (slug, ts),
            )
        conn.commit()
    finally:
        conn.close()


def _write_ledger(lines: list[str]) -> None:
    from app.config import get_settings

    path = get_settings().brief_chat_ledger
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ask_row(ts: str, topic: str = "ai-llms") -> str:
    return json.dumps(
        {"ts": ts, "brief_date": "2026-07-14", "topic": topic, "item_id": "abc123def456",
         "model": "sonnet", "is_error": False}
    )


# -- the aggregator ------------------------------------------------------------


def test_mirror_counts_window_attention_and_sentence(tmp_path, monkeypatch):
    """The full read: distinct in-window mornings, local-day bucketing across all four
    sources, the capped attention split over every keyed signal, one templated sentence,
    and the roster's paused titles. Garbage rows/lines are skipped, never a crash."""
    _env(tmp_path, monkeypatch, "full")
    try:
        _seed(
            # 2 distinct in-window days (07-14 twice = one morning); 07-01 out; junk skipped.
            visits=["2026-07-15", "2026-07-14", "2026-07-14", "2026-07-01", "garbage"],
            notes=[
                ("ai-llms", "2026-07-14 12:00:00"),
                ("ai-llms", "2026-07-15 12:00:00"),
                ("celtics", "2026-07-13 12:00:00"),
                ("ai-llms", "2026-07-01 12:00:00"),  # outside the window
                ("ai-llms", "nope"),  # unreadable timestamp: skipped
            ],
            news=[
                ("local", "2026-07-13 12:00:00"),
                ("local", "2026-07-14 12:00:00"),
                ("local", "2026-07-15 12:00:00"),
                ("uplifting", "2026-07-13 12:00:00"),
                ("local", "2026-06-30 12:00:00"),  # outside the window
            ],
        )
        _write_ledger(
            [
                _ask_row("2026-07-14T12:00:00Z"),
                _ask_row("2026-07-15T12:00:00Z"),
                _ask_row("2026-07-01T12:00:00Z"),  # outside the window
                "not json at all",  # skipped
                json.dumps({"topic": "ai-llms"}),  # no ts: skipped
            ]
        )

        from app.config import get_settings
        from app.mirror import build_mirror

        m = build_mirror(get_settings(), ROSTER, now=NOW)

        assert m.generated_at
        assert m.window_days == 7
        assert m.mornings == 2
        assert m.notes == 3
        assert m.asks == 2
        assert m.news_events == 4
        assert m.sufficient is True
        # Attention: ai-llms 4 (2 notes + 2 asks) · local 3 · celtics/uplifting tied at 1
        # (slug order breaks the tie) — capped at 3 slices, shares out of ALL 9 keyed events.
        assert [(a.slug, a.title, a.events, a.share_pct) for a in m.attention] == [
            ("ai-llms", "AI / LLMs", 4, 44),
            ("local", "Local", 3, 33),
            ("celtics", "Boston Celtics", 1, 11),
        ]
        assert m.paused_topics == ["Boston Celtics"]
        assert m.sentence == (
            "You showed up 2 of the last 7 mornings, left 3 notes, and asked 2 questions "
            "— attention leaned 44% AI / LLMs."
        )
    finally:
        _teardown()


def test_mirror_cold_start_is_honest(tmp_path, monkeypatch):
    """An empty store renders the insufficient state — zero counts, no sentence, and
    nothing extrapolated (idea-doc open question 1, answered: never fabricate)."""
    _env(tmp_path, monkeypatch, "cold")
    try:
        from app.config import get_settings
        from app.mirror import build_mirror

        m = build_mirror(get_settings(), ROSTER, now=NOW)

        assert m.sufficient is False
        assert m.sentence == ""
        assert (m.mornings, m.notes, m.asks, m.news_events) == (0, 0, 0, 0)
        assert m.attention == []
    finally:
        _teardown()


def test_mirror_signal_floor_and_singular_wording(tmp_path, monkeypatch):
    """4 total signals sit below the floor; the 5th flips sufficient — and the sentence
    handles singulars ('left 1 note') and a single-source 100% attention lean."""
    _env(tmp_path, monkeypatch, "floor")
    try:
        from app.config import get_settings
        from app.mirror import build_mirror

        _seed(visits=["2026-07-12", "2026-07-13", "2026-07-14", "2026-07-15"])
        below = build_mirror(get_settings(), ROSTER, now=NOW)
        assert below.mornings == 4
        assert below.sufficient is False and below.sentence == ""

        _seed(notes=[("ai-llms", "2026-07-14 12:00:00")])
        at = build_mirror(get_settings(), ROSTER, now=NOW)
        assert at.sufficient is True
        assert at.sentence == (
            "You showed up 4 of the last 7 mornings, left 1 note, and asked 0 questions "
            "— attention leaned 100% AI / LLMs."
        )
    finally:
        _teardown()


def test_mirror_sentence_without_attention(tmp_path, monkeypatch):
    """Visits carry no topic key — a sufficient week of pure mornings ends the sentence
    without an attention clause instead of inventing a lean."""
    _env(tmp_path, monkeypatch, "plain")
    try:
        from app.config import get_settings
        from app.mirror import build_mirror

        _seed(visits=["2026-07-11", "2026-07-12", "2026-07-13", "2026-07-14", "2026-07-15"])
        m = build_mirror(get_settings(), ROSTER, now=NOW)

        assert m.sufficient is True and m.attention == []
        assert m.sentence == (
            "You showed up 5 of the last 7 mornings, left 0 notes, and asked 0 questions."
        )
    finally:
        _teardown()


def test_mirror_unreadable_ledger_zeroes_asks_only(tmp_path, monkeypatch):
    """The ledger path existing as a DIRECTORY (open() raises) must zero the asks source
    and leave every other count live — a broken source never breaks the mirror."""
    _env(tmp_path, monkeypatch, "brokenledger")
    try:
        from app.config import get_settings
        from app.mirror import build_mirror

        get_settings().brief_chat_ledger.mkdir(parents=True, exist_ok=True)
        _seed(
            visits=["2026-07-13", "2026-07-14", "2026-07-15"],
            notes=[("ai-llms", "2026-07-14 12:00:00"), ("ai-llms", "2026-07-15 12:00:00")],
        )
        m = build_mirror(get_settings(), ROSTER, now=NOW)

        assert m.asks == 0
        assert m.mornings == 3 and m.notes == 2
        assert m.sufficient is True  # 5 signals without the ledger
    finally:
        _teardown()


# -- API wiring ----------------------------------------------------------------


def test_brief_carries_the_mirror_on_the_live_view(tmp_path, monkeypatch):
    """GET /api/brief (no ?date=) always carries a mirror — honest-insufficient on an
    empty store, sufficient once a week of signal exists (relative seeding, real now)."""
    _env(tmp_path, monkeypatch, "api")
    try:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        body = client.get("/api/brief").json()
        assert body["mirror"] is not None
        assert body["mirror"]["sufficient"] is False
        assert body["mirror"]["window_days"] == 7

        today = date.today()
        _seed(visits=[(today - timedelta(days=i)).isoformat() for i in range(5)])
        body = client.get("/api/brief").json()
        assert body["mirror"]["sufficient"] is True
        assert body["mirror"]["mornings"] == 5
        assert body["mirror"]["sentence"].startswith("You showed up 5")
    finally:
        _teardown()


def test_archived_date_view_carries_no_mirror(tmp_path, monkeypatch):
    """?date= serves the never-pruned archive — a historical morning must not carry
    today's live self-read (the strip is a now-thing, not part of the record)."""
    sweeps = _env(tmp_path, monkeypatch, "archive")
    try:
        day = sweeps / "2026-07-14"
        day.mkdir()
        (day / "ai-llms.json").write_text(json.dumps(VALID_BRIEF), encoding="utf-8")

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        assert client.get("/api/brief").json()["mirror"] is not None
        assert client.get("/api/brief", params={"date": "2026-07-14"}).json()["mirror"] is None
    finally:
        _teardown()
