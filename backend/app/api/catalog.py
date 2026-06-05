"""GET /api/catalog — the hub home feed. Sidecar-only (fast, offline, no auth dependency)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..catalog.build import to_groups
from ..catalog.ingest import load_sidecars
from ..deps import get_app_settings
from ..models import AuthState, CatalogResponse

router = APIRouter()


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog(settings=Depends(get_app_settings)) -> CatalogResponse:
    load = load_sidecars(settings.notebooklm_root)
    return CatalogResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        groups=to_groups(load.sidecars),
        auth=AuthState(ok=True),
        warnings=load.warnings,
        notebooklm_root=str(settings.notebooklm_root),
    )
