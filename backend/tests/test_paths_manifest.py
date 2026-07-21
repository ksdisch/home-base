"""app.paths.manifest — defensive parse of a learning-path sidecar (M8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.paths import manifest


def _write(tmp: Path, notebook_id: str, data: dict) -> Path:
    f = tmp / f"{notebook_id}.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def _good() -> dict:
    return {
        "title": "Global Workspace in LLMs — the Jacobian Lens Paper",
        "topic": "interpretability",
        "steps": [
            {"id": "intro", "kind": "intro", "title": "What the J-lens is", "body": "one minute"},
            {"id": "ep2", "kind": "audio", "title": "Ep 2 — Map of the Layers",
             "artifact_id": "aud-2", "focus": "how features map across layers",
             "estimated_minutes": 9},
            {"id": "bridge", "kind": "bridge", "title": "J-lens vs logit lens",
             "body": "In one line, how do they differ?"},
            {"id": "quiz", "kind": "quiz", "title": "Jacobian Lens quiz", "artifact_id": "quiz-1"},
        ],
    }


def test_loads_a_wellformed_path(tmp_path: Path) -> None:
    path = manifest.load_path_file(_write(tmp_path, "nb-1", _good()))
    assert path["notebook_id"] == "nb-1"
    assert [s["kind"] for s in path["steps"]] == ["intro", "audio", "bridge", "quiz"]
    ep2 = path["steps"][1]
    assert ep2["artifact_id"] == "aud-2"
    assert ep2["focus"] == "how features map across layers"
    assert ep2["estimated_minutes"] == 9


def test_filename_is_identity_body_notebook_id_ignored(tmp_path: Path) -> None:
    data = _good()
    data["notebook_id"] = "SPOOFED"  # a stray id in the body must never win over the filename
    assert manifest.load_path_file(_write(tmp_path, "real-nb", data))["notebook_id"] == "real-nb"


def test_missing_title_raises(tmp_path: Path) -> None:
    data = _good()
    data.pop("title")
    with pytest.raises(manifest.PathError):
        manifest.load_path_file(_write(tmp_path, "nb", data))


def test_empty_steps_raises(tmp_path: Path) -> None:
    data = _good()
    data["steps"] = []
    with pytest.raises(manifest.PathError):
        manifest.load_path_file(_write(tmp_path, "nb", data))


def test_artifact_kind_without_artifact_id_raises(tmp_path: Path) -> None:
    data = _good()
    data["steps"] = [{"id": "a", "kind": "audio", "title": "Ep 1"}]  # no artifact_id
    with pytest.raises(manifest.PathError):
        manifest.load_path_file(_write(tmp_path, "nb", data))


def test_glue_kind_without_artifact_id_is_fine(tmp_path: Path) -> None:
    data = _good()
    data["steps"] = [{"id": "r", "kind": "reflect", "title": "One line takeaway"}]
    assert manifest.load_path_file(_write(tmp_path, "nb", data))["steps"][0]["kind"] == "reflect"


def test_duplicate_step_id_raises(tmp_path: Path) -> None:
    data = _good()
    data["steps"] = [
        {"id": "x", "kind": "reflect", "title": "a"},
        {"id": "x", "kind": "reflect", "title": "b"},
    ]
    with pytest.raises(manifest.PathError):
        manifest.load_path_file(_write(tmp_path, "nb", data))


def test_url_unsafe_step_id_raises(tmp_path: Path) -> None:
    data = _good()
    data["steps"] = [{"id": "bad id/x", "kind": "reflect", "title": "a"}]
    with pytest.raises(manifest.PathError):
        manifest.load_path_file(_write(tmp_path, "nb", data))


def test_invalid_json_raises(tmp_path: Path) -> None:
    f = tmp_path / "nb.json"
    f.write_text("{not json", encoding="utf-8")
    with pytest.raises(manifest.PathError):
        manifest.load_path_file(f)


def test_get_path_discovers_from_paths_dir(tmp_path: Path, monkeypatch) -> None:
    # get_path reads settings().paths_dir; point it at a tmp dir and confirm discovery + miss.
    monkeypatch.setattr(get_settings(), "paths_dir", tmp_path)
    _write(tmp_path, "nb-42", _good())
    assert manifest.get_path("nb-42")["title"].startswith("Global Workspace")
    assert manifest.get_path("does-not-exist") is None
    assert "nb-42" in manifest.list_path_ids()
