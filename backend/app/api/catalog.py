"""GET /api/catalog — the hub home feed. Sidecar-only (fast, offline, no auth dependency).

The cards are pure sidecar data; Phase 4 stamps each one's decayed-mastery signal
(``mastery`` / ``due_for_review`` / ``last_touched``) from the hub store on top, so the home
screen can show a calm "🔁 due for review" nudge + a mastery chip without the pure card builder
needing DB access.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..catalog.build import to_groups
from ..catalog.ingest import load_sidecars
from ..deps import get_app_settings
from ..models import AuthState, CatalogResponse
from ..store import mastery as store_mastery

router = APIRouter()


def _stamp_mastery(groups) -> None:
    """Fill each card's decayed mastery / due / last-touched from the store (best-effort)."""
    try:
        by_topic = store_mastery.due_topic_ids()
    except Exception:  # the home feed must never 500 over the store
        return
    for g in groups:
        for card in g.notebooks:
            info = by_topic.get(card.notebook_id)
            if info is None:
                continue
            card.mastery = info["mastery"]
            card.due_for_review = info["due"]
            card.last_touched = info["last_review_at"]


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog(settings=Depends(get_app_settings)) -> CatalogResponse:
    load = load_sidecars(settings.notebooklm_root)
    groups = to_groups(load.sidecars)
    _stamp_mastery(groups)
    return CatalogResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        groups=groups,
        auth=AuthState(ok=True),
        warnings=load.warnings,
        notebooklm_root=str(settings.notebooklm_root),
    )
