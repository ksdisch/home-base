"""SQLite schema. Phase 1 only writes ``episode_progress`` + ``activity``, but the schema is
shaped now so the later mastery-decay + spaced-repetition engine has a concrete home:
per-topic and per-question mastery scores with a ``last_review_at`` to fade against an injected
clock, feeding a deterministic "Review next" queue. None of that is implemented yet."""

from __future__ import annotations

SCHEMA_VERSION = 2

# Each statement is applied idempotently (IF NOT EXISTS) on startup.
STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version    INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Manual "I listened to this episode" checkbox. (No NotebookLM listening API exists.)
    """
    CREATE TABLE IF NOT EXISTS episode_progress (
        notebook_id TEXT NOT NULL,
        artifact_id TEXT NOT NULL,
        listened    INTEGER NOT NULL DEFAULT 0,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (notebook_id, artifact_id)
    )
    """,
    # Quiz attempts (Phase 2 writes these; schema present now).
    """
    CREATE TABLE IF NOT EXISTS attempts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        notebook_id      TEXT NOT NULL,
        quiz_artifact_id TEXT NOT NULL,
        started_at       TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at      TEXT,
        score            INTEGER,
        total            INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attempt_answers (
        attempt_id     INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
        question_index INTEGER NOT NULL,
        question_key   TEXT,
        chosen_index   INTEGER,
        correct        INTEGER NOT NULL DEFAULT 0,
        used_hint      INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (attempt_id, question_index)
    )
    """,
    # Post-episode reflections (the `/episode-review` skill's "how well did it land?" step).
    # Saved-and-resurfaced so they can feed the future "Review next" / study-planner work.
    """
    CREATE TABLE IF NOT EXISTS reflections (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        notebook_id         TEXT NOT NULL,
        episode_artifact_id TEXT,
        body                TEXT NOT NULL DEFAULT '',
        grasp_rating        INTEGER,
        created_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Free-form notes per notebook.
    """
    CREATE TABLE IF NOT EXISTS notes (
        notebook_id TEXT PRIMARY KEY,
        body        TEXT NOT NULL DEFAULT '',
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Non-NotebookLM custom topics (Phase 5).
    """
    CREATE TABLE IF NOT EXISTS custom_topics (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        title        TEXT NOT NULL,
        notes        TEXT NOT NULL DEFAULT '',
        progress_pct INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # Mastery that decays over time-since-last-review (Phase 4 scoring fn reads these).
    """
    CREATE TABLE IF NOT EXISTS topic_mastery (
        notebook_id    TEXT PRIMARY KEY,
        score          REAL NOT NULL DEFAULT 0,
        last_review_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_mastery (
        notebook_id      TEXT NOT NULL,
        quiz_artifact_id TEXT NOT NULL,
        question_key     TEXT NOT NULL,
        score            REAL NOT NULL DEFAULT 0,
        miss_count       INTEGER NOT NULL DEFAULT 0,
        last_review_at   TEXT,
        PRIMARY KEY (notebook_id, quiz_artifact_id, question_key)
    )
    """,
    # Daily activity rollup -> streaks.
    """
    CREATE TABLE IF NOT EXISTS activity (
        day         TEXT NOT NULL,
        notebook_id TEXT,
        kind        TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]
