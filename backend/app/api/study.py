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
from typing import Any, Dict, List, Optional, Sequence, Set
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from ..chat import BriefChatClient, append_chat_ledger
from ..deps import get_app_settings, get_calendar_port, get_study_negotiate_client
from ..models import (
    AppliedPlan,
    ConflictEvent,
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
from ..studycal.parse import parse_preference
from ..studycal.planner import PlanConfig, plan_sessions
from ..studycal.port import CalendarNotConnected, Interval

router = APIRouter()

TRACK_KIND = "path"
_TZ = ZoneInfo("America/Chicago")
_MIN_SESSION, _MAX_SESSION = 10, 180
_DEF = PlanConfig()  # planner defaults for knobs the user + persisted prefs both leave unset
# The panel's "no preference set" default window — a broad daytime band (aligned with the frontend),
# so a fresh path isn't stuck on the planner's evening default. One tap / one note to change.
_DEFAULT_START, _DEFAULT_END = 9, 17
_UNREADABLE = "I couldn't read that one — set it with the controls above, or try simpler wording."


def _apply_overrides(config: PlanConfig, ov: Dict[str, Any]) -> PlanConfig:
    """Overlay a knob-override dict (from the local parser or the claude lane) onto ``config`` —
    the note wins for the keys it names, the controls hold for the rest. Values are clamped and the
    day window is repaired so ``day_end_hour`` stays above ``day_start_hour``."""
    fields: Dict[str, Any] = dict(ov)
    if "days_of_week" in fields:
        d = fields["days_of_week"]
        fields["days_of_week"] = frozenset(d) if d else None
    for key, lo, hi in (
        ("session_minutes", _MIN_SESSION, _MAX_SESSION),
        ("day_start_hour", 0, 23),
        ("day_end_hour", 1, 24),
        ("max_blocks", 1, 20),
        ("max_per_day", 1, 5),
        ("window_days", 1, 30),
    ):
        if key in fields:
            fields[key] = _clamp(fields[key], lo, hi)
    new = replace(config, **fields)
    if new.day_end_hour <= new.day_start_hour:
        # Repair by moving the edge the note did NOT name, so the repair can't undo the note: an
        # end-only note ("nothing after 3pm") against a standing 17:00 start must not be pushed to
        # 17:00–18:00, which is the very band it ruled out. A start-only note still gives way at the
        # end (unchanged), and a note naming both edges — or neither — keeps the end-moves rule.
        if "day_end_hour" in fields and "day_start_hour" not in fields:
            new = replace(new, day_start_hour=max(0, new.day_end_hour - 1))
        else:
            new = replace(new, day_end_hour=min(24, new.day_start_hour + 1))
    return new


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


_MAX_CONFLICTS = 8


def _busy_events(port: Any, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """Titled busy events for flagging/annotation — best-effort: any adapter hiccup degrades to an
    empty list (the freebusy-based placement is unaffected), so titles never break a propose."""
    try:
        return list(port.busy_events(start, end))
    except Exception:
        return []


def _events_in_window(events: List[Dict[str, Any]], config: PlanConfig) -> List[ConflictEvent]:
    """The titled events that fall inside the requested daily band on allowed weekdays — i.e. what is
    booking the window the learner asked for. Sorted by start, capped for a legible flag."""
    out: List[ConflictEvent] = []
    for ev in sorted(events, key=lambda e: e["start"]):
        s = ev["start"].astimezone(_TZ)
        e = ev["end"].astimezone(_TZ)
        if config.days_of_week is not None and s.weekday() not in config.days_of_week:
            continue
        midnight = s.replace(hour=0, minute=0, second=0, microsecond=0)
        band_start = midnight + timedelta(hours=config.day_start_hour)
        band_end = midnight + timedelta(hours=config.day_end_hour)
        if s < band_end and e > band_start:  # overlaps the daily study band
            out.append(ConflictEvent(start=s.isoformat(), end=e.isoformat(), title=ev["title"]))
        if len(out) >= _MAX_CONFLICTS:
            break
    return out


def _overlaps_for(block: Dict[str, Any], events: List[Dict[str, Any]]) -> List[str]:
    """Distinct titles of events a placed block double-books (for its ⚠ badge)."""
    bs = datetime.fromisoformat(block["start"])
    be = datetime.fromisoformat(block["end"])
    titles: List[str] = []
    for ev in events:
        if ev["start"] < be and ev["end"] > bs and ev["title"] not in titles:
            titles.append(ev["title"])
    return titles


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


def _scheduled_step_ids(rows: Sequence[Dict[str, Any]]) -> Set[str]:
    """Every step id covered by a live ('written') ledger block. Reads the full ``step_ids`` set —
    a block packs several steps, and keying off the first one alone is how a revisit came to
    re-schedule the rest of them."""
    return {sid for r in rows for sid in (r.get("step_ids") or []) if sid}


def _ledger_intervals(rows: Sequence[Dict[str, Any]]) -> List[Interval]:
    """Live study blocks as busy intervals, so new placement dodges them. free/busy only reads the
    primary calendar (a documented v0 deferral), which leaves the dedicated Study calendar invisible.

    Defensive by design: a row whose times don't parse — or that predates the confirm-side
    validation — is skipped rather than raised, and a naive datetime would blow up the planner's
    interval comparisons, so those go too. One bad row must never 500 every future propose."""
    out: List[Interval] = []
    for r in rows:
        try:
            start = datetime.fromisoformat(str(r.get("start_at")))
            end = datetime.fromisoformat(str(r.get("end_at")))
        except (TypeError, ValueError):
            continue
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            continue
        out.append((start.astimezone(_TZ), end.astimezone(_TZ)))
    return out


def _connected(port: Any) -> bool:
    try:
        return bool(port.is_connected())
    except Exception:
        return False


def _token_age(port: Any) -> Optional[float]:
    """Days since the Google consent, best-effort — a port that can't say (or blows up saying)
    degrades to ``None`` rather than breaking the whole state payload."""
    try:
        fn = getattr(port, "token_age_days", None)
        return fn() if callable(fn) else None
    except Exception:
        return None


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
        token_age_days=_token_age(port),
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
    visits. Config is built from the explicit control knobs (falling back to persisted prefs, then a
    daytime default). A free-text ``preference`` **refines** those controls: the local deterministic
    parser handles the common patterns (days · time-of-day · session length · max blocks) with no LLM
    call, and only an unrecognized phrase falls back to the grounded ``claude -p`` lane; if neither
    can read it, the plan is unchanged and an honest message is returned (never a silent no-op)."""
    raw = _load_path_or_404(notebook_id)
    opt = study_blocks.get_study_opt_in(TRACK_KIND, notebook_id)
    # Steps with a live block are already on the calendar; re-planning them is how a second visit
    # (or a double-tap, or a retry after a timeout) wrote a whole duplicate event set.
    live_rows = study_blocks.list_study_blocks(TRACK_KIND, notebook_id)
    already = _scheduled_step_ids(live_rows)
    steps = [s for s in _incomplete_steps(notebook_id, raw) if s["id"] not in already]
    already_ids = [s["id"] for s in _incomplete_steps(notebook_id, raw) if s["id"] in already]

    def _pref(key: str, default: int) -> int:
        v = opt.get(key)
        return int(v) if v is not None else int(default)

    session_minutes = _clamp_session(
        body.session_minutes if body.session_minutes is not None else opt["session_minutes"]
    )
    day_start = _clamp(
        body.day_start_hour if body.day_start_hour is not None else _pref("day_start_hour", _DEFAULT_START),
        0, 23,
    )
    day_end = _clamp(
        body.day_end_hour if body.day_end_hour is not None else _pref("day_end_hour", _DEFAULT_END),
        1, 24,
    )
    if day_end <= day_start:  # repair an inverted window
        day_end = min(24, day_start + 1)
    dow = _norm_days(body.days_of_week) if body.days_of_week is not None else _norm_days(opt.get("days_of_week"))
    max_blocks = _clamp(
        body.max_blocks if body.max_blocks is not None else _pref("max_blocks", _DEF.max_blocks), 1, 20
    )
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
    pref_text = (body.preference or "").strip()
    if pref_text:
        # 1) Local parser first — refines the current controls, no LLM, always available.
        overrides = parse_preference(pref_text, config.days_of_week)
        if overrides:
            config = _apply_overrides(config, overrides)
        else:
            # 2) Fallback: the grounded claude -p lane for phrasings the parser doesn't recognize.
            neg = negotiate_plan(client, preference=pref_text, base_config=config)
            changed = neg["changed"]
            if changed:
                config = _apply_overrides(config, changed)
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
            if not changed:  # 3) neither parser nor claude could read it — be honest, don't pretend
                message = message or _UNREADABLE

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
            already_scheduled_step_ids=already_ids,
            message=message,
            error=negotiate_error,
            applied=applied,
        )

    now = _now()
    horizon = now + timedelta(days=config.window_days)
    try:
        busy = port.free_busy(now, horizon)
    except CalendarNotConnected:
        return StudyProposal(
            ok=False,
            connected=False,
            session_minutes=config.session_minutes,
            unscheduled_step_ids=unscheduled,
            already_scheduled_step_ids=already_ids,
            message=message,
            error=negotiate_error,
            applied=applied,
        )

    events = _busy_events(port, now, horizon)  # titled, for flagging + double-book annotation
    # Live study blocks are pinned busy even in double-book mode: studying through someone else's
    # meeting is the point of that mode; stacking a block on your own study time never is.
    plan = plan_sessions(
        steps,
        busy=busy,
        now=now,
        config=config,
        ignore_busy=body.allow_double_book,
        always_busy=_ledger_intervals(live_rows),
    )
    if already_ids and not steps:
        # Don't hand back an empty plan with no explanation — say why there's nothing to do.
        message = message or "Every remaining step is already on your calendar."

    if body.allow_double_book:
        # Placed over free/busy: annotate each block with what it double-books (⚠), no conflict flag.
        blocks = [
            ProposedBlock(**b, overlaps=_overlaps_for(b, events)) for b in plan["blocks"]
        ]
        conflicts: List[ConflictEvent] = []
        can_double_book = False
    else:
        blocks = [ProposedBlock(**b) for b in plan["blocks"]]
        # Steps that didn't fit AND real events sitting in the requested window → offer a double-book.
        conflicts = _events_in_window(events, config) if plan["unscheduled_step_ids"] else []
        can_double_book = bool(plan["unscheduled_step_ids"]) and bool(conflicts)

    return StudyProposal(
        ok=True,
        connected=True,
        session_minutes=config.session_minutes,
        blocks=blocks,
        unscheduled_step_ids=plan["unscheduled_step_ids"],
        already_scheduled_step_ids=already_ids,
        message=message,
        error=negotiate_error,
        applied=applied,
        conflicts=conflicts,
        can_double_book=can_double_book,
        total_cost_usd=cost,
        duration_ms=duration,
    )


def _validate_block_times(blocks: Sequence[ProposedBlock]) -> None:
    """Every block must carry tz-aware RFC3339 times with end after start — what the planner emits.

    Confirm bodies are client-controlled, and an unvalidated string is a real hazard on both sides:
    Google rejects it mid-batch with a 400, and it lands in the ledger as a row a later propose
    can't parse. Reject at the door instead."""
    for b in blocks:
        try:
            start, end = datetime.fromisoformat(b.start), datetime.fromisoformat(b.end)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422, detail="Block start/end must be RFC3339 timestamps with an offset."
            )
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise HTTPException(
                status_code=422, detail="Block start/end must carry an offset, and end after start."
            )


def _partial_write_detail(written: int, total: int, exc: Optional[Exception] = None) -> str:
    """Honest copy for a confirm that died mid-batch: say exactly how far it got, and that the part
    that landed is still removable (the one hard rule holds even on the failure path)."""
    tail = f" ({exc})" if exc else ""
    return (
        f"Wrote {written} of {total} blocks before the calendar failed{tail}. "
        "The ones that were written are on your calendar and can still be removed from here."
    )


@router.post("/paths/{notebook_id}/schedule/confirm", response_model=StudyScheduleState)
def confirm(
    notebook_id: str, body: StudyConfirmRequest, port: Any = Depends(get_calendar_port)
) -> StudyScheduleState:
    """Write the reviewed batch to the 'Study' calendar, recording each event in the removable
    ledger **as it lands** — create one, ledger one, repeat. That ordering is what makes the
    feature's one hard rule ("every written event is removable") survive a mid-batch failure: a
    batch that only ledgers after every insert succeeds strands whatever it already created.

    Calendar writes are opt-in, enforced here rather than by the UI hiding the panel — a stale tab
    or a retried POST must not be able to write events for an opted-out path. A partial failure
    returns 502 with an honest count; everything written before it stays removable."""
    _load_path_or_404(notebook_id)
    if not body.blocks:
        raise HTTPException(status_code=422, detail="No blocks to write.")
    if not study_blocks.get_study_opt_in(TRACK_KIND, notebook_id)["enabled"]:
        raise HTTPException(
            status_code=409,
            detail="Calendar scheduling is off for this path — turn it on before writing blocks.",
        )
    _validate_block_times(body.blocks)

    # Skip blocks whose steps already have a live block, so a double-tap or a retry-after-timeout
    # can't write a second copy. Skip-and-continue rather than reject-the-batch: resubmitting the
    # whole set is exactly how a partially-written confirm gets finished.
    already = _scheduled_step_ids(study_blocks.list_study_blocks(TRACK_KIND, notebook_id))
    pending = [b for b in body.blocks if not (already & set(b.step_ids))]
    if not pending:
        raise HTTPException(
            status_code=409,
            detail="Those steps are already on your calendar — remove the existing blocks first.",
        )

    try:
        calendar_id = port.ensure_study_calendar()
    except CalendarNotConnected as e:
        raise HTTPException(status_code=409, detail=str(e))

    total, written = len(pending), 0
    for b in pending:
        event = {
            "summary": f"📚 {b.title}".strip(),
            "description": _describe(b),
            "start": b.start,
            "end": b.end,
        }
        try:
            event_id = port.create_event(calendar_id, event)
        except CalendarNotConnected as e:
            # A clean 409 only while nothing has been written yet; once events exist, the partial
            # count is the honest answer regardless of *why* the rest failed.
            if written == 0:
                raise HTTPException(status_code=409, detail=str(e))
            raise HTTPException(status_code=502, detail=_partial_write_detail(written, total, e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=_partial_write_detail(written, total, e))

        row = {
            "step_id": (b.step_ids[0] if b.step_ids else ""),
            "step_ids": list(b.step_ids),
            "calendar_id": calendar_id,
            "event_id": event_id,
            "title": b.title,
            "start_at": b.start,
            "end_at": b.end,
        }
        try:
            study_blocks.add_study_blocks(TRACK_KIND, notebook_id, [row])
        except Exception as e:
            # The ledger is what makes an event removable, so an event we can't record must not
            # survive: drop it again, best-effort, rather than leave an orphan on the calendar.
            try:
                port.delete_events(calendar_id, [event_id])
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=_partial_write_detail(written, total, e))
        written += 1

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
