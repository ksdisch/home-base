"""GET /api/study-plan — the Phase-6 daily, time-boxed, interleaved review session.

Reads the per-question SM-2 queue (`store/mastery.sr_plan_items`), packs the most-overdue
questions into a minute budget, and interleaves the resulting per-quiz segments
(`study/planner.build_study_plan`). Topic labels come from the offline sidecar catalog; course
segments (``notebook_id='course:<slug>'``) are titled from the on-disk course catalog. Never a
500: an empty store degrades to ``has_data=false``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Mapping, Set, Tuple

from fastapi import APIRouter, Depends, Query

from ..courses import COURSE_NB_PREFIX, CourseError, course_notebook_id, get_course, list_courses
from ..deps import get_app_settings
from ..models import StudyPlanResponse, StudyPlanSegment
from ..store import mastery as store_mastery
from ..study import planner
from .labels import label_map

router = APIRouter()


def course_plan_meta() -> Tuple[Dict[str, Dict[str, str]], Set[Tuple[str, str]]]:
    """One pass over the course catalog for the plan: ``(labels, quiz_keys)``.

    ``labels`` is ``course:<slug> → {title}`` so course segments show the course title, not the raw
    synthetic id. ``quiz_keys`` is the set of ``(course:<slug>, quiz_path)`` for every course *quiz*
    material — the only course rows the plan surfaces. Course flashcard decks share the SM-2 table
    under the same namespace but keep their own review surface, so they're filtered out here (a deck
    path can't be played as a quiz). Best-effort/offline like ``label_map`` — a bad course dir is
    skipped by ``list_courses`` and never 500s the plan."""
    labels: Dict[str, Dict[str, str]] = {}
    quiz_keys: Set[Tuple[str, str]] = set()
    for c in list_courses():
        nb = course_notebook_id(c["slug"])
        labels[nb] = {"title": c["title"]}
        try:
            course = get_course(c["slug"])
        except CourseError:
            continue
        if not course:
            continue
        for m in course["modules"]:
            for lsn in m["lessons"]:
                for mat in lsn["materials"]:
                    if mat.get("type") == "quiz" and isinstance(mat.get("path"), str):
                        quiz_keys.add((nb, mat["path"]))
    return labels, quiz_keys


def _plan_items(quiz_keys: Set[Tuple[str, str]]) -> List[Mapping[str, object]]:
    """The SM-2 queue with topic rows kept as-is and course rows kept only when they're a course
    quiz (course flashcard rows share the table but stay on their own review surface)."""
    return [
        it
        for it in store_mastery.sr_plan_items()
        if not str(it["notebook_id"]).startswith(COURSE_NB_PREFIX)
        or (it["notebook_id"], it["quiz_artifact_id"]) in quiz_keys
    ]


@router.get("/study-plan", response_model=StudyPlanResponse)
def get_study_plan(
    minutes: int = Query(planner.DEFAULT_MINUTES, description="time budget for the session"),
    settings=Depends(get_app_settings),
) -> StudyPlanResponse:
    budget = planner.clamp_minutes(minutes)
    # Topic labels from the sidecar catalog + course labels/quiz-keys from the on-disk course
    # catalog; course notebook ids are ``course:<slug>`` so they never collide with a real one.
    course_labels, quiz_keys = course_plan_meta()
    items = _plan_items(quiz_keys)
    plan = planner.build_study_plan(items, minutes=budget)
    labels = {**label_map(settings), **course_labels}

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
