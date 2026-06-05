"""Pure reconciliation of sidecar artifacts against a live ``nlm studio status`` listing.

No network here — the caller fetches the studio list and passes it in, so this stays a pure,
unit-testable function. Rules:
  * artifact in BOTH  -> keep the sidecar's rich title, refresh status, mark live-confirmed.
  * artifact in nlm ONLY -> surface it (typed from nlm, ``Untitled <type>``), never invent a title.
  * artifact in sidecar ONLY -> keep it, flag ``live_missing`` (may be stale/deleted upstream).
Nothing is silently dropped in either direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List

from .markdown_tables import RawArtifact

# nlm studio-status `type` strings already match our vocabulary; normalize a couple aliases.
_NLM_TYPE_ALIASES = {
    "audio_overview": "audio",
    "study_guide": "study_guide",
    "mindmap": "mind_map",
    "mind_map": "mind_map",
    "slides": "slide_deck",
    "slide_deck": "slide_deck",
}


@dataclass
class ReconcileResult:
    artifacts: List[RawArtifact]
    nlm_only_ids: List[str] = field(default_factory=list)
    sidecar_only_ids: List[str] = field(default_factory=list)
    live_status: Dict[str, str] = field(default_factory=dict)  # id -> nlm status
    live_missing_ids: List[str] = field(default_factory=list)


def _norm_type(t: str) -> str:
    t = (t or "").lower()
    return _NLM_TYPE_ALIASES.get(t, t or "unknown")


def reconcile(
    sidecar_artifacts: List[RawArtifact], studio_artifacts: List[Dict[str, Any]]
) -> ReconcileResult:
    by_id: Dict[str, RawArtifact] = {a.artifact_id: a for a in sidecar_artifacts}
    live_ids = set()
    live_status: Dict[str, str] = {}

    for raw in studio_artifacts or []:
        aid = str(raw.get("id", "")).lower()
        if not aid:
            continue
        live_ids.add(aid)
        status = str(raw.get("status", "")) or None
        ntype = _norm_type(str(raw.get("type", "")))
        if status:
            live_status[aid] = status

        if aid in by_id:
            existing = by_id[aid]
            new_type = existing.type if existing.type != "unknown" else ntype
            by_id[aid] = replace(
                existing,
                type=new_type,
                status=status or existing.status,
                source=(existing.source + "+nlm") if "nlm" not in existing.source else existing.source,
            )
        else:
            by_id[aid] = RawArtifact(
                artifact_id=aid,
                type=ntype,
                title="",  # nlm has no title; UI renders "Untitled <type>"
                status=status,
                source="nlm",
            )

    nlm_only = sorted(aid for aid in live_ids if all(
        aid != a.artifact_id for a in sidecar_artifacts))
    sidecar_ids = {a.artifact_id for a in sidecar_artifacts}
    sidecar_only = sorted(sidecar_ids - live_ids)
    live_missing = sidecar_only  # in sidecar but not live

    return ReconcileResult(
        artifacts=list(by_id.values()),
        nlm_only_ids=nlm_only,
        sidecar_only_ids=sorted(sidecar_ids - live_ids),
        live_status=live_status,
        live_missing_ids=live_missing,
    )
