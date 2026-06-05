"""GET /api/topics/{id} — topic detail. Sidecar by default; ?live=true reconciles with nlm."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..catalog.build import to_topic_detail
from ..catalog.ingest import find_sidecar
from ..catalog.reconcile import reconcile
from ..deps import get_app_settings, get_nlm_client
from ..models import AuthState, TopicDetail
from ..nlm import NlmAuthError, NlmClient, NlmError
from ..store import get_episode_progress

router = APIRouter()


@router.get("/topics/{notebook_id}", response_model=TopicDetail)
def get_topic(
    notebook_id: str,
    live: bool = False,
    settings=Depends(get_app_settings),
    nlm: NlmClient = Depends(get_nlm_client),
) -> TopicDetail:
    sidecar = find_sidecar(settings.notebooklm_root, notebook_id)
    if sidecar is None:
        raise HTTPException(status_code=404, detail="Notebook not found in sidecars.")

    artifacts = list(sidecar.artifacts)
    auth = AuthState(ok=True)
    warnings: list[str] = list(sidecar.warnings)
    used_live = False

    if live:
        try:
            studio = nlm.studio_status(notebook_id)
            result = reconcile(sidecar.artifacts, studio)
            artifacts = result.artifacts
            used_live = True
            if result.nlm_only_ids:
                warnings.append(
                    f"{len(result.nlm_only_ids)} artifact(s) found live but not in the sidecar."
                )
        except NlmAuthError as e:
            auth = AuthState(ok=False, message=e.user_message)
            warnings.append("Live refresh skipped: " + e.user_message)
        except NlmError as e:
            auth = AuthState(ok=False, message=e.user_message)
            warnings.append("Live refresh failed: " + e.user_message)

    try:
        listened = get_episode_progress(notebook_id)
    except Exception:
        listened = {}

    detail = to_topic_detail(sidecar, artifacts, listened, live=used_live)
    detail.auth = auth
    detail.warnings = warnings
    return detail
