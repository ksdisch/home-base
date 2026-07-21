"""The bundled Jacobian Lens example path ships well-formed (M8 vertical-slice fixture)."""

from __future__ import annotations

from app.paths import manifest

JACOBIAN = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4"
_ARTIFACT_KINDS = {"audio", "read", "flashcards", "quiz"}


def test_bundled_jacobian_path_loads_and_is_wellformed() -> None:
    # discoverable via EXAMPLES_DIR even with an empty user PATHS_DIR (the isolated test data dir)
    path = manifest.get_path(JACOBIAN)
    assert path is not None
    assert path["notebook_id"] == JACOBIAN
    kinds = [s["kind"] for s in path["steps"]]
    assert kinds[0] == "intro"
    assert "quiz" in kinds
    # this topic has NO study guide, so the path stands in a generated bridge-check
    assert "bridge" in kinds
    # every artifact-backed step references a real artifact id
    for s in path["steps"]:
        if s["kind"] in _ARTIFACT_KINDS:
            assert s["artifact_id"], f"step {s['id']} ({s['kind']}) must reference an artifact"


def test_bundled_jacobian_id_is_listed() -> None:
    assert JACOBIAN in manifest.list_path_ids()
