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

from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..deps import get_app_settings
from ..models import (
    BriefNote,
    BriefNoteCreate,
    BriefNoteDeleteResponse,
    BriefNotesResponse,
    BriefResponse,
    BriefTopic,
    BriefVisitResponse,
)
from ..store import add_brief_note, delete_brief_note, list_brief_notes, record_brief_visit
from ..sweeps import latest_sweep_date, load_brief_topics, load_roster, topic_title

router = APIRouter()


def _roster_titles(settings) -> Dict[str, str]:
    roster = load_roster(settings.roster_file)
    return {t["slug"]: t["title"] for t in roster if t["title"]}


@router.get("/brief", response_model=BriefResponse)
def get_brief(settings=Depends(get_app_settings)) -> BriefResponse:
    date = latest_sweep_date(settings.sweeps_dir)
    roster = load_roster(settings.roster_file)
    raw_topics = load_brief_topics(settings.sweeps_dir, date, roster) if date else []

    # Join the served day's notes onto their items (oldest first — reading order).
    if date and raw_topics:
        titles = {t["slug"]: t["title"] for t in roster if t["title"]}
        notes_by_item: Dict[str, List[dict]] = {}
        for note in reversed(list_brief_notes(brief_date=date)):
            note["topic_title"] = topic_title(note["topic_slug"], titles)
            notes_by_item.setdefault(note["item_id"], []).append(note)
        for topic in raw_topics:
            for item in topic.get("items", []):
                item["notes"] = notes_by_item.get(item["id"], [])

    return BriefResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=len(raw_topics) > 0,
        date=date,
        topics=[BriefTopic(**t) for t in raw_topics],
        audio_available=bool(date) and (settings.sweeps_dir / date / "brief.mp3").is_file(),
    )


@router.get("/brief/audio")
def get_brief_audio(settings=Depends(get_app_settings)) -> FileResponse:
    """The served day's narrated MP3 (M4 — sweeps/audio_brief.py renders it after each sweep).

    404 when the latest sweep has no audio (Kokoro was down, or a pre-M4 day) — the page just
    hides the player. Always the *served* day's file, never a stale mp3 from an older folder.
    """
    date = latest_sweep_date(settings.sweeps_dir)
    path = (settings.sweeps_dir / date / "brief.mp3") if date else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="no audio brief for the latest sweep")
    return FileResponse(path, media_type="audio/mpeg", filename=f"brief-{date}.mp3")


@router.post("/brief/visit", response_model=BriefVisitResponse)
def log_brief_visit() -> BriefVisitResponse:
    row = record_brief_visit()
    return BriefVisitResponse(ok=True, day=row["day"], visited_at=row["visited_at"])


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
