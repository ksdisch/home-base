"""Quiz player API: the take→grade→review loop, the answer-key integrity guard, and the calm
auth-failure path — all driven through the real session logic with a mocked `nlm` runner that
serves the committed sample quiz (so the contract is exercised end-to-end, offline)."""

from __future__ import annotations

import json
from pathlib import Path

SAMPLE_QUIZ = Path(__file__).resolve().parents[2] / "docs" / "fixtures" / "sample-quiz.json"


def _runner_serving_quiz(args):
    """A fake `nlm` runner: any `download quiz …` returns the committed sample quiz JSON."""
    from app.nlm import NlmResult

    return NlmResult(args=list(args), stdout=SAMPLE_QUIZ.read_text(encoding="utf-8"),
                     stderr="", returncode=0)


def _runner_not_logged_in(args):
    from app.nlm import NlmResult

    return NlmResult(args=list(args), stdout="", stderr="Error: not logged in", returncode=1)


def _make_client(runner):
    from fastapi.testclient import TestClient

    from app.deps import get_nlm_client
    from app.main import app
    from app.nlm import NlmClient

    app.dependency_overrides[get_nlm_client] = lambda: NlmClient(runner=runner)
    return TestClient(app)


def _answer_key() -> dict[int, int]:
    """The correct option index per question, read straight from the fixture's `isCorrect`."""
    data = json.loads(SAMPLE_QUIZ.read_text(encoding="utf-8"))
    key = {}
    for qi, q in enumerate(data["questions"]):
        for oi, opt in enumerate(q["answerOptions"]):
            if opt["isCorrect"]:
                key[qi] = oi
    return key


def test_prepare_returns_player_view_without_leaking_the_answer_key():
    client = _make_client(_runner_serving_quiz)
    try:
        r = client.post("/api/topics/nb-1/quizzes/quiz-1/prepare")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["session_id"]
        assert body["total"] == len(_answer_key())
        assert len(body["questions"]) == body["total"]
        # Integrity guard: NOTHING in the player payload may reveal the answer.
        blob = json.dumps(body)
        assert "isCorrect" not in blob
        assert "rationale" not in blob
        assert "correct_index" not in blob
        for q in body["questions"]:
            assert set(q) == {"index", "question", "options", "hint"}
            assert all(isinstance(o, str) for o in q["options"])
    finally:
        client.app.dependency_overrides.clear()


def test_grade_all_correct_is_full_score_and_persists_the_attempt():
    client = _make_client(_runner_serving_quiz)
    try:
        sid = client.post("/api/topics/nb-1/quizzes/quiz-1/prepare").json()["session_id"]
        key = _answer_key()
        r = client.post("/api/quiz/grade", json={"session_id": sid, "answers": key})
        assert r.status_code == 200
        body = r.json()
        assert body["score"] == body["total"] == len(key)
        assert body["pct"] == 100.0
        assert body["attempt_id"] >= 1
        # The review exposes the key now that the attempt is graded + saved.
        assert all(item["is_correct"] for item in body["review"])
        assert body["review"][0]["correct_rationale"]
    finally:
        client.app.dependency_overrides.clear()


def test_grade_a_miss_lowers_the_score_and_surfaces_the_correction():
    client = _make_client(_runner_serving_quiz)
    try:
        sid = client.post("/api/topics/nb-1/quizzes/quiz-1/prepare").json()["session_id"]
        key = _answer_key()
        # Force question 0 wrong by choosing a different option.
        wrong0 = next(i for i in range(4) if i != key[0])
        answers = dict(key)
        answers[0] = wrong0
        body = client.post(
            "/api/quiz/grade",
            json={"session_id": sid, "answers": answers, "hints": {"0": True}},
        ).json()
        assert body["score"] == body["total"] - 1
        q0 = next(item for item in body["review"] if item["index"] == 0)
        assert q0["is_correct"] is False
        assert q0["chosen_index"] == wrong0
        assert q0["correct_index"] == key[0]
        assert q0["used_hint"] is True
        assert q0["correct_rationale"]  # the explanation is shown on the miss
    finally:
        client.app.dependency_overrides.clear()


def test_prepare_auth_failure_is_a_calm_banner_not_a_500():
    client = _make_client(_runner_not_logged_in)
    try:
        r = client.post("/api/topics/nb-1/quizzes/quiz-1/prepare")
        assert r.status_code == 200  # degraded, not a crash
        body = r.json()
        assert body["ok"] is False
        assert body["auth"]["ok"] is False
        assert "nlm login" in (body["auth"]["message"] or "").lower()
        assert body["session_id"] is None
    finally:
        client.app.dependency_overrides.clear()


def test_grade_unknown_session_is_404():
    client = _make_client(_runner_serving_quiz)
    try:
        r = client.post(
            "/api/quiz/grade", json={"session_id": "does-not-exist", "answers": {}}
        )
        assert r.status_code == 404
        assert "expired" in r.json()["detail"].lower()
    finally:
        client.app.dependency_overrides.clear()
