"""Thin stdlib ``sqlite3`` access layer. Dependency-free; one connection per call."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..config import get_settings
from . import scheduler
from .schema import MIGRATIONS, SCHEMA_VERSION, STATEMENTS


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _safe_alter(conn: sqlite3.Connection, stmt: str) -> None:
    """Run an additive ``ALTER TABLE ADD COLUMN``, treating "already there" as success.

    Fresh DBs already have the column (it's in STATEMENTS), so the ALTER would raise a duplicate-
    column error — that's the idempotent no-op case, not a failure. Anything else re-raises.
    """
    try:
        conn.execute(stmt)
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise


def init_db(db_path: Optional[Path] = None) -> None:
    conn = connect(db_path)
    try:
        for stmt in STATEMENTS:
            conn.execute(stmt)
        # Apply forward migrations not yet recorded for this store (idempotent ALTERs).
        applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        for version in sorted(MIGRATIONS):
            if version in applied:
                continue
            for alter in MIGRATIONS[version]:
                _safe_alter(conn, alter)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)", (version,)
            )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    finally:
        conn.close()


def set_episode_listened(
    notebook_id: str, artifact_id: str, listened: bool, db_path: Optional[Path] = None
) -> bool:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO episode_progress (notebook_id, artifact_id, listened, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(notebook_id, artifact_id)
            DO UPDATE SET listened = excluded.listened, updated_at = datetime('now')
            """,
            (notebook_id, artifact_id, 1 if listened else 0),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now'), ?, ?)",
            (notebook_id, "episode_listened" if listened else "episode_unlistened"),
        )
        conn.commit()
    finally:
        conn.close()
    return listened


def save_reflection(
    notebook_id: str,
    body: str,
    *,
    episode_artifact_id: Optional[str] = None,
    grasp_rating: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist a post-episode reflection (+ an activity row for streaks). Returns its id."""
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO reflections (notebook_id, episode_artifact_id, body, grasp_rating)
            VALUES (?, ?, ?, ?)
            """,
            (notebook_id, episode_artifact_id, body, grasp_rating),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now'), ?, ?)",
            (notebook_id, "reflection"),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_reflections(
    notebook_id: Optional[str] = None,
    *,
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Most-recent-first reflections (optionally for one notebook).

    The `/episode-review` skill *writes* these via :func:`save_reflection`; until Phase 6 nothing
    read them back. This is that read path — newest first, capped by ``limit``.
    """
    limit = max(1, min(500, int(limit)))
    conn = connect(db_path)
    try:
        if notebook_id is not None:
            rows = conn.execute(
                "SELECT id, notebook_id, episode_artifact_id, body, grasp_rating, created_at "
                "FROM reflections WHERE notebook_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (notebook_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, notebook_id, episode_artifact_id, body, grasp_rating, created_at "
                "FROM reflections ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": int(r["id"]),
            "notebook_id": r["notebook_id"],
            "episode_artifact_id": r["episode_artifact_id"],
            "body": r["body"],
            "grasp_rating": r["grasp_rating"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def record_attempt(
    notebook_id: str,
    quiz_artifact_id: str,
    *,
    score: int,
    total: int,
    answers: List[Mapping[str, Any]],
    episode_artifact_id: Optional[str] = None,
    mark_listened: bool = False,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist a graded quiz attempt and the raw signal the mastery engines read.

    ``answers`` is one mapping per question with keys: ``question_index`` (int),
    ``question_key`` (str|None — stable per-question identity for mastery), ``chosen_index``
    (int|None), ``correct`` (bool), ``used_hint`` (bool).

    Writes ``attempts`` + ``attempt_answers``, the per-question/topic mastery signal (latest
    score + ``last_review_at`` + miss counts that Phase 4's topic decay ranks on) **and** the
    per-question SM-2 state (ease/interval/reps/lapses/``due_at``) that Phase 6's scheduler
    advances, and an ``activity`` row. If ``mark_listened`` and an ``episode_artifact_id`` is
    given, also marks that episode listened in the same transaction. ``now`` is injected for
    deterministic SM-2 scheduling (defaults to UTC now). Returns the attempt id.
    """
    now_dt = now or scheduler.now_utc()
    now_str = scheduler.fmt_ts(now_dt)
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO attempts (notebook_id, quiz_artifact_id, finished_at, score, total)
            VALUES (?, ?, datetime('now'), ?, ?)
            """,
            (notebook_id, quiz_artifact_id, score, total),
        )
        attempt_id = int(cur.lastrowid)

        for a in answers:
            correct = bool(a["correct"])
            used_hint = bool(a.get("used_hint"))
            conn.execute(
                """
                INSERT INTO attempt_answers
                    (attempt_id, question_index, question_key, chosen_index, correct, used_hint)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    int(a["question_index"]),
                    a.get("question_key"),
                    a.get("chosen_index"),
                    1 if correct else 0,
                    1 if used_hint else 0,
                ),
            )
            qkey = a.get("question_key")
            if qkey is not None:
                # Raw mastery signal: clean-correct=1.0, hinted-correct=0.5, miss=0.0.
                qscore = (0.5 if used_hint else 1.0) if correct else 0.0
                miss = 0 if correct else 1
                # Advance this question's SM-2 state off whatever it was before.
                prev = conn.execute(
                    "SELECT ease, interval_days, reps, lapses FROM question_mastery "
                    "WHERE notebook_id = ? AND quiz_artifact_id = ? AND question_key = ?",
                    (notebook_id, quiz_artifact_id, qkey),
                ).fetchone()
                state = scheduler.next_state(
                    ease=prev["ease"] if prev else scheduler.INITIAL_EASE,
                    interval_days=prev["interval_days"] if prev else 0.0,
                    reps=prev["reps"] if prev else 0,
                    lapses=prev["lapses"] if prev else 0,
                    quality=scheduler.quality_from_signal(correct, used_hint),
                    now=now_dt,
                )
                conn.execute(
                    """
                    INSERT INTO question_mastery
                        (notebook_id, quiz_artifact_id, question_key, score, miss_count,
                         last_review_at, ease, interval_days, reps, lapses, due_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(notebook_id, quiz_artifact_id, question_key)
                    DO UPDATE SET score = excluded.score,
                                  miss_count = question_mastery.miss_count + ?,
                                  last_review_at = excluded.last_review_at,
                                  ease = excluded.ease,
                                  interval_days = excluded.interval_days,
                                  reps = excluded.reps,
                                  lapses = excluded.lapses,
                                  due_at = excluded.due_at
                    """,
                    (
                        notebook_id, quiz_artifact_id, qkey, qscore, miss, now_str,
                        state.ease, state.interval_days, state.reps, state.lapses,
                        scheduler.fmt_ts(state.due_at), miss,
                    ),
                )

        frac = (score / total) if total else 0.0
        conn.execute(
            """
            INSERT INTO topic_mastery (notebook_id, score, last_review_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(notebook_id)
            DO UPDATE SET score = excluded.score, last_review_at = datetime('now')
            """,
            (notebook_id, frac),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now'), ?, ?)",
            (notebook_id, "quiz_attempt"),
        )

        if mark_listened and episode_artifact_id:
            conn.execute(
                """
                INSERT INTO episode_progress (notebook_id, artifact_id, listened, updated_at)
                VALUES (?, ?, 1, datetime('now'))
                ON CONFLICT(notebook_id, artifact_id)
                DO UPDATE SET listened = 1, updated_at = datetime('now')
                """,
                (notebook_id, episode_artifact_id),
            )
            conn.execute(
                "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now'), ?, ?)",
                (notebook_id, "episode_listened"),
            )

        conn.commit()
        return attempt_id
    finally:
        conn.close()


