"""GET /api/paths/{notebook_id} + per-step coverage/confidence writes (M8).

A path is a generated sidecar over a NotebookLM topic (see ``app.paths``); this router merges the
learner's three axes onto it: **coverage** (``path_step_progress``), **recall** (the shared SM-2
store — the exact read the home card uses), and **confidence** (``path_confidence``). A step's
"Start" launches the topic's REAL artifact surfaces (quiz/flashcards/audio/study-guide) via the
existing routes, and those already write mastery — so this router only owns coverage + confidence.
The bridge-check grade (the one LLM step) is a separate endpoint added in Phase 3b."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..catalog.ingest import find_sidecar
from ..chat import BriefChatClient, append_chat_ledger
from ..config import get_settings
from ..deps import get_app_settings, get_brief_chat_client, get_path_designer_client
from ..models import (
    BridgeGradeRequest,
    BridgeGradeResponse,
    PathGenerateResponse,
    PathResponse,
    PathsResponse,
    PathStep,
    PathSummary,
    StepComplete,
    StepConfidence,
)
from ..paths import PathError, get_path, list_path_ids, path_file, write_path_file
from ..paths.designer import compose_path
from ..paths.grader import grade_bridge, max_answer_chars
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


@router.get("/paths", response_model=PathsResponse)
def list_learning_paths() -> PathsResponse:
    """All composed learning paths + their resume point — the Plan **Continue** lane (design
    decision 6): coverage progress and the next incomplete step per path, non-empty day one via the
    bundled example. A malformed path file is listed by id but skipped here (never a 500), mirroring
    the loader's tolerant posture. Still-in-progress paths sort first, then by title (stable)."""
    items: list[PathSummary] = []
    for nid in list_path_ids():
        try:
            raw = get_path(nid)
        except PathError:
            continue  # a malformed file is skipped, like the manifest list
        if raw is None:
            continue
        done = db.get_path_progress(nid)
        conf = db.get_path_confidence(nid)
        steps = raw["steps"]
        total = len(steps)
        completed = sum(1 for s in steps if done.get(s["id"]))
        next_raw = next((s for s in steps if not done.get(s["id"])), None)
        ratings = [conf[s["id"]] for s in steps if s["id"] in conf]
        items.append(
            PathSummary(
                notebook_id=raw["notebook_id"],
                title=raw["title"],
                topic=raw.get("topic", "") or "",
                step_count=total,
                completed_steps=completed,
                progress_pct=round(completed / total * 100) if total else 0,
                next_step=PathStep(**next_raw) if next_raw else None,
                confidence=round(sum(ratings) / len(ratings), 1) if ratings else None,
            )
        )
    items.sort(key=lambda it: (it.next_step is None, it.title.lower()))
    return PathsResponse(generated_at=datetime.now(timezone.utc).isoformat(), items=items)


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


@router.post("/paths/{notebook_id}/steps/{step_id}/bridge", response_model=BridgeGradeResponse)
def grade_bridge_step(
    notebook_id: str,
    step_id: str,
    body: BridgeGradeRequest,
    client: BriefChatClient = Depends(get_brief_chat_client),
) -> BridgeGradeResponse:
    """Grade a bridge-check answer formatively on the M5 lane, then mark the step done (coverage).
    Never moves mastery; a claude hiccup degrades to ``ok=False`` (200), never a 500."""
    raw = _load_or_404(notebook_id)
    step = next((s for s in raw["steps"] if s["id"] == step_id), None)
    if step is None:
        raise HTTPException(status_code=404, detail="No such step in this path.")
    if step["kind"] != "bridge":
        raise HTTPException(status_code=400, detail="This step is not a bridge-check.")
    answer = body.answer.strip()
    if not answer:
        raise HTTPException(status_code=422, detail="answer must not be empty")

    result = grade_bridge(
        client,
        topic_title=raw["title"],
        question=step.get("body") or step["title"],
        answer=answer[: max_answer_chars()],
    )
    # Formative: mark the step done on submit (coverage) regardless of the grade — a bridge never
    # moves mastery. Confidence is a separate self-rating the UI prompts for afterwards.
    db.set_step_completed(notebook_id, step_id, True)
    append_chat_ledger(
        get_settings().paths_grade_ledger,
        brief_date="",
        topic_slug=notebook_id,
        item_id=step_id,
        model=client.model,
        envelope=result.get("envelope"),
        error=result.get("error"),
    )
    return BridgeGradeResponse(
        ok=result["ok"],
        feedback=result["feedback"],
        error=result["error"],
        path=_build_response(notebook_id, raw),
    )


@router.post("/paths/{notebook_id}/generate", response_model=PathGenerateResponse)
def generate_path(
    notebook_id: str,
    replace: bool = False,
    client: BriefChatClient = Depends(get_path_designer_client),
    settings=Depends(get_app_settings),
) -> PathGenerateResponse:
    """Compose a path over this topic's REAL artifacts on the M5 lane (design decision 9). Every
    artifact-backed step is validated against the catalog (the M0 no-fabrication bar); the sidecar
    is written ONLY when the whole path is clean — a fabricated id, unparseable output, or a claude
    hiccup all return a calm ``ok=False`` (never a 500). On success returns the fresh three-axis path
    so the card lights up without a refetch. Every run (success or failure) appends a usage row.

    Generating is a REPLACE, so it refuses (409) when this topic already has a path unless
    ``replace=true`` says so out loud. A path can be hand-authored — richer than anything the
    Designer emits — and the refusal is what makes an accidental Generate survivable: the card's
    Generate button is the only control on a state a transient GET failure can reach. The check
    runs before the designer call, so refusing costs neither a minute nor a cent. It keys on
    ``path_file`` (the examples ∪ user union), so shadowing a bundled example is a deliberate act
    too; ``write_path_file`` still keeps a ``.bak`` when a confirmed replace lands."""
    sidecar = find_sidecar(settings.notebooklm_root, notebook_id)
    if sidecar is None:
        raise HTTPException(status_code=404, detail="Notebook not found in sidecars.")

    if not replace and path_file(notebook_id) is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This topic already has a learning path. Generating replaces it — "
                "retry with replace=true to confirm."
            ),
        )

    artifacts = [{"id": a.artifact_id, "type": a.type, "title": a.title} for a in sidecar.artifacts]
    result = compose_path(
        client, notebook_id=notebook_id, topic_title=sidecar.title, artifacts=artifacts
    )

    env = result.get("envelope") or {}
    ledger_error = result.get("error") or (
        "; ".join(result["errors"]) if result.get("errors") else None
    )
    append_chat_ledger(
        settings.paths_generate_ledger,
        brief_date="",
        topic_slug=notebook_id,
        item_id="generate",
        model=client.model,
        envelope=result.get("envelope"),
        error=ledger_error,
    )

    if not result["ok"]:
        return PathGenerateResponse(
            ok=False,
            error=result.get("error"),
            errors=result.get("errors", []),
            total_cost_usd=env.get("total_cost_usd"),
            duration_ms=env.get("duration_ms"),
        )

    write_path_file(notebook_id, result["raw"])
    return PathGenerateResponse(
        ok=True,
        path=_build_response(notebook_id, _load_or_404(notebook_id)),
        total_cost_usd=env.get("total_cost_usd"),
        duration_ms=env.get("duration_ms"),
    )
