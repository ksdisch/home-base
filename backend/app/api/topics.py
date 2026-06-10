"""GET /api/topics/{id} — topic detail. Sidecar by default; ?live=true reconciles with nlm."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..catalog.build import NOTEBOOKLM_URL, to_topic_detail
from ..catalog.ingest import find_sidecar
from ..catalog.reconcile import reconcile
from ..deps import get_app_settings, get_nlm_client
from ..models import AuthState, StudyGuideResponse, TopicDetail
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


@router.get(
    "/topics/{notebook_id}/study-guides/{artifact_id}",
    response_model=StudyGuideResponse,
)
def get_study_guide(
    notebook_id: str,
    artifact_id: str,
    settings=Depends(get_app_settings),
    nlm: NlmClient = Depends(get_nlm_client),
) -> StudyGuideResponse:
    """Fetch a study guide's Markdown for the in-hub reader.

    Same degrade contract as the quiz player's prepare: an `nlm` sign-in lapse becomes a calm
    auth banner and a download failure a calm error string — never a 500.
    """
    sidecar = find_sidecar(settings.notebooklm_root, notebook_id)
    if sidecar is None:
        raise HTTPException(status_code=404, detail="Notebook not found in sidecars.")

    # The sidecar's title (the doc's own H1 often differs); an id the sidecar doesn't know is
    # tolerated — downloadability is proven by the fetch itself, exactly like quiz prepare.
    # The lookup is case/whitespace-insensitive so an id VARIANT of a known quiz can't slip
    # past the type guard below while still resolving to the same artifact at nlm.
    wanted = artifact_id.strip().lower()
    known = next(
        (a for a in sidecar.artifacts if a.artifact_id.strip().lower() == wanted), None
    )
    title = known.title.strip() or None if known else None
    base = dict(
        notebook_id=notebook_id,
        artifact_id=artifact_id,
        title=title,
        notebooklm_url=NOTEBOOKLM_URL.format(notebook_id),
    )

    # Defense in depth for the answer-key-free invariant: a KNOWN non-study-guide id (above all
    # a quiz, whose keyed JSON must never reach a client verbatim) is refused before any fetch,
    # rather than trusting `nlm download report --id` to reject a cross-typed artifact.
    if known is not None and known.type != "study_guide":
        return StudyGuideResponse(
            **base, ok=False, error="Couldn't load this study guide: not a study guide artifact."
        )

    try:
        markdown = nlm.download_study_guide(notebook_id, artifact_id)
    except NlmAuthError as e:
        return StudyGuideResponse(
            **base, ok=False, auth=AuthState(ok=False, message=e.user_message)
        )
    except NlmError as e:
        msg = getattr(e, "user_message", None) or str(e)
        return StudyGuideResponse(**base, ok=False, error=f"Couldn't load this study guide: {msg}")

    if not markdown.strip():
        return StudyGuideResponse(
            **base, ok=False, error="Couldn't load this study guide: nlm returned an empty file."
        )
    return StudyGuideResponse(**base, ok=True, markdown=markdown)
