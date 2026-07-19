"""P1 bug #4 (docs/bug-hunt/2026-07-19-post-m7.md): ``activity.day`` must be the LOCAL
calendar day, mirroring ``brief_visits`` (store/schema.py documents the 7pm-CDT hazard) —
sqlite's ``date('now')`` and ``now_utc()[:10]`` file an evening Chicago session under
tomorrow's UTC day, breaking streaks.

The far-TZ fixture pins ``TZ`` (process-wide, restored after) to a zone where the local
calendar day is guaranteed to differ from the UTC day *right now*, so these tests are
deterministic at any wall-clock hour on any machine — a day-bucketing bug can't hide
behind a machine sitting near UTC. The SM-2/attempt TIMESTAMPS must stay naive UTC
(interval arithmetic depends on it); only the day bucket is local, and that boundary is
pinned here too.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.store.db import (
    add_custom_topic,
    init_db,
    record_attempt,
    record_flashcard_review,
    save_reflection,
    set_course_assessment,
    set_episode_listened,
    set_lesson_completed,
    update_custom_topic,
)


@pytest.fixture
def far_tz():
    """Pin TZ so the local calendar day != the UTC calendar day for this test.

    Etc/GMT zone signs are POSIX-inverted: Etc/GMT-14 == UTC+14. From 10:00 UTC on,
    UTC+14 is already tomorrow; before 10:00 UTC, UTC-11 is still yesterday.
    """
    old = os.environ.get("TZ")
    os.environ["TZ"] = "Etc/GMT-14" if datetime.now(timezone.utc).hour >= 10 else "Etc/GMT+11"
    time.tzset()
    yield
    if old is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = old
    time.tzset()


def _db(tmp_path) -> Path:
    db = tmp_path / "store.sqlite"
    init_db(db_path=db)
    return db


def _local_today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _activity(db: Path) -> list:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT day, kind FROM activity ORDER BY rowid").fetchall()
    finally:
        conn.close()


def test_raw_sql_activity_writers_bucket_on_local_day(far_tz, tmp_path):
    """Every raw-SQL activity writer files under the local day, not sqlite's UTC now."""
    db = _db(tmp_path)
    before = _local_today()
    topic = add_custom_topic("Rust", db_path=db)
    update_custom_topic(topic["id"], notes="n", db_path=db)
    set_episode_listened("nb1", "ep1", True, db_path=db)
    save_reflection("nb1", "solid episode", db_path=db)
    set_lesson_completed("course-x", "l1", True, db_path=db)
    set_course_assessment("course-x", "m/cap.md", 4, {"scope": "met"}, "ok", db_path=db)
    after = _local_today()

    rows = _activity(db)
    assert len(rows) == 6
    for r in rows:
        assert r["day"] in {before, after}, (
            f"{r['kind']} filed under {r['day']} — expected the local day {before}"
        )


def test_record_attempt_files_activity_local_but_timestamps_utc(far_tz, tmp_path):
    """The activity bucket goes local; the attempt/SM-2 timestamps stay naive UTC."""
    db = _db(tmp_path)
    before_local, before_utc = _local_today(), _utc_today()
    record_attempt(
        "nb1",
        "quiz1",
        score=1,
        total=1,
        answers=[
            {
                "question_index": 0,
                "question_key": "q1",
                "chosen_index": 0,
                "correct": True,
                "used_hint": False,
            }
        ],
        db_path=db,
    )
    after_local, after_utc = _local_today(), _utc_today()

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        day = conn.execute(
            "SELECT day FROM activity WHERE kind = 'quiz_attempt'"
        ).fetchone()["day"]
        finished = conn.execute("SELECT finished_at FROM attempts").fetchone()["finished_at"]
        reviewed = conn.execute(
            "SELECT last_review_at FROM question_mastery"
        ).fetchone()["last_review_at"]
    finally:
        conn.close()

    assert day in {before_local, after_local}
    assert finished[:10] in {before_utc, after_utc}  # attempt timestamp stays UTC
    assert reviewed[:10] in {before_utc, after_utc}  # SM-2 timestamp stays UTC
    assert day != finished[:10]  # under the far TZ the two calendars must disagree


def test_flashcard_review_files_activity_local_but_sm2_utc(far_tz, tmp_path):
    db = _db(tmp_path)
    before_local, before_utc = _local_today(), _utc_today()
    state = record_flashcard_review(
        "course-x", "materials/deck.json", "c1", "good", db_path=db
    )
    after_local, after_utc = _local_today(), _utc_today()

    rows = _activity(db)
    assert [r["kind"] for r in rows] == ["flashcard_review"]
    assert rows[0]["day"] in {before_local, after_local}
    assert state["last_review_at"][:10] in {before_utc, after_utc}
    assert rows[0]["day"] != state["last_review_at"][:10]


def test_progress_streak_agrees_with_local_days_end_to_end(far_tz, tmp_path, monkeypatch):
    """Yesterday-local + today-local practice reads as a 2-day current streak.

    Today's row goes through a real writer and yesterday's is seeded as the fixed
    writers file it; the /api/progress reader's "today" must be on the same local
    calendar — a UTC leak on either side breaks the pair under the far TZ."""
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("NOTEBOOKLM_ROOT", str(tmp_path / "empty-nbs"))
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        init_db()
        set_lesson_completed("course-x", "l1", True)  # today's practice
        yesterday = (datetime.now().astimezone().date() - timedelta(days=1)).isoformat()
        conn = sqlite3.connect(str(get_settings().db_path))
        try:
            conn.execute(
                "INSERT INTO activity (day, notebook_id, kind) VALUES (?, NULL, 'quiz_attempt')",
                (yesterday,),
            )
            conn.commit()
        finally:
            conn.close()

        from fastapi.testclient import TestClient

        from app.main import app

        body = TestClient(app).get("/api/progress").json()
        assert body["summary"]["current_streak"] == 2
    finally:
        get_settings.cache_clear()
