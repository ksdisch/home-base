"""Health + nlm reachability (used by the UI to show a calm 'connected' state)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_app_settings, get_nlm_client
from ..models import HealthResponse
from ..nlm import NlmClient, NlmError

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(
    settings=Depends(get_app_settings), nlm: NlmClient = Depends(get_nlm_client)
) -> HealthResponse:
    nlm_version = None
    nlm_available = False
    try:
        nlm_version = nlm.version()
        nlm_available = True
    except NlmError:
        nlm_available = False
    return HealthResponse(
        ok=True,
        nlm_available=nlm_available,
        nlm_version=nlm_version,
        notebooklm_root=str(settings.notebooklm_root),
        root_exists=settings.notebooklm_root.exists(),
    )
