from app.catalog.markdown_tables import RawArtifact
from app.catalog.reconcile import reconcile

A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
C = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def test_reconcile_surfaces_nlm_only_without_inventing_titles():
    sidecar = [RawArtifact(artifact_id=A, type="quiz", title="Ep 1 — Quiz")]
    studio = [
        {"id": A, "type": "quiz", "status": "completed"},
        {"id": C, "type": "audio", "status": "completed"},  # in nlm, not sidecar
    ]
    res = reconcile(sidecar, studio)
    by_id = {a.artifact_id: a for a in res.artifacts}
    assert set(by_id) == {A, C}
    assert by_id[A].title == "Ep 1 — Quiz"  # sidecar title preserved
    assert by_id[C].title == ""  # nlm has no title -> empty (UI renders "Untitled audio")
    assert res.nlm_only_ids == [C]
    assert "nlm" in by_id[A].source


def test_reconcile_flags_sidecar_only_as_missing():
    sidecar = [
        RawArtifact(artifact_id=A, type="quiz", title="Q"),
        RawArtifact(artifact_id=B, type="audio", title="Stale"),
    ]
    studio = [{"id": A, "type": "quiz", "status": "completed"}]
    res = reconcile(sidecar, studio)
    assert res.sidecar_only_ids == [B]
    assert res.live_missing_ids == [B]
    assert {a.artifact_id for a in res.artifacts} == {A, B}  # nothing dropped


def test_reconcile_refreshes_status_and_fills_unknown_type():
    sidecar = [RawArtifact(artifact_id=A, type="unknown", title="?", status="old")]
    studio = [{"id": A, "type": "flashcards", "status": "completed"}]
    res = reconcile(sidecar, studio)
    a = res.artifacts[0]
    assert a.type == "flashcards"  # unknown filled from live
    assert a.status == "completed"


def test_reconcile_empty_studio_is_noop_passthrough():
    sidecar = [RawArtifact(artifact_id=A, type="quiz", title="Q")]
    res = reconcile(sidecar, [])
    assert [a.artifact_id for a in res.artifacts] == [A]
    assert res.nlm_only_ids == []


def test_reconcile_matches_truncated_sidecar_id_to_full_live_id():
    """A README often shortens an artifact id (id_complete=False). The full live id must reconcile
    to that same artifact instead of doubling it (a phantom nlm-only + a stale sidecar-only)."""
    sidecar = [RawArtifact(artifact_id="aaaaaaaa", type="quiz", title="Ep 1 — Quiz", id_complete=False)]
    studio = [{"id": A, "type": "quiz", "status": "completed"}]  # full id — same artifact
    res = reconcile(sidecar, studio)

    assert len(res.artifacts) == 1            # not doubled
    assert res.nlm_only_ids == []             # not surfaced as a phantom nlm-only
    assert res.sidecar_only_ids == []         # not flagged missing/stale
    a = res.artifacts[0]
    assert a.title == "Ep 1 — Quiz"           # sidecar's rich title preserved
    assert a.status == "completed"            # live status refreshed
    assert "nlm" in a.source                  # live-confirmed


def test_reconcile_does_not_prefix_match_complete_ids():
    """Precision guard: only truncated ids (id_complete=False) prefix-match. A *complete* sidecar id
    that is coincidentally a prefix of a different live id stays a distinct artifact."""
    sidecar = [RawArtifact(artifact_id="aaaaaaaa", type="quiz", title="Q")]  # id_complete=True (default)
    studio = [{"id": A, "type": "audio", "status": "completed"}]
    res = reconcile(sidecar, studio)

    assert len(res.artifacts) == 2
    assert res.nlm_only_ids == [A]
    assert res.sidecar_only_ids == ["aaaaaaaa"]
