"""Custom (non-NotebookLM) topics — the Phase-5 HTTP surface over the existing store writer.

A book, a YouTube series, a loose interest: tracked loosely with manual progress + notes. The
store helpers (`app.store.db`) already validate and log activity; this router is thin —
``ValueError`` from the store → 400, an unknown id → 404. Like all hub state these live in the
hub's SQLite, never the NotebookLM sidecars.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..models import (
    CustomTopic,
    CustomTopicCreate,
    CustomTopicsResponse,
    CustomTopicUpdate,
)
from ..store import (
    add_custom_topic,
    list_custom_topics,
    update_custom_topic,
)

router = APIRouter()


@router.get("/custom-topics", response_model=CustomTopicsResponse)
def get_custom_topics() -> CustomTopicsResponse:
    return CustomTopicsResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        topics=[CustomTopic(**t) for t in list_custom_topics()],
    )


@router.post("/custom-topics", response_model=CustomTopic, status_code=201)
def create_custom_topic(body: CustomTopicCreate) -> CustomTopic:
    try:
        topic = add_custom_topic(
            body.title, notes=body.notes, progress_pct=body.progress_pct
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CustomTopic(**topic)


@router.patch("/custom-topics/{topic_id}", response_model=CustomTopic)
def patch_custom_topic(topic_id: int, body: CustomTopicUpdate) -> CustomTopic:
    try:
        updated = update_custom_topic(
            topic_id,
            title=body.title,
            notes=body.notes,
            progress_pct=body.progress_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No custom topic with id {topic_id}.")
    return CustomTopic(**updated)
