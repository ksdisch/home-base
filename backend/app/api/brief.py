"""GET /api/brief + the visit log (M1) + inline item notes (M2) — the Today page.

Serves the newest data/sweeps/<date>/ folder: structured topics from <topic>.json, with an
honest raw-markdown fallback for md-only days (the pre-JSON era) or an unreadable json — a
topic is never silently dropped. Never a 500 on missing data: no sweeps yet degrades to
``has_data=false`` and the page tells you to run ``make sweep``. The visit log is the
kickoff's habit metric (opened ≥5 mornings/week); M1 only writes it — read it via sqlite.

M2 notes: each structured item carries a read-time id (see ``app.sweeps``); the served
day's notes are joined inline onto their items, POST /brief/notes attaches one, and
GET /brief/notes?topic= is the browsable-per-topic read (note rows are self-contained via
their snapshot columns, so they outlive the sweep files they point at).
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ..chat import (
    BriefChatError,
    _scrubbed_env,
    append_chat_ledger,
    build_prompt,
    max_question_chars,
)
from ..deps import get_app_settings, get_brief_chat_client
from ..models import (
    BriefAudioChapter,
    BriefCalibration,
    BriefChatRequest,
    BriefChatResponse,
    BriefArchiveEntry,
    BriefArchiveResponse,
    BriefHabitResponse,
    BriefHabitWeek,
    BriefMissingTopic,
    BriefNote,
    BriefNoteCreate,
    BriefNoteDeleteResponse,
    BriefNotesResponse,
    BriefOvernight,
    BriefOvernightProposal,
    BriefReadiness,
    BriefResponse,
    BriefSweepResponse,
    BriefTopic,
    BriefVisitResponse,
)
from ..mirror import build_mirror
from ..overnight import append_status, build_overnight, load_queue
from ..store import (
    add_brief_note,
    brief_habit_weeks,
    delete_brief_note,
    list_brief_notes,
    record_brief_visit,
)
from ..sweeps import (
    build_calibration,
    build_readiness,
    latest_sweep_date,
    load_brief_topics,
    load_roster,
    sweep_dates,
    topic_title,
)
from ..visit_source import source_from_request

router = APIRouter()


def _roster_titles(settings) -> Dict[str, str]:
    roster = load_roster(settings.roster_file)
    return {t["slug"]: t["title"] for t in roster if t["title"]}


def _load_audio_chapters(path: Path) -> List[BriefAudioChapter]:
    """FR4: [{slug, title, start_seconds}] written by sweeps/audio_brief.py beside the mp3.

    Missing, mangled, or wrong-shape entries degrade to fewer/no chips — the chips are a
    bonus on top of the player and can never break the morning read."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    chapters: List[BriefAudioChapter] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        slug, title, start = entry.get("slug"), entry.get("title"), entry.get("start_seconds")
        if (
            isinstance(slug, str)
            and isinstance(title, str)
            and isinstance(start, (int, float))
            and not isinstance(start, bool)
        ):
            chapters.append(BriefAudioChapter(slug=slug, title=title, start_seconds=float(start)))
    return chapters


