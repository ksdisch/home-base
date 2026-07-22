"""The bundled Jacobian Lens example path ships well-formed (M8 vertical-slice fixture).

Also the audio-primary guard: the path must be built on the notebook's **audio** overview
season, never the whiteboard **video** season (which is supplementary — see
``docs/ideas/learning-paths.md``). The fixture is hand-authored, so it bypasses the Designer's
catalog cross-check (``compose_path`` only runs it on generated paths); these tests are that
missing check pinned for the shipped fixture, so a video-as-audio inversion can't recur.
"""

from __future__ import annotations

from app.paths import manifest
from app.paths.designer import _TYPE_FOR_KIND

JACOBIAN = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4"
_ARTIFACT_KINDS = {"audio", "read", "flashcards", "quiz"}

# The jlens-workspace notebook has two parallel "Ep N —" seasons whose ids must never be confused:
# the AUDIO deep-dive season (the learning spine) and the whiteboard VIDEO/explainer season
# (supplementary). Source of truth: the notebook's README artifact tables.
_AUDIO_SERIES_IDS = {
    "82a3597b-6f32-4d7f-acaa-ba76bd407249",  # Ep 1 — The Global Workspace Idea
    "72118929-ea29-420a-bfd4-5a25a50a0036",  # Ep 2 — The Jacobian Lens
    "bf0196c0-1db8-4586-a988-c383cb10b019",  # Ep 3 — Report, Control, Reasoning
    "32682216-8712-4145-8341-be4c999dce75",  # Ep 4 — Broadcast, Selectivity, Structure
    "c918a216-2a1a-42b5-879a-aed873f7b684",  # Ep 5 — Auditing Hidden Thoughts
    "0b54dbfa-f335-4ccf-ba42-2cbe8000c900",  # Ep 6 — Consciousness & Replication
}
_VIDEO_SERIES_IDS = {
    "fa4bda2a-f34e-4b4d-9ff5-d562bef025cb",  # Ep 1 — Anatomy of the Lens (explainer/whiteboard)
    "6b7e660a-738c-42bb-a28f-32b56e2ca183",  # Ep 2 — The Map of the Layers
    "01ed5155-5ab9-413c-a063-7ffbe37b4355",  # Ep 3 — Surgery on Thoughts
    "c3ccb11d-2945-4af3-af50-742e6c5f6d58",  # Ep 4 — Replicating the Paper
}


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


def test_bundled_jacobian_artifact_types_match_their_kind() -> None:
    """A generalizable consistency guard: an artifact-backed step's declared ``artifact_type`` must
    equal the type its ``kind`` implies (``audio`` step → ``audio`` artifact, etc.). Catches a future
    fixture that mislabels a step's type."""
    path = manifest.get_path(JACOBIAN)
    assert path is not None
    for s in path["steps"]:
        expected = _TYPE_FOR_KIND.get(s["kind"])
        if expected is None:
            continue  # a glue step (intro/bridge/reflect/recap)
        assert s["artifact_type"] == expected, (
            f"step {s['id']} (kind {s['kind']}) declares artifact_type "
            f"{s['artifact_type']!r}, expected {expected!r}"
        )


def test_bundled_jacobian_is_built_on_audio_not_video() -> None:
    """The audio-primary guard. Every audio step must cite an id from the audio deep-dive season,
    and NO step anywhere may cite an id from the supplementary whiteboard video season — the exact
    inversion that shipped in the original fixture (video ids mislabeled as ``audio``)."""
    path = manifest.get_path(JACOBIAN)
    assert path is not None
    audio_ids = {s["artifact_id"] for s in path["steps"] if s["kind"] == "audio"}
    assert audio_ids, "the path should have audio steps"
    assert audio_ids <= _AUDIO_SERIES_IDS, (
        f"audio steps must cite the audio-series ids; stray ids: {audio_ids - _AUDIO_SERIES_IDS}"
    )
    cited = {s["artifact_id"] for s in path["steps"] if s["artifact_id"]}
    leaked_video = cited & _VIDEO_SERIES_IDS
    assert not leaked_video, f"no step may cite a video-series id; found: {leaked_video}"
