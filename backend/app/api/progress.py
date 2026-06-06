"""GET /api/progress — the Phase-3 progress dashboard feed.

Reads the signal Phase 2 logs (`attempts`, `question_mastery`, `activity`) back into a calm
summary: per-topic score trends, an activity streak, and the shakiest quizzes. Topic labels are
resolved from the sidecar catalog (offline, no auth — same source as `/catalog`); an unknown
notebook falls back to its id. Never a 500: an empty store degrades to ``has_data=false``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends

from ..catalog.build import to_groups
from ..catalog.ingest import load_sidecars
from ..deps import get_app_settings
from ..models import (
    ActivityDay,
    AttemptPoint,
    ProgressResponse,
    ProgressSummary,
    ShakyQuiz,
    TopicProgress,
)
from ..store import progress as store_progress

router = APIRouter()

# How many trailing days the activity strip shows.
ACTIVITY_DAYS_BACK = 35


def _label_map(settings) -> Dict[str, Dict[str, str]]:
    """``notebook_id → {title, group, group_label, topic_url}`` from the sidecar catalog.

    Best-effort and offline; if the catalog can't be read we just label by id downstream.
    """
    out: Dict[str, Dict[str, str]] = {}
    try:
        groups = to_groups(load_sidecars(settings.notebooklm_root).sidecars)
    except Exception:  # the dashboard must never 500 over a catalog hiccup
        return out
    for g in groups:
        for nb in g.notebooks:
            out[nb.notebook_id] = {
                "title": nb.title,
                "group": nb.group,
                "group_label": nb.group_label,
                "topic_url": nb.topic_url,
            }
    return out


@router.get("/progress", response_model=ProgressResponse)
def get_progress(settings=Depends(get_app_settings)) -> ProgressResponse:
    labels = _label_map(settings)

    def label(notebook_id: str) -> Dict[str, str]:
        return labels.get(notebook_id, {})

    summary_raw = store_progress.overall_summary()
    today = datetime.now(timezone.utc).date()
    current, longest = store_progress.compute_streaks(
        store_progress.activity_days(), today
    )

    topics = [
        TopicProgress(
            notebook_id=t["notebook_id"],
            title=label(t["notebook_id"]).get("title") or t["notebook_id"],
            group=label(t["notebook_id"]).get("group"),
            group_label=label(t["notebook_id"]).get("group_label"),
            topic_url=label(t["notebook_id"]).get("topic_url"),
            attempts=t["attempts"],
            last_pct=t["last_pct"],
            best_pct=t["best_pct"],
            avg_pct=t["avg_pct"],
            last_practiced=t["last_practiced"],
            points=[AttemptPoint(**p) for p in t["points"]],
        )
        for t in store_progress.topic_breakdowns()
    ]

    shaky = [
        ShakyQuiz(
            notebook_id=s["notebook_id"],
            title=label(s["notebook_id"]).get("title") or s["notebook_id"],
            topic_url=label(s["notebook_id"]).get("topic_url"),
            quiz_artifact_id=s["quiz_artifact_id"],
            total_misses=s["total_misses"],
            shaky_questions=s["shaky_questions"],
            last_review_at=s["last_review_at"],
        )
        for s in store_progress.shaky_quizzes()
    ]

    activity = [
        ActivityDay(**a)
        for a in store_progress.activity_counts(ACTIVITY_DAYS_BACK, today)
    ]

    return ProgressResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=summary_raw["attempts_total"] > 0,
        summary=ProgressSummary(
            attempts_total=summary_raw["attempts_total"],
            topics_practiced=summary_raw["topics_practiced"],
            avg_pct=summary_raw["avg_pct"],
            current_streak=current,
            longest_streak=longest,
            last_activity=summary_raw["last_activity"],
        ),
        topics=topics,
        shaky=shaky,
        activity=activity,
    )
