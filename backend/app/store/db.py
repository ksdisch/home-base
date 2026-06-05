"""Thin stdlib ``sqlite3`` access layer. Dependency-free; one connection per call."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..config import get_settings
from .schema import SCHEMA_VERSION, STATEMENTS


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    conn = connect(db_path)
    try:
        for stmt in STATEMENTS:
            conn.execute(stmt)
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


def record_attempt(
    notebook_id: str,
    quiz_artifact_id: str,
    *,
    score: int,
    total: int,
    answers: List[Mapping[str, Any]],
    episode_artifact_id: Optional[str] = None,
    mark_listened: bool = False,
    db_path: Optional[Path] = None,
) -> int:
    """Persist a graded quiz attempt and the raw signal the Phase-4 mastery engine reads.

    ``answers`` is one mapping per question with keys: ``question_index`` (int),
    ``question_key`` (str|None — stable per-question identity for mastery), ``chosen_index``
    (int|None), ``correct`` (bool), ``used_hint`` (bool).

    Writes ``attempts`` + ``attempt_answers``, a raw per-question/topic mastery signal
    (latest score + ``last_review_at`` + miss counts — the decay/ranking is Phase 4's job,
    not ours), and an ``activity`` row. If ``mark_listened`` and an ``episode_artifact_id`` is
    given, also marks that episode listened in the same transaction. Returns the attempt id.
    """
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
                conn.execute(
                    """
                    INSERT INTO question_mastery
                        (notebook_id, quiz_artifact_id, question_key, score, miss_count,
                         last_review_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(notebook_id, quiz_artifact_id, question_key)
                    DO UPDATE SET score = excluded.score,
                                  miss_count = question_mastery.miss_count + ?,
                                  last_review_at = datetime('now')
                    """,
                    (notebook_id, quiz_artifact_id, qkey, qscore, miss, miss),
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
