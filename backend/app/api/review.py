"""GET /api/review — the Phase-4 spaced-repetition "Review next" queue.

Reads the mastery signal Phase 2 logs (`topic_mastery`/`question_mastery`), fades it with the
decay model in `store/mastery.py`, and returns a ranked list of what to review now. Topic labels
are resolved from the offline sidecar catalog (same source as `/catalog` and `/progress`); an
unknown notebook falls back to its id. Never a 500: an empty store degrades to ``has_data=false``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends

from ..catalog.build import to_groups
from ..catalog.ingest import load_sidecars
from ..deps import get_app_settings
from ..models import ReviewItem, ReviewResponse
from ..store import mastery as store_mastery

router = APIRouter()


def _label_map(settings) -> Dict[str, Dict[str, str]]:
    """``notebook_id → {title, group, group_label, topic_url}`` from the sidecar catalog.

    Best-effort and offline; if the catalog can't be read we just label by id downstream.
    """
    out: Dict[str, Dict[str, str]] = {}
    try:
        groups = to_groups(load_sidecars(settings.notebooklm_root).sidecars)
    except Exception:  # the queue must never 500 over a catalog hiccup
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


@router.get("/review", response_model=ReviewResponse)
def get_review(settings=Depends(get_app_settings)) -> ReviewResponse:
    labels = _label_map(settings)
    queue = store_mastery.review_queue()

    items = [
        ReviewItem(
            notebook_id=q["notebook_id"],
            title=labels.get(q["notebook_id"], {}).get("title") or q["notebook_id"],
            group=labels.get(q["notebook_id"], {}).get("group"),
            group_label=labels.get(q["notebook_id"], {}).get("group_label"),
            topic_url=labels.get(q["notebook_id"], {}).get("topic_url"),
            mastery=q["mastery"],
            decayed=q["decayed"],
            due=q["due"],
            priority=q["priority"],
            days_since_review=q["days_since_review"],
            total_misses=q["total_misses"],
            shaky_questions=q["shaky_questions"],
            last_review_at=q["last_review_at"],
            reason=q["reason"],
        )
        for q in queue
    ]

    return ReviewResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=len(items) > 0,
        due_count=sum(1 for i in items if i.due),
        items=items,
    )
