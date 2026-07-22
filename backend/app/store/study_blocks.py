"""app.store.study_blocks — the Study Scheduler's opt-in flag + removable block ledger (v0).

Same content-on-disk / progress-in-SQLite split as ``path_step_progress``: the path sidecar stays
read-only; the per-track opt-in and the calendar blocks the scheduler wrote live in SQLite. Every
block records its Google ``event_id`` + ``calendar_id`` so it is cleanly removable — the feature's
one hard rule. ``track_kind`` is 'path' in v0; the shared ordered-step engine lets a 'course' opt
in later with no schema change. Every function takes an optional ``db_path`` so tests point at a
throwaway store (the house pattern)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .db import connect

DEFAULT_SESSION_MINUTES = 45

_BLOCK_COLUMNS = (
    "id",
    "track_kind",
    "track_id",
    "step_id",
    "calendar_id",
    "event_id",
    "title",
    "start_at",
    "end_at",
    "status",
    "created_at",
    "removed_at",
)
_COLS = ", ".join(_BLOCK_COLUMNS)


def get_study_opt_in(
    track_kind: str, track_id: str, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """The opt-in state for a track — ``{enabled, session_minutes}``. No row → opted out at the
    default session length (the honest default: scheduling is off until Kyle turns it on)."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT enabled, session_minutes FROM study_opt_in WHERE track_kind = ? AND track_id = ?",
            (track_kind, track_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"enabled": False, "session_minutes": DEFAULT_SESSION_MINUTES}
    return {"enabled": bool(row["enabled"]), "session_minutes": int(row["session_minutes"])}


def set_study_opt_in(
    track_kind: str,
    track_id: str,
    enabled: bool,
    session_minutes: int,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Upsert the opt-in flag + session length for a track (one row per track, never duplicated)."""
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO study_opt_in (track_kind, track_id, enabled, session_minutes, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(track_kind, track_id)
            DO UPDATE SET enabled = excluded.enabled,
                          session_minutes = excluded.session_minutes,
                          updated_at = datetime('now')
            """,
            (track_kind, track_id, 1 if enabled else 0, int(session_minutes)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"enabled": bool(enabled), "session_minutes": int(session_minutes)}


def _row(r: Any) -> Dict[str, Any]:
    return {k: r[k] for k in _BLOCK_COLUMNS}


def add_study_blocks(
    track_kind: str,
    track_id: str,
    blocks: Sequence[Mapping[str, Any]],
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Record the batch of blocks the scheduler just WROTE to the calendar (status 'written').
    Each block carries its Google ``event_id`` + ``calendar_id`` so it stays removable. Returns the
    inserted rows (with ids), ordered by start_at."""
    conn = connect(db_path)
    ids: List[int] = []
    try:
        for b in blocks:
            cur = conn.execute(
                """
                INSERT INTO study_blocks
                    (track_kind, track_id, step_id, calendar_id, event_id, title, start_at, end_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_kind,
                    track_id,
                    b["step_id"],
                    b["calendar_id"],
                    b["event_id"],
                    b["title"],
                    b["start_at"],
                    b["end_at"],
                ),
            )
            ids.append(int(cur.lastrowid))
        conn.commit()
        rows = (
            conn.execute(
                f"SELECT {_COLS} FROM study_blocks "
                f"WHERE id IN ({','.join('?' * len(ids))}) ORDER BY start_at, id",
                ids,
            ).fetchall()
            if ids
            else []
        )
    finally:
        conn.close()
    return [_row(r) for r in rows]


def list_study_blocks(
    track_kind: str,
    track_id: str,
    include_removed: bool = False,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """The track's blocks, chronological. Live ('written') only by default; ``include_removed``
    returns the full audit ledger (removed rows keep their event_id for the record)."""
    q = f"SELECT {_COLS} FROM study_blocks WHERE track_kind = ? AND track_id = ?"
    if not include_removed:
        q += " AND status = 'written'"
    q += " ORDER BY start_at, id"
    conn = connect(db_path)
    try:
        rows = conn.execute(q, (track_kind, track_id)).fetchall()
    finally:
        conn.close()
    return [_row(r) for r in rows]


def mark_study_blocks_removed(
    track_kind: str,
    track_id: str,
    block_ids: Optional[Sequence[int]] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Flip live blocks to 'removed' (stamping ``removed_at``) after their calendar events are
    deleted — ``block_ids`` targets a subset, ``None`` removes every live block for the track. Only
    'written' rows flip, so re-removing is a no-op. Returns how many rows changed."""
    conn = connect(db_path)
    try:
        if block_ids is None:
            cur = conn.execute(
                "UPDATE study_blocks SET status = 'removed', removed_at = datetime('now') "
                "WHERE track_kind = ? AND track_id = ? AND status = 'written'",
                (track_kind, track_id),
            )
        else:
            ids = [int(i) for i in block_ids]
            if not ids:
                return 0
            cur = conn.execute(
                "UPDATE study_blocks SET status = 'removed', removed_at = datetime('now') "
                f"WHERE track_kind = ? AND track_id = ? AND status = 'written' "
                f"AND id IN ({','.join('?' * len(ids))})",
                [track_kind, track_id, *ids],
            )
        n = int(cur.rowcount)
        conn.commit()
    finally:
        conn.close()
    return n