def get_episode_progress(notebook_id: str, db_path: Optional[Path] = None) -> Dict[str, bool]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT artifact_id, listened FROM episode_progress WHERE notebook_id = ?",
            (notebook_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["artifact_id"]: bool(r["listened"]) for r in rows}


# -- custom topics -------------------------------------------------------------
# Non-NotebookLM interests (a book, a YouTube series, a loose thread) tracked loosely with
# manual progress + notes. The first writer for the Phase-5 ``custom_topics`` table; like all
# hub state it lives here in SQLite, never in the NotebookLM sidecars.

def _row_to_topic(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "title": r["title"],
        "notes": r["notes"],
        "progress_pct": int(r["progress_pct"]),
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def _validate_progress(progress_pct: int) -> int:
    if not isinstance(progress_pct, int) or isinstance(progress_pct, bool):
        raise ValueError("progress_pct must be an integer")
    if not 0 <= progress_pct <= 100:
        raise ValueError("progress_pct must be between 0 and 100")
    return progress_pct


def add_custom_topic(
    title: str,
    *,
    notes: str = "",
    progress_pct: int = 0,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a custom topic (+ an activity row for streaks). Returns the new row as a dict."""
    if not title or not title.strip():
        raise ValueError("title must be a non-empty string")
    _validate_progress(progress_pct)
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO custom_topics (title, notes, progress_pct) VALUES (?, ?, ?)",
            (title.strip(), notes, progress_pct),
        )
        topic_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now'), NULL, ?)",
            ("custom_topic_added",),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM custom_topics WHERE id = ?", (topic_id,)
        ).fetchone()
        return _row_to_topic(row)
    finally:
        conn.close()


def list_custom_topics(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM custom_topics ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_topic(r) for r in rows]


def get_custom_topic(
    topic_id: int, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM custom_topics WHERE id = ?", (topic_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_topic(row) if row else None


def update_custom_topic(
    topic_id: int,
    *,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    progress_pct: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Patch the provided fields (+ an activity row if anything changed). Returns the updated
    row, or ``None`` if no topic has that id. A call with nothing to change is a no-op that
    returns the current row."""
    sets: List[str] = []
    params: List[Any] = []
    if title is not None:
        if not title.strip():
            raise ValueError("title must be a non-empty string")
        sets.append("title = ?")
        params.append(title.strip())
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    if progress_pct is not None:
        _validate_progress(progress_pct)
        sets.append("progress_pct = ?")
        params.append(progress_pct)

    if not sets:  # nothing to change — return current row (None if it doesn't exist)
        return get_custom_topic(topic_id, db_path)

    sets.append("updated_at = datetime('now')")
    conn = connect(db_path)
    try:
        cur = conn.execute(
            f"UPDATE custom_topics SET {', '.join(sets)} WHERE id = ?",
            (*params, topic_id),
        )
        if cur.rowcount == 0:  # no such topic
            conn.rollback()
            return None
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now'), NULL, ?)",
            ("custom_topic_updated",),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM custom_topics WHERE id = ?", (topic_id,)
        ).fetchone()
        return _row_to_topic(row)
    finally:
        conn.close()
