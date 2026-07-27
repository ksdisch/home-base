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
    "step_ids",
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


def _days_to_csv(days: Optional[Sequence[int]]) -> Optional[str]:
    """A day-of-week list -> a stable CSV column value; None (all days) stays NULL."""
    if not days:
        return None
    return ",".join(str(int(d)) for d in days)


def _days_from_csv(value: Any) -> Optional[List[int]]:
    """The CSV column -> a list of weekday ints, or None when unset/blank."""
    if not value:
        return None
    out = [int(p) for p in str(value).split(",") if p.strip() != ""]
    return out or None


def get_study_opt_in(
    track_kind: str, track_id: str, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """The opt-in state + persisted window prefs for a track. No row → opted out at the default
    session length with every window pref unset (None) — the honest default: scheduling is off, and
    the planner uses its own defaults, until Kyle sets things."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT enabled, session_minutes, day_start_hour, day_end_hour, days_of_week, max_blocks "
            "FROM study_opt_in WHERE track_kind = ? AND track_id = ?",
            (track_kind, track_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {
            "enabled": False,
            "session_minutes": DEFAULT_SESSION_MINUTES,
            "day_start_hour": None,
            "day_end_hour": None,
            "days_of_week": None,
            "max_blocks": None,
        }
    return {
        "enabled": bool(row["enabled"]),
        "session_minutes": int(row["session_minutes"]),
        "day_start_hour": row["day_start_hour"] if row["day_start_hour"] is None else int(row["day_start_hour"]),
        "day_end_hour": row["day_end_hour"] if row["day_end_hour"] is None else int(row["day_end_hour"]),
        "days_of_week": _days_from_csv(row["days_of_week"]),
        "max_blocks": row["max_blocks"] if row["max_blocks"] is None else int(row["max_blocks"]),
    }


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


def set_study_prefs(
    track_kind: str,
    track_id: str,
    *,
    session_minutes: int,
    day_start_hour: Optional[int],
    day_end_hour: Optional[int],
    days_of_week: Optional[Sequence[int]],
    max_blocks: Optional[int],
    db_path: Optional[Path] = None,
) -> None:
    """Persist the learner's scheduler window prefs (session length + time-of-day + days-of-week +
    max blocks) for a track. Upserts the pref columns only — the ``enabled`` flag is left alone (a
    fresh insert takes its column default of 0; an existing opt-in survives), so saving prefs never
    silently turns scheduling on or off. ``days_of_week=None``/empty clears the restriction."""
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO study_opt_in
                (track_kind, track_id, session_minutes, day_start_hour, day_end_hour, days_of_week,
                 max_blocks, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(track_kind, track_id)
            DO UPDATE SET session_minutes = excluded.session_minutes,
                          day_start_hour  = excluded.day_start_hour,
                          day_end_hour    = excluded.day_end_hour,
                          days_of_week    = excluded.days_of_week,
                          max_blocks      = excluded.max_blocks,
                          updated_at      = datetime('now')
            """,
            (
                track_kind,
                track_id,
                int(session_minutes),
                None if day_start_hour is None else int(day_start_hour),
                None if day_end_hour is None else int(day_end_hour),
                _days_to_csv(days_of_week),
                None if max_blocks is None else int(max_blocks),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _row(r: Any) -> Dict[str, Any]:
    out = {k: r[k] for k in _BLOCK_COLUMNS}
    # ``step_ids`` is the full set a block covers; pre-v13 rows only recorded the first one.
    out["step_ids"] = _steps_from_csv(out.get("step_ids")) or ([out["step_id"]] if out["step_id"] else [])
    return out


def _steps_to_csv(step_ids: Optional[Sequence[str]]) -> Optional[str]:
    """The step-id list -> a stable CSV column value; empty stays NULL."""
    ids = [str(s) for s in (step_ids or []) if str(s)]
    return ",".join(ids) or None


def _steps_from_csv(value: Any) -> List[str]:
    if not value:
        return []
    return [p for p in str(value).split(",") if p]


def add_study_blocks(
    track_kind: str,
    track_id: str,
    blocks: Sequence[Mapping[str, Any]],
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Record the batch of blocks the scheduler just WROTE to the calendar (status 'written').
    Each block carries its Google ``event_id`` + ``calendar_id`` so it stays removable, and its full
    ``step_ids`` set so a later propose knows which steps are already on the calendar. Returns the
    inserted rows (with ids), ordered by start_at. Callers that must survive a partial calendar
    write pass one block at a time, so each commit lands with its event."""
    conn = connect(db_path)
    ids: List[int] = []
    try:
        for b in blocks:
            cur = conn.execute(
                """
                INSERT INTO study_blocks
                    (track_kind, track_id, step_id, step_ids, calendar_id, event_id, title,
                     start_at, end_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_kind,
                    track_id,
                    b["step_id"],
                    _steps_to_csv(b.get("step_ids") or ([b["step_id"]] if b.get("step_id") else [])),
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
