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


def _match_truncated(aid: str, truncated_ids: set[str], claimed: set[str]) -> str | None:
    """A truncated sidecar id (``id_complete=False``) is a prefix of the full live id — READMEs
    often shorten artifact ids, so match it to its live id instead of doubling the artifact. Only a
    unique, unclaimed truncated prefix wins; ambiguity falls through to an nlm-only entry."""
    prefixes = [s for s in truncated_ids if s and aid.startswith(s) and s not in claimed]
    return prefixes[0] if len(prefixes) == 1 else None


def reconcile(
    sidecar_artifacts: List[RawArtifact], studio_artifacts: List[Dict[str, Any]]
) -> ReconcileResult:
    # Canonicalize ids on BOTH sides so case/whitespace never splits one artifact into two.
    by_canon: Dict[str, RawArtifact] = {}
    sidecar_ids = set()
    truncated_ids = set()  # id_complete=False ids, eligible to prefix-match a full live id
    for a in sidecar_artifacts:
        c = _canon(a.artifact_id)
        sidecar_ids.add(c)
        by_canon[c] = a
        if not a.id_complete:
            truncated_ids.add(c)

    live_status: Dict[str, str] = {}
    claimed_sidecar_ids = set()  # sidecar ids a live artifact reconciled to (exact or truncated)
    nlm_only: List[str] = []

    for raw in studio_artifacts or []:
        if not isinstance(raw, dict):
            continue  # nlm should return objects; ignore anything else rather than crash
        aid = _canon(raw.get("id"))
        if not aid:  # null / empty / whitespace-only id -> not an artifact
            continue

        raw_status = raw.get("status")
        status = (str(raw_status).strip() or None) if raw_status is not None else None
        ntype = _norm_type(str(raw.get("type", "")))
        if status:
            live_status[aid] = status

        # Reconcile to a sidecar artifact by exact canon id, else a truncated sidecar id that
        # prefixes this full live id, else fall back to an nlm-only entry already created for `aid`.
        key = aid if aid in by_canon else _match_truncated(aid, truncated_ids, claimed_sidecar_ids)
        if key is not None:
            if key in sidecar_ids:
                claimed_sidecar_ids.add(key)
            existing = by_canon[key]
            new_type = existing.type if existing.type != "unknown" else ntype
            by_canon[key] = replace(
                existing,
                type=new_type,
                status=status or existing.status,
                source=(existing.source + "+nlm") if "nlm" not in existing.source else existing.source,
            )
        else:
            nlm_only.append(aid)
            by_canon[aid] = RawArtifact(
                artifact_id=aid,
                type=ntype,
                title="",  # nlm has no title; UI renders "Untitled <type>"
                status=status,
                source="nlm",
            )

    sidecar_only = sorted(sidecar_ids - claimed_sidecar_ids)

    return ReconcileResult(
        artifacts=list(by_canon.values()),
        nlm_only_ids=sorted(nlm_only),
        sidecar_only_ids=sidecar_only,
        live_status=live_status,
        live_missing_ids=sidecar_only,  # in sidecar but not live
    )
