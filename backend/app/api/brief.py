"""GET /api/brief + POST /api/brief/visit — the Today page (M1).

Serves the newest data/sweeps/<date>/ folder: structured topics from <topic>.json, with an
honest raw-markdown fallback for md-only days (the pre-JSON era) or an unreadable json — a
topic is never silently dropped. Never a 500 on missing data: no sweeps yet degrades to
``has_data=false`` and the page tells you to run ``make sweep``. The visit log is the
kickoff's habit metric (opened ≥5 mornings/week); M1 only writes it — read it via sqlite.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..deps import get_app_settings
from ..models import BriefResponse, BriefTopic, BriefVisitResponse
from ..store import record_brief_visit
from ..sweeps import latest_sweep_date, load_brief_topics

router = APIRouter()


@router.get("/brief", response_model=BriefResponse)
def get_brief(settings=Depends(get_app_settings)) -> BriefResponse:
    date = latest_sweep_date(settings.sweeps_dir)
    raw_topics = load_brief_topics(settings.sweeps_dir, date) if date else []
    return BriefResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=len(raw_topics) > 0,
        date=date,
        topics=[BriefTopic(**t) for t in raw_topics],
    )


@router.post("/brief/visit", response_model=BriefVisitResponse)
def log_brief_visit() -> BriefVisitResponse:
    row = record_brief_visit()
    return BriefVisitResponse(ok=True, day=row["day"], visited_at=row["visited_at"])
