"""GET/POST /api/paths/{notebook_id}/schedule/* — the Study Scheduler (v0).

The acting surface for opt-in Google Calendar study blocks over a learning path. Flow: toggle the
per-path opt-in → **propose** a set of blocks (read-only: incomplete steps + duration model +
free/busy + the deterministic planner, optionally shaped by the claude -p negotiation lane) →
**confirm** writes the reviewed batch to the dedicated 'Study' calendar and records each event in the
removable ledger → **remove** deletes events + flips the ledger. Every calendar call goes through the
injected ``CalendarPort`` (fake in tests), and an unconnected calendar degrades to an honest
``connected=False`` state rather than a 500."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from ..chat import BriefChatClient, append_chat_ledger
from ..deps import get_app_settings, get_calendar_port, get_study_negotiate_client
from ..models import (
    AppliedPlan,
    ProposedBlock,
    StudyConfirmRequest,
    StudyOptInRequest,
    StudyProposal,
    StudyProposeRequest,
    StudyRemoveRequest,
    StudyScheduleState,
    WrittenBlock,
)
from ..paths import PathError, get_path
from ..store import db
from ..store import study_blocks
from ..studycal.negotiate import negotiate_plan
from ..studycal.planner import PlanConfig, plan_sessions
from ..studycal.port import CalendarNotConnected

router = APIRouter()

TRACK_KIND = "path"
_TZ = ZoneInfo("America/Chicago")
_MIN_SESSION, _MAX_SESSION = 10, 180
_DEF = PlanConfig()  # planner defaults for knobs the user + persisted prefs both leave unset


def _now() -> datetime:
    return datetime.now(_TZ)


def _clamp_session(minutes: int) -> int:
    return max(_MIN_SESSION, min(_MAX_SESSION, int(minutes)))


def _clamp(value: Any, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _norm_days(value: Optional[Sequence[int]]) -> Optional[List[int]]:
    """A sorted, unique list of weekday ints (Mon=0 … Sun=6) from a control list, dropping anything
    out of range. ``None``/empty → ``None`` (every day — no restriction)."""
    if not value:
        return None
    out = sorted({int(d) for d in value if not isinstance(d, bool) and isinstance(d, int) and 0 <= int(d) <= 6})
    return out or None


def _load_path_or_404(notebook_id: str) -> Dict[str, Any]:
    try:
        raw = get_path(notebook_id)
    except PathError as e:
        raise HTTPException(status_code=422, detail=f"malformed path: {e}")
    if raw is None:
        raise HTTPException(status_code=404, detail="No learning path for this topic yet.")
    return raw


def _incomplete_steps(notebook_id: str, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    done = db.get_path_progress(notebook_id)
    return [s for s in raw["steps"] if not done.get(s["id"])]


def _connected(port: Any) -> bool:
    try:
        return bool(port.is_connected())
    except Exception:
        return False


def _written(rows: List[Dict[str, Any]]) -> List[WrittenBlock]:
    return [
        WrittenBlock(
            id=r["id"],
            step_id=r["step_id"],
            title=r["title"],
            start=r["start_at"],
            end=r["end_at"],
            event_id=r["event_id"],
            calendar_id=r["calendar_id"],
            status=r["status"],
        )
        for r in rows
    ]


def _state(notebook_id: str, port: Any) -> StudyScheduleState:
    opt = study_blocks.get_study_opt_in(TRACK_KIND, notebook_id)
    rows = study_blocks.list_study_blocks(TRACK_KIND, notebook_id)
    return StudyScheduleState(
        track_id=notebook_id,
        enabled=opt["enabled"],
        session_minutes=opt["session_minutes"],
        connected=_connected(port),
        calendar_id=rows[-1]["calendar_id"] if rows else None,
        blocks=_written(rows),
        day_start_hour=opt["day_start_hour"],
        day_end_hour=opt["day_end_hour"],
        days_of_week=opt["days_of_week"],
        max_blocks=opt["max_blocks"],
    )


@router.get("/paths/{notebook_id}/schedule", response_model=StudyScheduleState)
def get_schedule(notebook_id: str, port: Any = Depends(get_calendar_port)) -> StudyScheduleState:
    _load_path_or_404(notebook_id)
    return _state(notebook_id, port)


@router.post("/paths/{notebook_id}/schedule/opt-in", response_model=StudyScheduleState)
def set_opt_in(
    notebook_id: str, body: StudyOptInRequest, port: Any = Depends(get_calendar_port)
) -> StudyScheduleState:
    _load_path_or_404(notebook_id)
    current = study_blocks.get_study_opt_in(TRACK_KIND, notebook_id)
    minutes = body.session_minutes if body.session_minutes is not None else current["session_minutes"]
    study_blocks.set_study_opt_in(TRACK_KIND, notebook_id, body.enabled, _clamp_session(minutes))
    return _state(notebook_id, port)


@router.post("/paths/{notebook_id}/schedule/propose", response_model=StudyProposal)
def propose(
    notebook_id: str,
    body: StudyProposeRequest,
    port: Any = Depends(get_calendar_port),
    client: BriefChatClient = Depends(get_study_negotiate_client),
    settings=Depends(get_app_settings),
) -> StudyProposal:
    """Propose blocks for the path's incomplete steps against live free/busy. Read-only against the
    calendar — writes no events; it does persist the learner's control prefs so they stick across
    visits. Config is built from the explicit control knobs (falling back to the persisted prefs,
    then planner defaults); the free-text ``preference`` runs the claude -p negotiation lane, whose
    suggestions fill only the knobs the user did NOT set by hand this turn (controls win per key)."""
    raw = _load_path_or_404(notebook_id)
    opt = study_blocks.get_study_opt_in(TRACK_KIND, notebook_id)
    steps = _incomplete_steps(notebook_id, raw)

    # Which knobs the user set explicitly this turn — these win over any LLM suggestion for the key.
    explicit: set[str] = set()

    def _pref(key: str, default: int) -> int:
        v = opt.get(key)
        return int(v) if v is not None else int(default)

    if body.session_minutes is not None:
        explicit.add("session_minutes")
    session_minutes = _clamp_session(
        body.session_minutes if body.session_minutes is not None else opt["session_minutes"]
    )
    if body.day_start_hour is not None:
        explicit.add("day_start_hour")
    day_start = _clamp(
        body.day_start_hour if body.day_start_hour is not None else _pref("day_start_hour", _DEF.day_start_hour),
        0, 23,
    )
    if body.day_end_hour is not None:
        explicit.add("day_end_hour")
    day_end = _clamp(
        body.day_end_hour if body.day_end_hour is not None else _pref("day_end_hour", _DEF.day_end_hour),
        1, 24,
    )
    if day_end <= day_start:  # repair an inverted window (same rule as the negotiation lane)
        day_end = min(24, day_start + 1)
    if body.days_of_week is not None:
        explicit.add("days_of_week")
        dow = _norm_days(body.days_of_week)
    else:
        dow = _norm_days(opt.get("days_of_week"))
    if body.max_blocks is not None:
        explicit.add("max_blocks")
    max_blocks = _clamp(
        body.max_blocks if body.max_blocks is not None else _pref("max_blocks", _DEF.max_blocks), 1, 20
    )
    if body.max_per_day is not None:
        explicit.add("max_per_day")
    max_per_day = _clamp(body.max_per_day if body.max_per_day is not None else _DEF.max_per_day, 1, 5)
    window_days = _clamp(body.days if body.days is not None else _DEF.window_days, 1, 30)

    config = PlanConfig(
        session_minutes=session_minutes,
        window_days=window_days,
        day_start_hour=day_start,
        day_end_hour=day_end,
        max_blocks=max_blocks,
        max_per_day=max_per_day,
        days_of_week=frozenset(dow) if dow else None,
    )

    message = None
    negotiate_error = None
    cost = duration = None
    if body.preference and body.preference.strip():
        neg = negotiate_plan(client, preference=body.preference, base_config=config)
        # Apply only the knobs the user did NOT set explicitly this turn (per-key precedence).
        apply = {k: v for k, v in neg["changed"].items() if k not in explicit}
        if apply:
            if "days_of_week" in apply:
                apply["days_of_week"] = frozenset(apply["days_of_week"]) if apply["days_of_week"] else None
            config = replace(config, **apply)
        message = neg["message"] or None
        negotiate_error = neg["error"]
        env = neg.get("envelope") or {}
        cost, duration = env.get("total_cost_usd"), env.get("duration_ms")
        append_chat_ledger(
            settings.study_negotiate_ledger,
            brief_date="",
            topic_slug=notebook_id,
            item_id="negotiate",
            model=client.model,
            envelope=neg.get("envelope"),
            error=negotiate_error,
        )

    dow_list = sorted(config.days_of_week) if config.days_of_week else []
    # Persist the effective control set so the panel hydrates to it next visit (calendar untouched).
    study_blocks.set_study_prefs(
        TRACK_KIND,
        notebook_id,
        session_minutes=config.session_minutes,
        day_start_hour=config.day_start_hour,
        day_end_hour=config.day_end_hour,
        days_of_week=dow_list or None,
        max_blocks=config.max_blocks,
    )
    applied = AppliedPlan(
        session_minutes=config.session_minutes,
        day_start_hour=config.day_start_hour,
        day_end_hour=config.day_end_hour,
        days_of_week=dow_list,
        window_days=config.window_days,
        max_blocks=config.max_blocks,
        max_per_day=config.max_per_day,
    )

    unscheduled = [s["id"] for s in steps]
    if not _connected(port):
        return StudyProposal(
            ok=False,
            connected=False,
            session_minutes=config.session_minutes,
            unscheduled_step_ids=unscheduled,
            message=message,
            error=negotiate_error,
            applied=applied,
        )

    now = _now()
    try:
        busy = port.free_busy(now, now + timedelta(days=config.window_days))
    except CalendarNotConnected:
        return StudyProposal(
            ok=False,
            connected=False,
            session_minutes=config.session_minutes,
            unscheduled_step_ids=unscheduled,
            message=message,
            applied=applied,
        )

    plan = plan_sessions(steps, busy=busy, now=now, config=config)
    return StudyProposal(
        ok=True,
        connected=True,
        session_minutes=config.session_minutes,
        blocks=[ProposedBlock(**b) for b in plan["blocks"]],
        unscheduled_step_ids=plan["unscheduled_step_ids"],
        message=message,
        error=negotiate_error,
        applied=applied,
        total_cost_usd=cost,
        duration_ms=duration,
    )


@router.post("/paths/{notebook_id}/schedule/confirm", response_model=StudyScheduleState)
def confirm(
    notebook_id: str, body: StudyConfirmRequest, port: Any = Depends(get_calendar_port)
) -> StudyScheduleState:
    """Write the reviewed batch to the 'Study' calendar in one pass, recording each event id so the
    block stays removable. Nothing writes before this call (the single plan-level confirm)."""
    _load_path_or_404(notebook_id)
    if not body.blocks:
        raise HTTPException(status_code=422, detail="No blocks to write.")
    events = [
        {
            "summary": f"📚 {b.title}".strip(),
            "description": _describe(b),
            "start": b.start,
            "end": b.end,
        }
        for b in body.blocks
    ]
    try:
        calendar_id = port.ensure_study_calendar()
        event_ids = port.create_events(calendar_id, events)
    except CalendarNotConnected as e:
        raise HTTPException(status_code=409, detail=str(e))

    rows = [
        {
            "step_id": (b.step_ids[0] if b.step_ids else ""),
            "calendar_id": calendar_id,
            "event_id": eid,
            "title": b.title,
            "start_at": b.start,
            "end_at": b.end,
        }
        for b, eid in zip(body.blocks, event_ids)
    ]
    study_blocks.add_study_blocks(TRACK_KIND, notebook_id, rows)
    return _state(notebook_id, port)


@router.post("/paths/{notebook_id}/schedule/remove", response_model=StudyScheduleState)
def remove(
    notebook_id: str, body: StudyRemoveRequest, port: Any = Depends(get_calendar_port)
) -> StudyScheduleState:
    """Delete written blocks from the calendar and flip them 'removed' in the ledger — a subset by
    ``block_ids`` or every live block. Deletion is idempotent, so a partial remove can be retried."""
    _load_path_or_404(notebook_id)
    rows = study_blocks.list_study_blocks(TRACK_KIND, notebook_id)
    if body.block_ids is not None:
        wanted = set(body.block_ids)
        rows = [r for r in rows if r["id"] in wanted]
    if rows:
        by_cal: Dict[str, List[str]] = {}
        for r in rows:
            by_cal.setdefault(r["calendar_id"], []).append(r["event_id"])
        try:
            for cal, event_ids in by_cal.items():
                port.delete_events(cal, event_ids)
        except CalendarNotConnected as e:
            raise HTTPException(status_code=409, detail=str(e))
        study_blocks.mark_study_blocks_removed(TRACK_KIND, notebook_id, [r["id"] for r in rows])
    return _state(notebook_id, port)


def _describe(block: ProposedBlock) -> str:
    steps = ", ".join(s.title for s in block.steps if s.title)
    return f"Home Base study block — {steps}" if steps else "Home Base study block"