@router.get("/brief", response_model=BriefResponse)
def get_brief(date: Optional[str] = None, settings=Depends(get_app_settings)) -> BriefResponse:
    # QU1: an optional ?date= opens the never-pruned per-day archive — read-only time
    # travel over the raw record the design always promised was durable. No param keeps
    # today's latest-day behavior unchanged.
    dates = sweep_dates(settings.sweeps_dir)
    latest = dates[-1] if dates else None
    if date is not None and date not in dates:
        raise HTTPException(status_code=404, detail=f"no brief for {date}")
    served = date or latest

    roster = load_roster(settings.roster_file)
    raw_topics = load_brief_topics(settings.sweeps_dir, served, roster) if served else []
    titles = {t["slug"]: t["title"] for t in roster if t["title"]}

    # Join the served day's notes onto their items (oldest first — reading order).
    if served and raw_topics:
        notes_by_item: Dict[str, List[dict]] = {}
        for note in reversed(list_brief_notes(brief_date=served)):
            note["topic_title"] = topic_title(note["topic_slug"], titles)
            notes_by_item.setdefault(note["item_id"], []).append(note)
        for topic in raw_topics:
            for item in topic.get("items", []):
                item["notes"] = notes_by_item.get(item["id"], [])

    # QU12: name the active roster topics that produced nothing renderable for the served
    # day (a .raw.txt-only validation failure counts — load_brief_topics skips it). A quiet
    # topic and a crashed topic must not look the same on the page. Paused entries are a
    # legitimate absence; no served day at all is the page-level has_data=false story.
    missing: List[BriefMissingTopic] = []
    if served:
        present = {t["slug"] for t in raw_topics}
        missing = [
            BriefMissingTopic(slug=t["slug"], title=topic_title(t["slug"], titles))
            for t in roster
            if not t["paused"] and t["slug"] not in present
        ]

    # Audio is available for any day that has a brief.mp3, not just the latest — the
    # archive pages can play historical audio via GET /brief/audio?date=YYYY-MM-DD.
    audio_available = served is not None and (settings.sweeps_dir / served / "brief.mp3").is_file()
    # FR4: chapters only ride an actually-present mp3 — audio_brief.py writes them before
    # the render, so a failed Kokoro leaves an orphan file this gate keeps invisible.
    audio_chapters: List[BriefAudioChapter] = []
    if audio_available and served:
        audio_chapters = _load_audio_chapters(settings.sweeps_dir / served / "brief.chapters.json")

    # QU1: prev/next renderable neighbors make the archive walkable from any day.
    prev_date = next_date = None
    if served and served in dates:
        i = dates.index(served)
        prev_date = dates[i - 1] if i > 0 else None
        next_date = dates[i + 1] if i < len(dates) - 1 else None

    return BriefResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=len(raw_topics) > 0,
        date=served,
        topics=[BriefTopic(**t) for t in raw_topics],
        audio_available=audio_available,
        audio_chapters=audio_chapters,
        missing_topics=missing,
        prev_date=prev_date,
        next_date=next_date,
        # Mirror v0: the live view's 'You this week' self-read — an archived ?date=
        # morning is a record and must not wear today's mirror.
        mirror=build_mirror(settings, roster) if date is None else None,
        # Readiness v0: the live morning's 'Coming up' projection, computed for the served
        # day from its own prior window — never attached to a ?date= archive record, and
        # None when there's no served day to project for.
        readiness=(
            BriefReadiness(**build_readiness(settings.sweeps_dir, served, raw_topics))
            if date is None and served
            else None
        ),
        # Calibrated Doubt v0: grade prior mornings' wagers against their next readable
        # sweep and carry the running record — live only; an archived ?date= morning is
        # a record, not a grader.
        calibration=(
            BriefCalibration(
                **build_calibration(
                    settings.sweeps_dir,
                    served,
                    raw_topics,
                    titles,
                    settings.brief_calibration_ledger,
                )
            )
            if date is None and served
            else None
        ),
        # Overnight v0: the draft-only approve/discard queue — live only; an archived
        # ?date= morning is a record, not a to-do list.
        overnight=(
            BriefOvernight(**build_overnight(settings.brief_overnight_ledger, served, titles))
            if date is None and served
            else None
        ),
    )


@router.get("/brief/audio")
def get_brief_audio(
    date: Optional[str] = None, settings=Depends(get_app_settings)
) -> FileResponse:
    """The narrated MP3 for the given date (or the latest sweep when no date is given).

    404 when the day has no audio (Kokoro was down, or a pre-M4 day) — the page hides the
    player. Accepts an optional ?date=YYYY-MM-DD so archive views can stream historical audio.
    """
    if date is not None:
        dates = sweep_dates(settings.sweeps_dir)
        if date not in dates:
            raise HTTPException(status_code=404, detail=f"no brief for {date}")
        d = date
    else:
        d = latest_sweep_date(settings.sweeps_dir)
    path = (settings.sweeps_dir / d / "brief.mp3") if d else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="no audio brief for that sweep")
    return FileResponse(path, media_type="audio/mpeg", filename=f"brief-{d}.mp3")


# FR2: one sweep at a time, guarded in-process — the always-on single server is the choke
# point, so a module lock (not a lockfile) closes the double-fire footgun. The handle also
# lets a later tap see "still running" and tests wait deterministically.
_sweep_lock = threading.Lock()
_sweep_proc: Optional[subprocess.Popen] = None


