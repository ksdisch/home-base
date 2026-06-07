"""Phase-6 schema migration: a v2 store gains the SM-2 columns without losing its rows.

The migration is additive ``ALTER TABLE ADD COLUMN`` guarded to be idempotent, so it must work
on (a) a legacy v2 store, (b) a fresh store, and (c) a re-run — all verified here.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.store.db import connect, init_db


def _columns(db: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


# A pre-Phase-6 question_mastery table (no SM-2 columns), as a v2 store would have on disk.
_V2_QUESTION_MASTERY = """
CREATE TABLE question_mastery (
    notebook_id      TEXT NOT NULL,
    quiz_artifact_id TEXT NOT NULL,
    question_key     TEXT NOT NULL,
    score            REAL NOT NULL DEFAULT 0,
    miss_count       INTEGER NOT NULL DEFAULT 0,
    last_review_at   TEXT,
    PRIMARY KEY (notebook_id, quiz_artifact_id, question_key)
)
"""

_SR_COLUMNS = {"ease", "interval_days", "reps", "lapses", "due_at"}


def _make_v2_store(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO schema_migrations (version) VALUES (2)")
        conn.execute(_V2_QUESTION_MASTERY)
        conn.execute(
            "INSERT INTO question_mastery "
            "(notebook_id, quiz_artifact_id, question_key, score, miss_count, last_review_at) "
            "VALUES ('nb', 'qz', 'k1', 0.5, 2, '2026-05-01 10:00:00')"
        )
        conn.commit()
    finally:
        conn.close()


def test_v2_store_upgrades_and_keeps_rows(tmp_path):
    db = tmp_path / "v2.sqlite"
    _make_v2_store(db)
    assert not (_SR_COLUMNS & _columns(db, "question_mastery"))  # precondition: no SR cols yet

    init_db(db)

    cols = _columns(db, "question_mastery")
    assert _SR_COLUMNS <= cols  # all SM-2 columns added

    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT score, miss_count, ease, interval_days, reps, lapses, due_at "
            "FROM question_mastery WHERE question_key = 'k1'"
        ).fetchone()
        versions = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    finally:
        conn.close()

    # The legacy row survived; new columns took their defaults.
    assert row["score"] == 0.5
    assert row["miss_count"] == 2
    assert row["ease"] == 2.5
    assert row["interval_days"] == 0
    assert row["reps"] == 0
    assert row["lapses"] == 0
    assert row["due_at"] is None
    assert {2, 3} <= versions  # migration recorded


def test_fresh_store_has_sr_columns_and_is_reentrant(tmp_path):
    db = tmp_path / "fresh.sqlite"
    init_db(db)  # fresh DB gets the columns straight from STATEMENTS
    assert _SR_COLUMNS <= _columns(db, "question_mastery")
    # Re-running init_db must be a clean no-op (idempotent ALTERs).
    init_db(db)
    assert _SR_COLUMNS <= _columns(db, "question_mastery")
