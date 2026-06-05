"""The crafted-root adversarial cases: broken sidecars must degrade, never crash or fabricate."""

from __future__ import annotations

from app.catalog.build import to_groups, to_topic_detail
from app.catalog.ingest import find_sidecar, load_sidecars


def test_load_never_crashes_and_skips_unusable(crafted_root):
    load = load_sidecars(crafted_root)
    names = {sc.dir_name for sc in load.sidecars}
    # alpha, acme, archived, broken-fm, empty parse; no-id is skipped; non-notebook/.obsidian ignored.
    assert "alpha-learning" in names
    assert "acme-interview-prep" in names
    assert "old-archived" in names
    assert "broken-fm" in names
    assert "no-id" not in names
    assert "not-a-notebook" not in names
    assert any("no notebook_id" in w for w in load.warnings)


def test_groups_are_correct(crafted_root):
    groups = {g.key: g for g in to_groups(load_sidecars(crafted_root).sidecars)}
    learning_titles = {c.title for c in groups["learning"].notebooks}
    interview_titles = {c.title for c in groups["interview-prep"].notebooks}
    assert "Alpha Learning Topic" in learning_titles
    assert "Acme Interview Prep" in interview_titles
    assert "custom" in groups  # placeholder group exists even when empty
    assert groups["custom"].notebooks == []


def test_map_and_readme_merge_without_dropping(crafted_root):
    sc = find_sidecar(crafted_root, _id(crafted_root, "alpha-learning"))
    audio = [a for a in sc.artifacts if a.type == "audio"]
    # README has Eps 1-4; map has Eps 1-2 — union must be 4 (deduped), nothing dropped.
    assert sorted(a.episode for a in audio) == [1, 2, 3, 4]
    # The notebook's own id (in the map's "notebook_id" field) is NOT an artifact.
    assert sc.notebook_id not in {a.artifact_id for a in sc.artifacts}


def test_source_not_fabricated_as_artifact(crafted_root):
    sc = find_sidecar(crafted_root, _id(crafted_root, "alpha-learning"))
    assert all(a.type != "unknown" for a in sc.artifacts)
    # Exactly: 4 audio + 1 quiz + 1 study guide = 6 (the lone Source row excluded).
    assert len(sc.artifacts) == 6


def test_archived_notebook_renders(crafted_root):
    sc = find_sidecar(crafted_root, _id(crafted_root, "old-archived"))
    assert sc.archived is True
    assert sc.merged_into == "alpha-learning"
    detail = to_topic_detail(sc, sc.artifacts, {})
    assert detail.archived is True
    assert len(detail.quizzes) == 1


def test_recovered_notebook_id_from_url(crafted_root):
    sc = find_sidecar(crafted_root, _id(crafted_root, "broken-fm"))
    assert sc is not None  # id recovered from the body URL despite malformed YAML
    assert any("recovered from URL" in w for w in sc.warnings)
    assert len(sc.artifacts) == 1


def test_truncated_ids_in_interview_prep(crafted_root):
    sc = find_sidecar(crafted_root, _id(crafted_root, "acme-interview-prep"))
    # 2 artifacts table rows + 2 valid season rows (the broken no-id row skipped).
    assert len(sc.artifacts) == 4
    detail = to_topic_detail(sc, sc.artifacts, {})
    assert sorted(e.n for e in detail.episodes) == [1, 2]


def _id(root, dir_name: str) -> str:
    for sc in load_sidecars(root).sidecars:
        if sc.dir_name == dir_name:
            return sc.notebook_id
    raise AssertionError(f"{dir_name} not parsed")