@router.post("/brief/sweep", response_model=BriefSweepResponse)
def trigger_sweep(settings=Depends(get_app_settings)) -> BriefSweepResponse:
    """FR2: the stale banner's tap — re-invoke ./sweep.sh from the phone (M6's surface).

    Deliberately crosses assumption 2's read-only-phone line: the sweep and the server
    already share the Mac, so the capability is this lock-guarded detached spawn, not new
    infrastructure. No auth beyond the single-user tailnet trust boundary (assumption 5).
    The child env is scrubbed (bug #10's lane set — sweep.sh refuses to start on a leaked
    API key) and carries SWEEP_SKIP_DONE=1 so a tap on a fresh day no-ops per topic;
    SWEEP_FORCE stays absent so the HA2 note-detach guard keeps refusing this non-tty
    lane. Full roster only — per-topic re-runs stay a terminal affordance.
    """
    global _sweep_proc
    with _sweep_lock:
        if _sweep_proc is not None and _sweep_proc.poll() is None:
            return BriefSweepResponse(started=False, already_running=True)
        script = settings.sweep_script
        if not script.is_file():
            raise HTTPException(
                status_code=503, detail=f"sweep runner not found at {script}"
            )
        env = _scrubbed_env()
        env["SWEEP_SKIP_DONE"] = "1"
        env.pop("SWEEP_FORCE", None)
        log_dir = settings.sweeps_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        # The child inherits the fd; append-mode so taps share one honest trail.
        with open(log_dir / "phone-trigger.log", "ab") as log:
            log.write(
                f"[{datetime.now(timezone.utc).isoformat()}] phone tap → {script}\n".encode()
            )
            _sweep_proc = subprocess.Popen(
                ["bash", str(script)],
                cwd=str(script.parent),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return BriefSweepResponse(started=True, already_running=False)


@router.post("/brief/chat", response_model=BriefChatResponse)
def chat_about_brief_item(
    payload: BriefChatRequest,
    settings=Depends(get_app_settings),
    chat=Depends(get_brief_chat_client),
) -> BriefChatResponse:
    """One grounded follow-up answer about a served brief item (M5).

    Runs a single headless ``claude -p`` on the subscription lane (no tools, API key
    scrubbed — see ``app.chat``). The item is looked up on the *served* day, so a question
    from a stale tab 404s honestly instead of answering against the wrong morning. Every
    exchange lands in the chat ledger; only successful answers reach the page.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is empty")
    if len(question) > max_question_chars():
        raise HTTPException(
            status_code=400, detail=f"question is too long ({max_question_chars()} chars max)"
        )

    date = latest_sweep_date(settings.sweeps_dir)
    if not date:
        raise HTTPException(status_code=404, detail="no sweeps yet — nothing to chat about")
    roster = load_roster(settings.roster_file)
    topics = load_brief_topics(settings.sweeps_dir, date, roster)
    topic = next((t for t in topics if t["slug"] == payload.topic_slug), None)
    item = None
    if topic is not None:
        item = next((i for i in topic.get("items", []) if i.get("id") == payload.item_id), None)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail="that item isn't on the served brief — it may have rolled to a new day; reload",
        )

    prompt = build_prompt(topic, item, question, date)
    try:
        result = chat.ask(prompt)
    except BriefChatError as e:
        append_chat_ledger(
            settings.brief_chat_ledger,
            brief_date=date,
            topic_slug=payload.topic_slug,
            item_id=payload.item_id,
            model=chat.model,
            error=f"{e} ({e.detail})" if e.detail else str(e),
        )
        raise HTTPException(status_code=502, detail=f"chat failed: {e}")
    append_chat_ledger(
        settings.brief_chat_ledger,
        brief_date=date,
        topic_slug=payload.topic_slug,
        item_id=payload.item_id,
        model=chat.model,
        envelope=result["envelope"],
    )
    return BriefChatResponse(answer=result["answer"])


@router.post("/brief/visit", response_model=BriefVisitResponse)
def log_brief_visit(request: Request) -> BriefVisitResponse:
    """Log one Today-page load, tagged with where it came from (v14).

    Untagged, this endpoint could not tell a Tuesday morning read from a localhost dev load
    or a verify pass, so the ~08-03 v1 check would have graded build exhaust as a reading
    habit (docs/ideas/builder-vs-reader-metric.md). The bucket is echoed back so a live
    check from the phone can confirm what it lands as."""
    source = source_from_request(request)
    row = record_brief_visit(source=source)
    return BriefVisitResponse(
        ok=True, day=row["day"], visited_at=row["visited_at"], source=source
    )


_GRADE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\b")


def _last_graded(trust_log: Path) -> Optional[str]:
    """Newest ``## YYYY-MM-DD`` heading in the sweep-trust log, or None.

    The log (PR5 — docs/sweep-trust-log.md) is hand-appended at each monthly re-grade
    against the M0 rubric, so parse defensively: a missing or mangled file degrades to
    None — never a fabricated date, never a failed habit response."""
    try:
        text = trust_log.read_text(encoding="utf-8")
    except OSError:
        return None
    dates = [m.group(1) for line in text.splitlines() if (m := _GRADE_HEADING.match(line))]
    return max(dates) if dates else None


@router.get("/brief/habit", response_model=BriefHabitResponse)
def get_brief_habit(weeks: int = 4, settings=Depends(get_app_settings)) -> BriefHabitResponse:
    """Weekly visit/note counts — the first read surface for the visit log M1 only wrote.

    Feeds the kickoff's v1 success check (~3 weeks in: ≥5 mornings/week · ≥3 notes/week)
    so the evaluation is a glance at the Today strip, not a manual sqlite dig. ``weeks``
    is clamped in the store layer (1–12). Also carries the PR5 trust gauge: the date of
    the last manual sweep-accuracy re-grade, so trust reads as measured, not assumed."""
    return BriefHabitResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        weeks=[BriefHabitWeek(**w) for w in brief_habit_weeks(weeks)],
        last_graded=_last_graded(settings.trust_log),
    )


@router.post("/brief/notes", response_model=BriefNote)
def create_brief_note(payload: BriefNoteCreate, settings=Depends(get_app_settings)) -> BriefNote:
    try:
        row = add_brief_note(
            item_id=payload.item_id,
            topic_slug=payload.topic_slug,
            brief_date=payload.brief_date,
            item_headline=payload.item_headline,
            body=payload.body,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    row["topic_title"] = topic_title(row["topic_slug"], _roster_titles(settings))
    return BriefNote(**row)


@router.get("/brief/notes", response_model=BriefNotesResponse)
def get_brief_notes(
    topic: Optional[str] = None, settings=Depends(get_app_settings)
) -> BriefNotesResponse:
    """All notes newest-first, optionally filtered to one topic — the browse view."""
    titles = _roster_titles(settings)
    notes = [
        BriefNote(**{**n, "topic_title": topic_title(n["topic_slug"], titles)})
        for n in list_brief_notes(topic_slug=topic)
    ]
    return BriefNotesResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        notes=notes,
    )


@router.delete("/brief/notes/{note_id}", response_model=BriefNoteDeleteResponse)
def remove_brief_note(note_id: int) -> BriefNoteDeleteResponse:
    if not delete_brief_note(note_id):
        raise HTTPException(status_code=404, detail=f"no note with id {note_id}")
    return BriefNoteDeleteResponse(ok=True)


def _resolve_overnight(settings, proposal_id: str) -> dict:
    """The still-``proposed`` proposal, or the honest refusal: 404 for an id the ledger
    has never seen, 409 for one already resolved — resolution is single-shot, so a
    double tap (or a stale tab) can never double a note or flip a decision."""
    proposal = load_queue(settings.brief_overnight_ledger).get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"no overnight proposal {proposal_id}")
    if proposal["status"] != "proposed":
        raise HTTPException(
            status_code=409, detail=f"proposal already {proposal['status']}"
        )
    return proposal


@router.post("/brief/overnight/{proposal_id}/approve", response_model=BriefOvernightProposal)
def approve_overnight_proposal(
    proposal_id: str, settings=Depends(get_app_settings)
) -> BriefOvernightProposal:
    """Approve — the Overnight queue's one real write (v0 scope, 2026-07-20 gate).

    The drafted body lands as a note on the proposal's own item through the EXISTING
    notes path, so it joins the served brief and /notes and stays deletable there like
    any other note; the ledger gets the single-shot resolution row. Nothing external
    is touched — that boundary moves only through a future graded send gate.
    """
    proposal = _resolve_overnight(settings, proposal_id)
    try:
        note = add_brief_note(
            item_id=proposal["item_id"],
            topic_slug=proposal["slug"],
            brief_date=proposal["date"],
            item_headline=proposal["item_headline"],
            body=proposal["body"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    append_status(settings.brief_overnight_ledger, proposal_id, "approved", note_id=note["id"])
    return BriefOvernightProposal(
        **{
            **proposal,
            "title": topic_title(proposal["slug"], _roster_titles(settings)),
            "status": "approved",
            "note_id": note["id"],
        }
    )


@router.post("/brief/overnight/{proposal_id}/discard", response_model=BriefOvernightProposal)
def discard_overnight_proposal(
    proposal_id: str, settings=Depends(get_app_settings)
) -> BriefOvernightProposal:
    """Discard — the undo (v0 scope: nothing external happened, so undo = the draft
    goes away). The proposal keeps its row in the payload wearing ``discarded``; the
    page hides it."""
    proposal = _resolve_overnight(settings, proposal_id)
    append_status(settings.brief_overnight_ledger, proposal_id, "discarded")
    return BriefOvernightProposal(
        **{
            **proposal,
            "title": topic_title(proposal["slug"], _roster_titles(settings)),
            "status": "discarded",
        }
    )


@router.get("/brief/archive", response_model=BriefArchiveResponse)
def get_brief_archive(settings=Depends(get_app_settings)) -> BriefArchiveResponse:
    """All renderable sweep dates, newest-first, with an ``has_audio`` flag.

    Used by the archive index page to build a browsable history list. Dates are
    the same renderable-content-gated set that ``GET /brief?date=`` accepts."""
    sweeps_dir = Path(settings.sweeps_dir)
    dates = list(reversed(sweep_dates(sweeps_dir)))
    entries = [
        BriefArchiveEntry(
            date=d,
            has_audio=(sweeps_dir / d / "brief.mp3").exists(),
        )
        for d in dates
    ]
    return BriefArchiveResponse(dates=entries)
