"""POST episode-listened toggle. Writes ONLY to the hub's SQLite — never the sidecars."""

from __future__ import annotations

from fastapi import APIRouter

from ..models import EpisodeToggle
from ..store import set_episode_listened

router = APIRouter()


@router.post("/topics/{notebook_id}/episodes/{artifact_id}/listened")
def toggle_listened(notebook_id: str, artifact_id: str, body: EpisodeToggle) -> dict:
    listened = set_episode_listened(notebook_id, artifact_id, body.listened)
    return {"notebook_id": notebook_id, "artifact_id": artifact_id, "listened": listened}
