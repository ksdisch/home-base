"""Thin stdlib ``sqlite3`` access layer. Dependency-free; one connection per call."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Optional

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
