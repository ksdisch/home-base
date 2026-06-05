"""Parse ``artifacts/audio-series-artifact-map.json`` into RawArtifacts.

The map's *documented* shape is ``{audio:{}, study_guides:{}, quizzes:{}}`` keyed by episode,
but real maps also carry extra keys (``wave2_audio_*``, ``standalones_created``,
``deferred_audio``) — and engineering-abstractions' ``audio`` block stops at Ep 6 while Eps 7–10
hide under ``wave2_audio_*``. So we walk the whole tree, collect every UUID, and type each by its
key path. This guarantees nothing in the map is silently dropped.
"""

from __future__ import annotations

import re
from typing import Any, List

from .markdown_tables import UUID_RE, RawArtifact


def _type_from_keypath(keys: List[str]) -> str:
    joined = " ".join(keys).lower()
    if "quiz" in joined:
        return "quiz"
    if "study_guide" in joined or "study guide" in joined:
        return "study_guide"
    if any(k in joined for k in ("audio", "flagship", "standalone", "deferred_audio", "podcast")):
        return "audio"
    return "unknown"


# Map keys whose UUID value is metadata, not an artifact (the notebook's own id, etc.).
_IGNORE_KEYS = {"notebook_id", "notebookid", "nb", "nb_id"}


def _episode_from_key(key: str) -> int | None:
    if str(key).isdigit():
        return int(key)
    m = re.search(r"\bep\.?\s*(\d+)", str(key).lower())
    return int(m.group(1)) if m else None


def parse_artifact_map(data: Any) -> List[RawArtifact]:
    out: List[RawArtifact] = []

    def walk(node: Any, keys: List[str]) -> None:
        if isinstance(node, dict):
            # Canonical {"id": "...", "title": "..."} leaf.
            nid = node.get("id")
            if isinstance(nid, str) and UUID_RE.fullmatch(nid):
                title = node.get("title") or ""
                ty = _type_from_keypath(keys)
                ep = _episode_from_key(keys[-1]) if keys else None
                out.append(
                    RawArtifact(
                        artifact_id=nid.lower(),
                        type=ty,
                        title=str(title),
                        episode=ep,
                        source="map",
                    )
                )
                return
            for k, v in node.items():
                if str(k).lower() in _IGNORE_KEYS:
                    continue
                # {"<title>": "<uuid>"} or {"<ep>": "<uuid>"} leaf.
                if isinstance(v, str) and UUID_RE.fullmatch(v):
                    ty = _type_from_keypath(keys + [str(k)])
                    ep = _episode_from_key(str(k))
                    title = "" if str(k).isdigit() else str(k)
                    out.append(
                        RawArtifact(
                            artifact_id=v.lower(),
                            type=ty,
                            title=title,
                            episode=ep,
                            source="map",
                        )
                    )
                else:
                    walk(v, keys + [str(k)])
        elif isinstance(node, list):
            for v in node:
                walk(v, keys)
        elif isinstance(node, str):
            if UUID_RE.fullmatch(node):
                out.append(
                    RawArtifact(
                        artifact_id=node.lower(),
                        type=_type_from_keypath(keys),
                        title="",
                        episode=_episode_from_key(keys[-1]) if keys else None,
                        source="map",
                    )
                )

    walk(data, [])
    return out
