"""SQLite schema. Phase 1 only writes ``episode_progress`` + ``activity``, but the schema is
shaped now so the later mastery-decay + spaced-repetition engine has a concrete home:
per-topic and per-question mastery scores with a ``last_review_at`` to fade against an injected
clock, feeding a deterministic "Review next" queue. None of that is implemented yet."""

from __future__ import annotations

SCHEMA_VERSION = 5

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
    # Phase 6 adds the per-item SM-2 columns (ease/interval/reps/lapses/due_at). Fresh DBs get
    # them here; existing v2 stores get them via the ALTER migration below.
    """
    CREATE TABLE IF NOT EXISTS question_mastery (
        notebook_id      TEXT NOT NULL,
        quiz_artifact_id TEXT NOT NULL,
        question_key     TEXT NOT NULL,
        score            REAL NOT NULL DEFAULT 0,
        miss_count       INTEGER NOT NULL DEFAULT 0,
        last_review_at   TEXT,
        ease             REAL NOT NULL DEFAULT 2.5,
        interval_days    REAL NOT NULL DEFAULT 0,
        reps             INTEGER NOT NULL DEFAULT 0,
        lapses           INTEGER NOT NULL DEFAULT 0,
        due_at           TEXT,
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
    # M1: one row per Today-page load — the kickoff's habit metric ("opened ≥5 mornings/week"
    # = distinct days). `day` is the LOCAL calendar day, written by the app (sqlite's
    # datetime('now') is UTC, which would file a 7pm CDT visit under tomorrow). v4 adds this
    # table; being a plain CREATE IF NOT EXISTS it needs no ALTER migration entry.
    """
    CREATE TABLE IF NOT EXISTS brief_visits (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        day        TEXT NOT NULL,
        visited_at TEXT NOT NULL
    )
    """,
    # Phase 6: per-lesson "I finished this lesson" checkbox for generated courses. Course
    # *content* lives on disk (a course sidecar: course.json + material files); only progress
    # lives here — mirrors how ``episode_progress`` tracks NotebookLM episodes. Course progress %
    # is derived from these rows against the manifest's lesson count.
    """
    CREATE TABLE IF NOT EXISTS course_lesson_progress (
        course_slug TEXT NOT NULL,
        lesson_id   TEXT NOT NULL,
        completed   INTEGER NOT NULL DEFAULT 0,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (course_slug, lesson_id)
    )
    """,
    # M2: inline notes on brief items. ``item_id`` is the read-time anchor derived in
    # ``app.sweeps`` (sha1(date|slug|headline)[:12]); topic_slug/brief_date/item_headline
    # snapshot what was annotated because data/sweeps is gitignored + regenerable — a note
    # must stay meaningful after its brief file is re-swept or gone. Deliberately NOT an
    # ``activity`` row: activity feeds learning streaks (same reasoning as brief_visits).
    # v5 adds this table; a plain CREATE IF NOT EXISTS needs no ALTER migration entry.
    """
    CREATE TABLE IF NOT EXISTS brief_notes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id       TEXT NOT NULL,
        topic_slug    TEXT NOT NULL,
        brief_date    TEXT NOT NULL,
        item_headline TEXT NOT NULL,
        body          TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]

# Forward migrations for stores created before a given SCHEMA_VERSION. Each value is a list of
# additive ``ALTER TABLE`` statements applied in order when upgrading *past* that version. They
# run idempotently — :func:`app.store.db.init_db` ignores "duplicate column" so a fresh DB (which
# already has the columns from STATEMENTS) and a re-run are both safe.
MIGRATIONS = {
    3: [
        "ALTER TABLE question_mastery ADD COLUMN ease REAL NOT NULL DEFAULT 2.5",
        "ALTER TABLE question_mastery ADD COLUMN interval_days REAL NOT NULL DEFAULT 0",
        "ALTER TABLE question_mastery ADD COLUMN reps INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE question_mastery ADD COLUMN lapses INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE question_mastery ADD COLUMN due_at TEXT",
    ],
}
