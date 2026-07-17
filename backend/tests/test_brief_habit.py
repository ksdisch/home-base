"""GET /api/brief/habit + brief_habit_weeks — the v1 success-check instrumentation.

The kickoff's ~3-weeks-in criteria (≥5 mornings/week on the visit log, ≥3 notes/week) read
from ``brief_visits`` (day = LOCAL calendar day, by contract of ``record_brief_visit``) and
``brief_notes`` (created_at = sqlite UTC). Verified here: Monday-start local-week bucketing,
distinct-day morning counts, zero-filled windows, clamping, malformed-row tolerance, and the
API wiring.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.store.db import brief_habit_weeks, init_db

# A fixed local "now": Thursday 2026-07-16 → current week starts Monday 2026-07-13, and a
# 4-week window covers Mondays 06-22 · 06-29 · 07-06 · 07-13.
NOW = datetime(2026, 7, 16, 9, 30)


def _seed(db: Path, *, visits: list[str] = (), note_created_ats: list[str] = ()) -> None:
    conn = sqlite3.connect(str(db))
    try:
        for day in visits:
            conn.execute(
                "INSERT INTO brief_visits (day, visited_at) VALUES (?, ?)", (day, day + "T07:00:00")
            )
        for ts in note_created_ats:
            conn.execute(
                "INSERT INTO brief_notes (item_id, topic_slug, brief_date, item_headline, body, "
                "created_at) VALUES ('abc123def456', 'ai-llms', '2026-07-15', 'h', 'note', ?)",
                (ts,),
            )
        conn.commit()
    finally:
        conn.close()


def test_week_bucketing_distinct_days_and_window(tmp_path):
    db = tmp_path / "habit.sqlite"
    init_db(db)
    _seed(
        db,
        # This week: 3 distinct days (07-14 visited twice — one morning, not two). Last week:
        # 2 days. 06-01 is outside the 4-week window and must not appear anywhere.
        visits=[
            "2026-07-13", "2026-07-14", "2026-07-14", "2026-07-15",
            "2026-07-07", "2026-07-09",
            "2026-06-01",
            "garbage",  # hand-edited junk row: skipped, never a 500
        ],
        # Wednesday-noon UTC stamps stay inside their local Mon-start week in any timezone.
        note_created_ats=[
            "2026-07-15 12:00:00", "2026-07-15 12:05:00",
            "2026-07-08 12:00:00",
            "not-a-timestamp",  # skipped
        ],
    )

    weeks = brief_habit_weeks(4, now=NOW, db_path=db)

    assert [w["week_start"] for w in weeks] == [
        "2026-06-22", "2026-06-29", "2026-07-06", "2026-07-13"
    ]  # oldest first, current week last
    assert weeks[3] == {"week_start": "2026-07-13", "mornings": 3, "notes": 2}
    assert weeks[2] == {"week_start": "2026-07-06", "mornings": 2, "notes": 1}
    # Empty weeks are zero-filled, present, and untouched by the out-of-window 06-01 visit.
    assert weeks[0] == {"week_start": "2026-06-22", "mornings": 0, "notes": 0}
    assert weeks[1] == {"week_start": "2026-06-29", "mornings": 0, "notes": 0}


def test_weeks_clamped_and_empty_store_zero_fills(tmp_path):
    db = tmp_path / "empty.sqlite"
    init_db(db)

    assert len(brief_habit_weeks(0, now=NOW, db_path=db)) == 1  # floor
    capped = brief_habit_weeks(99, now=NOW, db_path=db)  # ceiling
    assert len(capped) == 12
    assert all(w["mornings"] == 0 and w["notes"] == 0 for w in capped)
    # Monday-start contract holds across the whole window.
    assert capped[-1]["week_start"] == "2026-07-13"
    assert capped[0]["week_start"] == "2026-04-27"


def test_habit_endpoint_wires_store_to_response(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from app.config import get_settings
    from app.store import add_brief_note, init_db as init_default, record_brief_visit

    get_settings.cache_clear()
    try:
        init_default()
        record_brief_visit()  # today, local — lands in the current (last) week
        add_brief_note(
            item_id="abc123def456",
            topic_slug="ai-llms",
            brief_date="2026-07-15",
            item_headline="h",
            body="a note",
        )

        from fastapi.testclient import TestClient

        from app.main import app

        body = TestClient(app).get("/api/brief/habit").json()

        assert body["generated_at"]
        assert len(body["weeks"]) == 4  # default window
        current = body["weeks"][-1]
        assert current["mornings"] >= 1
        assert current["notes"] >= 1
        # Every entry is a real Monday (weekday 0) — the strip can trust the axis.
        for w in body["weeks"]:
            assert datetime.strptime(w["week_start"], "%Y-%m-%d").weekday() == 0
    finally:
        get_settings.cache_clear()
