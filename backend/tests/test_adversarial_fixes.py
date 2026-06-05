"""Regression tests for defects found by the adversarial-verification workflow.

Each test pins a previously-reproducible bug in: parser fabrication, reconcile robustness,
the read-only boundary, auth classification, and the quiz oracle.
"""

from __future__ import annotations

import pytest

from app.catalog.artifact_map import parse_artifact_map
from app.catalog.markdown_tables import (
    classify_table_artifacts,
    extract_bullet_artifacts,
    extract_tables,
)
from app.catalog.reconcile import reconcile
from app.catalog.markdown_tables import RawArtifact
from app.nlm import DisallowedCommandError, NlmAuthError, NlmClient, NlmNotFoundError, NlmResult
from app.quiz import QuizValidationError, grade_quiz, load_quiz

A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
C = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _arts(md: str):
    out = []
    for t in extract_tables(md):
        out.extend(classify_table_artifacts(t))
    return out


# --- parser fabrication ----------------------------------------------------
def test_source_section_with_plain_id_column_is_not_fabricated():
    md = f"## Sources\n| # | Title | ID |\n|---|---|---|\n| 1 | A source | {A} |\n"
    assert _arts(md) == []  # section-level guard, not just header name


def test_migration_notes_bullet_is_not_an_artifact():
    md = f"## Season 1 — migration notes\n- The old Ep 3 was deleted and replaced by — {A}\n"
    assert extract_bullet_artifacts(md) == []


def test_escaped_pipe_in_cell_does_not_drop_the_artifact():
    md = f"## Audio\n| Type | Title | Artifact ID |\n|---|---|---|\n| Audio | A \\| B title | {A} |\n"
    arts = _arts(md)
    assert len(arts) == 1 and arts[0].artifact_id == A


def test_pure_decimal_in_id_column_is_skipped():
    md = "## Audio\n| Title | Artifact ID |\n|---|---|\n| Ep on a date | 20260605 |\n"
    assert _arts(md) == []  # a date is not a (truncated) id


def test_artifact_map_metadata_keys_never_fabricate_foreign_ids():
    data = {
        "notebook_id": A,
        "parent_notebook": B,
        "source_notebook": {"id": B, "title": "Original (deleted)"},
        "audio": {"1": {"id": C, "title": "Ep 1 — X"}},
    }
    ids = {a.artifact_id for a in parse_artifact_map(data)}
    assert ids == {C}  # only the real audio artifact; A and B excluded


# --- reconcile robustness --------------------------------------------------
def test_reconcile_skips_non_dict_entries_without_crashing():
    res = reconcile([RawArtifact(A, "quiz", "Q")], [{"id": A}, "garbage", 123, None])
    assert {a.artifact_id for a in res.artifacts} == {A}


def test_reconcile_case_insensitive_id_match_does_not_split():
    res = reconcile([RawArtifact(A, "quiz", "Q")], [{"id": A.upper(), "status": "completed"}])
    assert len(res.artifacts) == 1
    assert res.nlm_only_ids == []  # uppercase live id is the SAME artifact


def test_reconcile_null_status_is_not_string_none():
    res = reconcile([RawArtifact(A, "quiz", "Q", status="old")], [{"id": A, "status": None}])
    a = res.artifacts[0]
    assert a.status == "old"  # kept; not overwritten with the string "None"
    assert "None" not in res.live_status.values()


def test_reconcile_null_or_blank_live_id_makes_no_ghost():
    res = reconcile([RawArtifact(A, "quiz", "Q")], [{"id": None}, {"id": "   "}, {"id": A}])
    assert {a.artifact_id for a in res.artifacts} == {A}
    assert res.nlm_only_ids == []


# --- read-only boundary ----------------------------------------------------
def test_version_flag_rejects_trailing_tokens():
    calls: list = []
    client = NlmClient(runner=lambda a: calls.append(list(a)) or NlmResult(list(a), "", "", 0))
    with pytest.raises(DisallowedCommandError):
        client._run(["--version", "studio", "create"])
    assert calls == []


def test_bare_version_word_no_longer_allowed():
    client = NlmClient(runner=lambda a: NlmResult(list(a), "", "", 0))
    with pytest.raises(DisallowedCommandError):
        client._run(["version"])


def test_download_subcommand_is_allowlisted():
    calls: list = []
    client = NlmClient(runner=lambda a: calls.append(list(a)) or NlmResult(list(a), "[]", "", 0))
    client._run(["download", "report", "nb", "--id", "x"])  # ok
    with pytest.raises(DisallowedCommandError):
        client._run(["download", "everything", "nb"])  # not a known read-only type


# --- auth classification ---------------------------------------------------
def _runner(stderr="", code=1):
    return lambda a: NlmResult(list(a), "", stderr, code)


def test_grpc_permission_denied_is_auth():
    client = NlmClient(runner=_runner("rpc error: code = PermissionDenied desc = PERMISSION_DENIED"))
    with pytest.raises(NlmAuthError):
        client.studio_status("nb")


def test_invalid_grant_is_auth():
    client = NlmClient(runner=_runner("oauth2: cannot fetch token: invalid_grant"))
    with pytest.raises(NlmAuthError):
        client.studio_status("nb")


def test_http_code_embedded_in_uuid_is_not_false_positive_auth():
    # "403" inside a token (not standalone) must NOT be read as an auth error.
    client = NlmClient(runner=_runner("notebook a403b9c1 not found"))
    with pytest.raises(NlmNotFoundError):
        client.studio_status("nb")


def test_real_403_is_auth():
    client = NlmClient(runner=_runner("HTTP 403 Forbidden"))
    with pytest.raises(NlmAuthError):
        client.studio_status("nb")


# --- quiz oracle -----------------------------------------------------------
def _q(options):
    return {"title": "x", "questions": [{"question": "q", "answerOptions": options, "hint": "h"}]}


def test_non_bool_iscorrect_is_rejected():
    bad = _q([
        {"text": "a", "isCorrect": "true", "rationale": "r"},  # string, not bool
        {"text": "b", "isCorrect": False, "rationale": "r"},
    ])
    with pytest.raises(QuizValidationError):
        load_quiz(bad)


def test_non_int_answer_counts_incorrect_no_crash():
    quiz = load_quiz(_q([
        {"text": "a", "isCorrect": True, "rationale": "r"},
        {"text": "b", "isCorrect": False, "rationale": "r"},
    ]))
    result = grade_quiz(quiz, {0: "0"})  # string answer
    assert result.questions[0].is_correct is False
    assert result.questions[0].chosen_index is None


def test_bool_answer_not_used_as_index():
    quiz = load_quiz(_q([
        {"text": "a", "isCorrect": True, "rationale": "r"},
        {"text": "b", "isCorrect": False, "rationale": "r"},
    ]))
    result = grade_quiz(quiz, {0: True})  # True must not index option 1
    assert result.questions[0].is_correct is False
    assert result.questions[0].chosen_index is None
