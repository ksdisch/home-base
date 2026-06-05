"""Convert parsed sidecars (+ optional live reconcile) into API contract models."""

from __future__ import annotations

from typing import Dict, List, Optional

from ..models import (
    ArtifactRef,
    Episode,
    Group,
    NotebookCard,
    QuizRef,
    TopicDetail,
)
from .grouping import GROUP_LABELS, GROUP_ORDER
from .markdown_tables import TYPE_LABELS, RawArtifact
from .sidecar import ParsedSidecar

NOTEBOOKLM_URL = "https://notebooklm.google.com/notebook/{}"


def _display_title(a: RawArtifact) -> str:
    if a.title.strip():
        return a.title.strip()
    label = TYPE_LABELS.get(a.type, "Artifact")
    if a.episode is not None:
        return f"Ep {a.episode} — {label}"
    return f"Untitled {label}"


def _counts(artifacts: List[RawArtifact]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for a in artifacts:
        key = {"audio": "audio", "quiz": "quizzes", "study_guide": "study_guides"}.get(
            a.type, a.type
        )
        counts[key] = counts.get(key, 0) + 1
    counts["total"] = len(artifacts)
    return counts


def to_card(sc: ParsedSidecar) -> NotebookCard:
    return NotebookCard(
        notebook_id=sc.notebook_id,
        alias=sc.alias,
        title=sc.title,
        group=sc.group,
        group_label=GROUP_LABELS.get(sc.group, sc.group.title()),
        template=sc.template,
        tags=sc.tags,
        archived=sc.archived,
        notebooklm_url=NOTEBOOKLM_URL.format(sc.notebook_id),
        topic_url=f"/topics/{sc.notebook_id}",
        counts=_counts(sc.artifacts),
    )


def to_groups(sidecars: List[ParsedSidecar]) -> List[Group]:
    buckets: Dict[str, List[NotebookCard]] = {k: [] for k in GROUP_ORDER}
    for sc in sidecars:
        buckets.setdefault(sc.group, []).append(to_card(sc))
    for cards in buckets.values():
        # Active first, archived last; then by title.
        cards.sort(key=lambda c: (c.archived, c.title.lower()))
    return [
        Group(key=k, label=GROUP_LABELS.get(k, k.title()), notebooks=buckets.get(k, []))
        for k in GROUP_ORDER
    ]


def _episode_model(a: RawArtifact, listened: Dict[str, bool]) -> Episode:
    return Episode(
        n=a.episode,
        title=_display_title(a),
        artifact_id=a.artifact_id,
        fmt=a.fmt,
        length=a.length,
        status=a.status,
        listened=listened.get(a.artifact_id, False),
        source=a.source,
    )


def _artifact_ref(a: RawArtifact) -> ArtifactRef:
    return ArtifactRef(
        n=a.episode,
        title=_display_title(a),
        artifact_id=a.artifact_id,
        type=a.type,
        status=a.status,
        source=a.source,
    )


def to_topic_detail(
    sc: ParsedSidecar,
    artifacts: List[RawArtifact],
    listened: Optional[Dict[str, bool]] = None,
    *,
    live: bool = False,
) -> TopicDetail:
    listened = listened or {}

    episodes: List[Episode] = []
    standalones: List[Episode] = []
    study_guides: List[ArtifactRef] = []
    quizzes: List[QuizRef] = []
    other: List[ArtifactRef] = []

    for a in artifacts:
        if a.type == "audio":
            (episodes if a.episode is not None else standalones).append(
                _episode_model(a, listened)
            )
        elif a.type == "study_guide":
            study_guides.append(_artifact_ref(a))
        elif a.type == "quiz":
            ref = _artifact_ref(a)
            quizzes.append(QuizRef(**ref.model_dump(), takeable=False))
        else:
            other.append(_artifact_ref(a))

    episodes.sort(key=lambda e: (e.n if e.n is not None else 9999, e.title.lower()))
    standalones.sort(key=lambda e: e.title.lower())
    study_guides.sort(key=lambda r: (r.n if r.n is not None else 9999, r.title.lower()))
    quizzes.sort(key=lambda r: (r.n if r.n is not None else 9999, r.title.lower()))
    other.sort(key=lambda r: (r.type, r.title.lower()))

    return TopicDetail(
        notebook_id=sc.notebook_id,
        alias=sc.alias,
        title=sc.title,
        group=sc.group,
        group_label=GROUP_LABELS.get(sc.group, sc.group.title()),
        template=sc.template,
        tags=sc.tags,
        archived=sc.archived,
        merged_into=sc.merged_into,
        source_count=sc.source_count,
        notebooklm_url=NOTEBOOKLM_URL.format(sc.notebook_id),
        episodes=episodes,
        standalones=standalones,
        study_guides=study_guides,
        quizzes=quizzes,
        other_artifacts=other,
        counts=_counts(artifacts),
        live=live,
    )
