"""app.studycal.planner — the deterministic session planner (v0).

Two pure phases, no clock/DB/network of their own (``now`` + ``busy`` are injected), so every
property is deterministic to assert:

1. **Pack** the path's incomplete steps, in order, into sessions capped at ``session_minutes`` — a
   step is never split across two blocks, an over-long single step gets its own (longer) block, and
   micro-glue (intro/reflect/recap) rides along in the current session rather than opening its own.
2. **Place** each session-length block in the earliest free slot inside a daily study window,
   skipping ``busy`` intervals, never scheduling in the past, one block per day by default so
   sessions spread out (spacing beats cramming). Blocks that don't fit the window are reported as
   ``unscheduled_step_ids`` rather than dropped silently.

Times are computed in ``America/Chicago`` (Kyle is CT) as timezone-aware datetimes and serialized
RFC3339-with-offset, so the summer/winter offset (-05:00 / -06:00) is correct without special-casing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from .duration import is_foldable, step_minutes

Interval = Tuple[datetime, datetime]


@dataclass
class PlanConfig:
    session_minutes: int = 45
    window_days: int = 14
    day_start_hour: int = 18  # study window opens 6pm local
    day_end_hour: int = 21    # and closes 9pm local
    max_blocks: int = 8
    max_per_day: int = 1
    # Allowed days of the week (Python ``weekday()``: Mon=0 … Sun=6). ``None`` = every day is fair
    # game (the v0 default); a subset lets the learner ask for "weekdays" / "Tue+Thu" / "weekends".
    days_of_week: Optional[FrozenSet[int]] = None
    tz: str = "America/Chicago"


def _pack(steps: Sequence[Mapping[str, Any]], session_minutes: int) -> List[List[Mapping[str, Any]]]:
    """Group consecutive steps into sessions capped at ``session_minutes`` (never splitting a step;
    glue folds into the current session)."""
    sessions: List[List[Mapping[str, Any]]] = []
    current: List[Mapping[str, Any]] = []
    content = 0
    for s in steps:
        m = step_minutes(s)
        if not current:
            current, content = [s], m
            continue
        if is_foldable(s):
            # Glue always rides in the current session — it never opens or closes a block.
            current.append(s)
            content += m
            continue
        if content + m <= session_minutes:
            current.append(s)
            content += m
        else:
            sessions.append(current)
            current, content = [s], m
    if current:
        sessions.append(current)
    return sessions


def _local_window(day: datetime, hour: int) -> datetime:
    """The wall-clock ``hour`` on ``day`` (already tz-aware) — DST offset resolved by zoneinfo."""
    return day.replace(hour=hour, minute=0, second=0, microsecond=0)


def _earliest_slot(
    win_start: datetime, win_end: datetime, occupied: List[Interval], need: timedelta
) -> Optional[datetime]:
    """The earliest start in ``[win_start, win_end]`` where a ``need``-long block clears every
    ``occupied`` interval (sorted). ``None`` if the day can't hold it."""
    cursor = win_start
    for bs, be in occupied:
        if be <= cursor:
            continue
        if bs >= win_end:
            break
        if bs - cursor >= need:
            return cursor
        if be > cursor:
            cursor = be
        if cursor >= win_end:
            break
    return cursor if win_end - cursor >= need else None


def _block(session: Sequence[Mapping[str, Any]], start: datetime, end: datetime, minutes: int) -> Dict[str, Any]:
    anchor = next((s for s in session if not is_foldable(s)), session[0])
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "minutes": minutes,
        "title": str(anchor.get("title") or anchor.get("id") or "Study"),
        "step_ids": [s["id"] for s in session],
        "steps": [
            {
                "id": s["id"],
                "kind": s.get("kind", ""),
                "title": str(s.get("title") or s["id"]),
                "minutes": step_minutes(s),
            }
            for s in session
        ],
    }


def plan_sessions(
    steps: Sequence[Mapping[str, Any]],
    *,
    busy: Sequence[Interval],
    now: datetime,
    config: PlanConfig,
    ignore_busy: bool = False,
) -> Dict[str, Any]:
    """Propose calendar blocks for a path's incomplete ``steps`` against ``busy`` free/busy, as of
    ``now`` (both tz-aware). Writes nothing — pure planning. Returns ``blocks`` (chronological) +
    ``unscheduled_step_ids`` (steps that didn't fit the window / hit ``max_blocks``).

    ``ignore_busy=True`` is the deliberate **double-book** mode: placement ignores ``busy`` entirely
    (a block lands at the earliest window start regardless of existing events), for the "someone put
    stuff on my calendar but I can study through it" case. Everything else — the day window,
    ``days_of_week``, one-per-day, never-in-the-past — still holds; the caller flags the overlaps."""
    tz = ZoneInfo(config.tz)
    now = now.astimezone(tz)
    base_date = _local_window(now, config.day_start_hour)  # today's window start (tz-aware anchor)

    sessions = _pack(steps, config.session_minutes)

    blocks: List[Dict[str, Any]] = []
    unscheduled: List[str] = []
    placed_by_day: Dict[int, List[Interval]] = {}
    count_by_day: Dict[int, int] = {}

    for session in sessions:
        session_ids = [s["id"] for s in session]
        if len(blocks) >= config.max_blocks:
            unscheduled.extend(session_ids)
            continue
        content = sum(step_minutes(s) for s in session)
        block_len = max(content, config.session_minutes)
        need = timedelta(minutes=block_len)

        placed: Optional[datetime] = None
        for d in range(config.window_days):
            if count_by_day.get(d, 0) >= config.max_per_day:
                continue
            win_start = base_date + timedelta(days=d)
            if config.days_of_week is not None and win_start.weekday() not in config.days_of_week:
                continue  # this weekday isn't allowed (e.g. weekends when the learner asked for weekdays)
            win_end = _local_window(win_start, config.day_end_hour)
            eff_start = max(win_start, now)
            if win_end <= eff_start:
                continue
            external = [] if ignore_busy else [iv for iv in busy if iv[1] > eff_start and iv[0] < win_end]
            occ = sorted(external + placed_by_day.get(d, []))
            slot = _earliest_slot(eff_start, win_end, occ, need)
            if slot is not None:
                # A slot snapped to a busy-interval boundary inherits that interval's tz (Google
                # free/busy comes back in UTC); normalize to CT so every block serializes with the
                # CT offset — same instant, consistent -05:00/-06:00.
                placed = slot.astimezone(tz)
                placed_by_day.setdefault(d, []).append((placed, placed + need))
                count_by_day[d] = count_by_day.get(d, 0) + 1
                break

        if placed is None:
            unscheduled.extend(session_ids)
        else:
            blocks.append(_block(session, placed, placed + need, block_len))

    return {
        "session_minutes": config.session_minutes,
        "blocks": blocks,
        "unscheduled_step_ids": unscheduled,
    }
