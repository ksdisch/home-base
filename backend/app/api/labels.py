"""Shared notebook-label resolution for the read-only API surfaces.

``/review`, `/study-plan`, and friends all need to turn a bare ``notebook_id`` into a human title
+ group + topic URL from the offline sidecar catalog. This is that one helper — best-effort and
offline; a catalog hiccup degrades to labelling by id (the queues must never 500 over it).
"""

from __future__ import annotations

from typing import Dict

from ..catalog.build import to_groups
from ..catalog.ingest import load_sidecars


def label_map(settings) -> Dict[str, Dict[str, str]]:
    """``notebook_id → {title, group, group_label, topic_url}`` from the sidecar catalog."""
    out: Dict[str, Dict[str, str]] = {}
    try:
        groups = to_groups(load_sidecars(settings.notebooklm_root).sidecars)
    except Exception:  # the read-only queues must never 500 over a catalog hiccup
        return out
    for g in groups:
        for nb in g.notebooks:
            out[nb.notebook_id] = {
                "title": nb.title,
                "group": nb.group,
                "group_label": nb.group_label,
                "topic_url": nb.topic_url,
            }
    return out
