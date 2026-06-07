"""GET /api/reflections — the post-episode reflection journal (Phase 6).

The `/episode-review` skill has long *written* reflections (body + optional 1–5 grasp rating);
nothing read them back until now. This surfaces them newest-first with topic labels and an
average grasp, so the hub becomes a place you can revisit "what did past-me say didn't land?".
Read-only; never a 500 — an empty store degrades to ``has_data=false``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..deps import get_app_settings
from ..models import ReflectionItem, ReflectionsResponse
from ..store import list_reflections
from .labels import label_map

router = APIRouter()


@router.get("/reflections", response_model=ReflectionsResponse)
def get_reflections(
    notebook_id: Optional[str] = Query(None, description="filter to one notebook"),
    limit: int = Query(50, description="max reflections to return"),
    settings=Depends(get_app_settings),
) -> ReflectionsResponse:
    rows = list_reflections(notebook_id, limit=limit)
    labels = label_map(settings)

    items = [
        ReflectionItem(
            id=r["id"],
            notebook_id=r["notebook_id"],
            title=labels.get(r["notebook_id"], {}).get("title") or r["notebook_id"],
            episode_artifact_id=r["episode_artifact_id"],
            body=r["body"],
            grasp_rating=r["grasp_rating"],
            created_at=r["created_at"],
            topic_url=labels.get(r["notebook_id"], {}).get("topic_url"),
        )
        for r in rows
    ]

    grasps = [r["grasp_rating"] for r in rows if r["grasp_rating"] is not None]
    avg_grasp = round(sum(grasps) / len(grasps), 2) if grasps else None

    return ReflectionsResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        has_data=len(items) > 0,
        count=len(items),
        avg_grasp=avg_grasp,
        items=items,
    )
