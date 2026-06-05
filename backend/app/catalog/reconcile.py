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


def _canon(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def reconcile(
    sidecar_artifacts: List[RawArtifact], studio_artifacts: List[Dict[str, Any]]
) -> ReconcileResult:
    # Canonicalize ids on BOTH sides so case/whitespace never splits one artifact into two.
    by_canon: Dict[str, RawArtifact] = {}
    sidecar_ids = set()
    for a in sidecar_artifacts:
        c = _canon(a.artifact_id)
        sidecar_ids.add(c)
        by_canon[c] = a

    live_ids = set()
    live_status: Dict[str, str] = {}

    for raw in studio_artifacts or []:
        if not isinstance(raw, dict):
            continue  # nlm should return objects; ignore anything else rather than crash
        aid = _canon(raw.get("id"))
        if not aid:  # null / empty / whitespace-only id -> not an artifact
            continue
        live_ids.add(aid)

        raw_status = raw.get("status")
        status = (str(raw_status).strip() or None) if raw_status is not None else None
        ntype = _norm_type(str(raw.get("type", "")))
        if status:
            live_status[aid] = status

        if aid in by_canon:
            existing = by_canon[aid]
            new_type = existing.type if existing.type != "unknown" else ntype
            by_canon[aid] = replace(
                existing,
                type=new_type,
                status=status or existing.status,
                source=(existing.source + "+nlm") if "nlm" not in existing.source else existing.source,
            )
        else:
            by_canon[aid] = RawArtifact(
                artifact_id=aid,
                type=ntype,
                title="",  # nlm has no title; UI renders "Untitled <type>"
                status=status,
                source="nlm",
            )

    nlm_only = sorted(aid for aid in live_ids if aid not in sidecar_ids)
    sidecar_only = sorted(sidecar_ids - live_ids)

    return ReconcileResult(
        artifacts=list(by_canon.values()),
        nlm_only_ids=nlm_only,
        sidecar_only_ids=sidecar_only,
        live_status=live_status,
        live_missing_ids=sidecar_only,  # in sidecar but not live
    )
