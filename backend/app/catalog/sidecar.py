"""Parse one notebook sidecar directory into a :class:`ParsedSidecar`.

Combines: frontmatter, README tables, README bullets, and the artifact-map JSON — then merges
artifacts by id so the map and the README reinforce (not replace) each other.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .artifact_map import parse_artifact_map
from .frontmatter import parse_frontmatter
from .grouping import group_for
from .markdown_tables import (
    UUID_RE,
    RawArtifact,
    classify_table_artifacts,
    extract_bullet_artifacts,
    extract_tables,
)

_TYPE_SPECIFICITY = {
    "quiz": 5,
    "study_guide": 5,
    "audio": 4,
    "video": 4,
    "flashcards": 3,
    "mind_map": 3,
    "slide_deck": 3,
    "infographic": 3,
    "data_table": 3,
    "report": 2,
    "unknown": 0,
}


@dataclass
class ParsedSidecar:
    dir_name: str
    path: Path
    notebook_id: str
    alias: str
    title: str
    template: Optional[str]
    tags: List[str]
    group: str
    archived: bool
    merged_into: Optional[str]
    source_count: Optional[int]
    artifacts: List[RawArtifact]
    warnings: List[str] = field(default_factory=list)


def _first_h1(body: str) -> Optional[str]:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def _prefer_type(a: str, b: str) -> str:
    return a if _TYPE_SPECIFICITY.get(a, 0) >= _TYPE_SPECIFICITY.get(b, 0) else b


def _better_title(a: str, b: str) -> str:
    a, b = a.strip(), b.strip()

    def score(t: str) -> tuple:
        if not t:
            return (0, 0)
        lead = 1 if re.match(r"(ep\.?\s*\d+|s\d+\s*e\s*\d+)", t.lower()) else 0
        return (lead, len(t))

    return a if score(a) >= score(b) else b


def _combine(x: RawArtifact, y: RawArtifact) -> RawArtifact:
    if x.type == "unknown":
        ty = y.type
    elif y.type == "unknown":
        ty = x.type
    else:
        ty = _prefer_type(x.type, y.type)
    return RawArtifact(
        artifact_id=x.artifact_id,
        type=ty,
        title=_better_title(x.title, y.title),
        episode=x.episode if x.episode is not None else y.episode,
        fmt=x.fmt or y.fmt,
        length=x.length or y.length,
        status=x.status or y.status,
        section=x.section or y.section,
        source="map+readme" if x.source != y.source else x.source,
        id_complete=x.id_complete or y.id_complete,
    )


def merge_artifacts(arts: List[RawArtifact]) -> List[RawArtifact]:
    by_id: dict[str, RawArtifact] = {}
    for a in arts:
        if not a.artifact_id:
            continue
        if a.artifact_id in by_id:
            by_id[a.artifact_id] = _combine(by_id[a.artifact_id], a)
        else:
            by_id[a.artifact_id] = a
    return list(by_id.values())


def parse_sidecar(readme_path: Path) -> Optional[ParsedSidecar]:
    """Parse a sidecar README. Returns ``None`` (with no crash) only if no notebook_id exists."""
    dir_name = readme_path.parent.name
    warnings: List[str] = []
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return None
    fm, body = parse_frontmatter(text)

    notebook_id = fm.get("notebook_id")
    if not notebook_id:
        m = re.search(r"notebook/(" + UUID_RE.pattern + r")", body)
        if m:
            notebook_id = m.group(1)
            warnings.append("notebook_id missing from frontmatter; recovered from URL")
    if not notebook_id:
        return None
    notebook_id = str(notebook_id).strip()

    alias = str(fm.get("alias") or dir_name)
    title = str(fm.get("title") or _first_h1(body) or alias)
    template = fm.get("template")
    template = str(template) if template is not None else None
    tags_raw = fm.get("tags") or []
    tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else [str(tags_raw)]
    archived = str(fm.get("status", "")).lower() == "archived"
    merged_into = fm.get("merged_into")
    merged_into = str(merged_into) if merged_into else None
    source_count = fm.get("source_count")
    try:
        source_count = int(source_count) if source_count is not None else None
    except (TypeError, ValueError):
        source_count = None

    group = group_for(template, tags, alias, dir_name)

    artifacts: List[RawArtifact] = []
    try:
        for table in extract_tables(body):
            artifacts.extend(classify_table_artifacts(table))
    except Exception as e:  # never let one bad table sink the notebook
        warnings.append(f"table parse skipped: {e}")
    try:
        artifacts.extend(extract_bullet_artifacts(body))
    except Exception as e:
        warnings.append(f"bullet parse skipped: {e}")

    map_path = readme_path.parent / "artifacts" / "audio-series-artifact-map.json"
    if map_path.exists():
        try:
            data = json.loads(map_path.read_text(encoding="utf-8", errors="replace"))
            artifacts.extend(parse_artifact_map(data))
        except Exception as e:
            warnings.append(f"artifact-map parse skipped: {e}")

    artifacts = merge_artifacts(artifacts)

    return ParsedSidecar(
        dir_name=dir_name,
        path=readme_path.parent,
        notebook_id=notebook_id,
        alias=alias,
        title=title,
        template=template,
        tags=tags,
        group=group,
        archived=archived,
        merged_into=merged_into,
        source_count=source_count,
        artifacts=artifacts,
        warnings=warnings,
    )
