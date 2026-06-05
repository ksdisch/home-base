"""Assertions against the REAL sidecar dir (skipped if absent). Locks the behaviours we verified."""

from __future__ import annotations

from collections import Counter

from app.catalog.build import to_groups, to_topic_detail
from app.catalog.ingest import find_sidecar, load_sidecars

from .conftest import REAL_ROOT, needs_real_data

ENG_ID = "594e8167-7d8e-454d-8ea9-3930080c899f"
ENG_EP1_QUIZ = "f5c893d3-ebc3-47b5-b362-c7bb5bc16bd1"
SEGAL_ID = "cfcf7581-a69b-4b45-8d18-d41e98110c90"

pytestmark = needs_real_data


def test_all_real_sidecars_parse_without_crashing():
    load = load_sidecars(REAL_ROOT)
    assert len(load.sidecars) >= 6
    # No fabricated/unknown artifacts anywhere across the real corpus.
    total_unknown = sum(
        1 for sc in load.sidecars for a in sc.artifacts if a.type == "unknown"
    )
    assert total_unknown == 0


def test_grouping_separates_learning_and_interview_prep():
    groups = {g.key: g for g in to_groups(load_sidecars(REAL_ROOT).sidecars)}
    learning = {c.alias for c in groups["learning"].notebooks}
    interview = {c.alias for c in groups["interview-prep"].notebooks}
    assert "engineering-abstractions" in learning
    assert any("interview-prep" in a for a in interview)
    assert not (learning & interview)


def test_engineering_has_full_10_episode_season_and_matching_quiz():
    sc = find_sidecar(REAL_ROOT, ENG_ID)
    assert sc is not None
    detail = to_topic_detail(sc, sc.artifacts, {})
    # JSON map (Eps 1-6) merged with README table (Eps 7-10) -> all ten, none dropped.
    assert sorted(e.n for e in detail.episodes if e.n) == list(range(1, 11))
    quiz_ids = {q.artifact_id for q in detail.quizzes}
    assert ENG_EP1_QUIZ in quiz_ids  # matches docs/fixtures/sample-quiz.json


def test_segal_truncated_ids_still_yield_artifacts():
    sc = find_sidecar(REAL_ROOT, SEGAL_ID)
    assert sc is not None
    assert len(sc.artifacts) > 0
    detail = to_topic_detail(sc, sc.artifacts, {})
    assert sorted(e.n for e in detail.episodes if e.n) == [1, 2, 3, 4, 5, 6]


def test_stoicism_is_archived_and_no_source_ids_leak():
    # Find the archived notebook regardless of its id.
    archived = [sc for sc in load_sidecars(REAL_ROOT).sidecars if sc.archived]
    assert archived, "expected at least one archived notebook (stoicism)"
    sto = next((s for s in archived if s.dir_name == "stoicism"), archived[0])
    types = Counter(a.type for a in sto.artifacts)
    # All artifacts are real studio types; the Sources table (full of Source IDs) is excluded.
    assert types["unknown"] == 0
    assert 0 < len(sto.artifacts) < 15  # ~8 real artifacts, not the ~18 source rows


def test_inner_work_does_not_ingest_other_notebooks_ids():
    load = load_sidecars(REAL_ROOT)
    iw = next((s for s in load.sidecars if s.dir_name == "inner-work"), None)
    if iw is None:
        return
    # No foreign notebook ids (mentioned in migration-note prose) became artifacts.
    other_ids = {s.notebook_id for s in load.sidecars if s.dir_name != "inner-work"}
    assert not ({a.artifact_id for a in iw.artifacts} & other_ids)
