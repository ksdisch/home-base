"""Phase-6 schema migration: a v2 store gains the SM-2 columns without losing its rows.

The migration is additive ``ALTER TABLE ADD COLUMN`` guarded to be idempotent, so it must work
on (a) a legacy v2 store, (b) a fresh store, and (c) a re-run — all verified here. Also verified:
(d) the poisoned-ledger case (BACKLOG "migration ledger hardening", 2026-07-16 incident) — a
``schema_migrations`` row must not stop ``init_db`` from healing a table whose migrated columns
were lost to a drop/recreate outside the app.
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


def test_poisoned_ledger_still_heals_missing_columns(tmp_path):
    """The 2026-07-16 incident: ledger says v3 applied, but the table lost the SM-2 columns.

    ``question_mastery`` was dropped/recreated in its pre-v3 shape outside the app while
    ``schema_migrations`` kept the v3 row, and the ledger-gated ``init_db`` skipped the ALTERs —
    every SM-2 surface 500'd. ``init_db`` must trust the table's real shape over the ledger.
    """
    db = tmp_path / "poisoned.sqlite"
    init_db(db)  # healthy store: full schema, ledger records v3

    conn = sqlite3.connect(str(db))
    try:
        conn.execute("DROP TABLE question_mastery")
        conn.execute(_V2_QUESTION_MASTERY)  # recreated in the old shape; ledger untouched
        conn.execute(
            "INSERT INTO question_mastery "
            "(notebook_id, quiz_artifact_id, question_key, score, miss_count, last_review_at) "
            "VALUES ('nb', 'qz', 'k1', 0.5, 2, '2026-07-01 10:00:00')"
        )
        conn.commit()
        versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    finally:
        conn.close()
    # Preconditions = the incident state: ledger still claims v3, columns actually gone.
    assert 3 in versions
    assert not (_SR_COLUMNS & _columns(db, "question_mastery"))

    init_db(db)

    assert _SR_COLUMNS <= _columns(db, "question_mastery")  # healed despite the ledger
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT score, miss_count, ease, interval_days, reps, lapses, due_at "
            "FROM question_mastery WHERE question_key = 'k1'"
        ).fetchone()
    finally:
        conn.close()
    # The row written while the table was in its old shape survives the heal, defaults filled.
    assert row["score"] == 0.5
    assert row["miss_count"] == 2
    assert row["ease"] == 2.5
    assert row["reps"] == 0
    assert row["due_at"] is None


def test_unknown_ledger_versions_are_harmless(tmp_path):
    """A ledger row with no matching migration (hand-inserted, or from a newer schema) must
    neither crash ``init_db`` nor block the real migrations from keeping the store healthy."""
    db = tmp_path / "orphan.sqlite"
    init_db(db)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("INSERT INTO schema_migrations (version) VALUES (99)")
        conn.commit()
    finally:
        conn.close()

    init_db(db)  # must not raise

    assert _SR_COLUMNS <= _columns(db, "question_mastery")
    conn = connect(db)
    try:
        versions = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    finally:
        conn.close()
    assert {3, 99} <= versions  # 99 preserved as a record; 3 recorded normally
