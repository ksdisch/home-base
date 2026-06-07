"""GET /api/study-plan — the Phase-6 daily, time-boxed, interleaved review session.

Reads the per-question SM-2 queue (`store/mastery.sr_plan_items`), packs the most-overdue
questions into a minute budget, and interleaves the resulting per-quiz segments
(`study/planner.build_study_plan`). Topic labels come from the offline sidecar catalog. Never a
500: an empty store degrades to ``has_data=false``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ..deps import get_app_settings
from ..models import StudyPlanResponse, StudyPlanSegment
from ..store import mastery as store_mastery
from ..study import planner
from .labels import label_map

router = APIRouter()


@router.get("/study-plan", response_model=StudyPlanResponse)
def get_study_plan(
    minutes: int = Query(planner.DEFAULT_MINUTES, description="time budget for the session"),
    settings=Depends(get_app_settings),
) -> StudyPlanResponse:
    budget = planner.clamp_minutes(minutes)
    items = store_mastery.sr_plan_items()
    plan = planner.build_study_plan(items, minutes=budget)
    labels = label_map(settings)

    segments = [
        StudyPlanSegment(
            notebook_id=s["notebook_id"],
            title=labels.get(s["notebook_id"], {}).get("title") or s["notebook_id"],
            quiz_artifact_id=s["quiz_artifact_id"],
            topic_url=labels.get(s["notebook_id"], {}).get("topic_url"),
            item_count=s["item_count"],
            due_count=s["due_count"],
            minutes=s["minutes"],
            priority=s["priority"],
        )
        for s in plan["segments"]
    ]

    return StudyPlanResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=len(items) > 0,
        has_due=plan["has_due"],
        requested_minutes=plan["requested_minutes"],
        total_minutes=plan["total_minutes"],
        total_items=plan["total_items"],
        due_items=plan["due_items"],
        segments=segments,
    )
