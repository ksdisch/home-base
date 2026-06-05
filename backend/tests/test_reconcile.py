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
