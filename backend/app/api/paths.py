"""GET /api/paths/{notebook_id} + per-step coverage/confidence writes (M8).

A path is a generated sidecar over a NotebookLM topic (see ``app.paths``); this router merges the
learner's three axes onto it: **coverage** (``path_step_progress``), **recall** (the shared SM-2
store — the exact read the home card uses), and **confidence** (``path_confidence``). A step's
"Start" launches the topic's REAL artifact surfaces (quiz/flashcards/audio/study-guide) via the
existing routes, and those already write mastery — so this router only owns coverage + confidence.
The bridge-check grade (the one LLM step) is a separate endpoint added in Phase 3b."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from ..models import PathResponse, PathStep, StepComplete, StepConfidence
from ..paths import PathError, get_path
from ..store import db
from ..store import mastery as store_mastery

router = APIRouter()


def _mastery_for(notebook_id: str) -> Optional[float]:
    """The topic's decayed SM-2 mastery, or ``None`` — the same signal the home card shows. A path
    must never 500 over the store, so any store hiccup degrades to ``None`` (an honest em-dash)."""
    try:
        return store_mastery.due_topic_ids().get(notebook_id, {}).get("mastery")
    except Exception:
        return None


def _load_or_404(notebook_id: str) -> Dict[str, Any]:
    try:
        raw = get_path(notebook_id)
    except PathError as e:
        raise HTTPException(status_code=422, detail=f"malformed path: {e}")
    if raw is None:
        raise HTTPException(status_code=404, detail="No learning path for this topic yet.")
    return raw


def _require_step(raw: Dict[str, Any], step_id: str) -> None:
    if step_id not in {s["id"] for s in raw["steps"]}:
        raise HTTPException(status_code=404, detail="No such step in this path.")


def _build_response(notebook_id: str, raw: Dict[str, Any]) -> PathResponse:
    """Merge the three axes onto the on-disk path: coverage + confidence from the store, mastery
    from the shared SM-2 read. Used by the GET and both write endpoints (one contract, always fresh)."""
    done = db.get_path_progress(notebook_id)
    conf = db.get_path_confidence(notebook_id)
    steps = [
        PathStep(**s, completed=bool(done.get(s["id"])), confidence=conf.get(s["id"]))
        for s in raw["steps"]
    ]
    total = len(steps)
    completed = sum(1 for s in steps if s.completed)
    ratings = [conf[s["id"]] for s in raw["steps"] if s["id"] in conf]
    conf_avg = round(sum(ratings) / len(ratings), 1) if ratings else None
    return PathResponse(
        notebook_id=raw["notebook_id"],
        title=raw["title"],
        topic=raw["topic"],
        generated_at=raw["generated_at"],
        generator=raw["generator"],
        steps=steps,
        step_count=total,
        completed_steps=completed,
        progress_pct=round(completed / total * 100) if total else 0,
        mastery=_mastery_for(notebook_id),
        confidence=conf_avg,
    )


@router.get("/paths/{notebook_id}", response_model=PathResponse)
def get_learning_path(notebook_id: str) -> PathResponse:
    return _build_response(notebook_id, _load_or_404(notebook_id))


@router.post("/paths/{notebook_id}/steps/{step_id}/complete", response_model=PathResponse)
def complete_step(notebook_id: str, step_id: str, body: StepComplete) -> PathResponse:
    raw = _load_or_404(notebook_id)
    _require_step(raw, step_id)
    db.set_step_completed(notebook_id, step_id, body.completed)
    return _build_response(notebook_id, raw)


@router.post("/paths/{notebook_id}/steps/{step_id}/confidence", response_model=PathResponse)
def rate_step(notebook_id: str, step_id: str, body: StepConfidence) -> PathResponse:
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=422, detail="rating must be 1-5")
    raw = _load_or_404(notebook_id)
    _require_step(raw, step_id)
    db.set_step_confidence(notebook_id, step_id, body.rating)
    return _build_response(notebook_id, raw)
