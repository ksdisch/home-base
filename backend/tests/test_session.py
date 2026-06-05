"""Tests for the /episode-review backing CLI. Runs entirely offline against the fixture
(``--from-file``) — no nlm, no network. Asserts the answer-key-never-leaks property and the
grade→persist round-trip into the hub's SQLite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.quiz import session
from app.store import connect, init_db

FIXTURE = Path(__file__).resolve().parent.parent.parent / "docs" / "fixtures" / "sample-quiz.json"
NB = "notebook-xyz"
QUIZ = "quiz-artifact-1"
EP = "episode-artifact-1"


@pytest.fixture(autouse=True)
def _db():
    init_db()  # the isolated tmp DB from conftest; create tables before any write
    yield


def _prepare(episode=None):
    return session.cmd_prepare(NB, QUIZ, episode_artifact_id=episode, from_file=str(FIXTURE))


def test_prepare_returns_player_view_without_the_answer_key():
    out = _prepare()
    assert out["total"] == 10
    assert len(out["questions"]) == 10
    q0 = out["questions"][0]
    assert isinstance(q0["options"], list) and all(isinstance(o, str) for o in q0["options"])
    assert q0["hint"]  # hints are offered to the player...

    # ...but the answer key and rationales (which give the answer away) never appear.
    blob = json.dumps(out)
    assert "isCorrect" not in blob  # the answer key is gone
    assert "rationale" not in blob  # rationales (which give the answer away) are gone too


def test_session_file_keeps_the_keyed_quiz_for_grading_only():
    out = _prepare()
    session_file = session._sessions_dir() / f"{out['session_id']}.json"
    assert session_file.exists()
    stored = json.loads(session_file.read_text())
    # The keyed copy lives only in the session file that `grade` reads — not in the player view.
    assert stored["raw"]["questions"][0]["answerOptions"][0]["isCorrect"] is True


def test_grade_all_correct_persists_attempt_and_mastery():
    prep = _prepare()
    answers = {str(q["index"]): _correct_index(prep, q["index"]) for q in prep["questions"]}
    out = session.cmd_grade(prep["session_id"], answers)

    assert out["score"] == out["total"] == 10
    assert out["pct"] == 100.0
    assert out["review"][0]["is_correct"] is True
    assert out["review"][0]["correct_rationale"]  # review surfaces the rationale post-grade

    conn = connect()
    try:
        attempt = conn.execute(
            "SELECT score, total FROM attempts WHERE id = ?", (out["attempt_id"],)
        ).fetchone()
        assert (attempt["score"], attempt["total"]) == (10, 10)
        n_answers = conn.execute(
            "SELECT COUNT(*) c FROM attempt_answers WHERE attempt_id = ?", (out["attempt_id"],)
        ).fetchone()["c"]
        assert n_answers == 10
        topic = conn.execute(
            "SELECT score FROM topic_mastery WHERE notebook_id = ?", (NB,)
        ).fetchone()
        assert topic["score"] == 1.0
    finally:
        conn.close()


def test_grade_can_mark_episode_listened():
    prep = _prepare(episode=EP)
    answers = {str(q["index"]): _correct_index(prep, q["index"]) for q in prep["questions"]}
    out = session.cmd_grade(prep["session_id"], answers, mark_listened=True)
    assert out["episode_marked_listened"] is True

    conn = connect()
    try:
        row = conn.execute(
            "SELECT listened FROM episode_progress WHERE notebook_id = ? AND artifact_id = ?",
            (NB, EP),
        ).fetchone()
        assert row is not None and bool(row["listened"]) is True
    finally:
        conn.close()


def test_hint_is_metadata_not_a_score_penalty():
    prep = _prepare()
    answers = {str(q["index"]): _correct_index(prep, q["index"]) for q in prep["questions"]}
    out = session.cmd_grade(prep["session_id"], answers, hints={"0": True})

    assert out["score"] == 10  # a hinted-but-correct answer still scores full
    assert out["review"][0]["used_hint"] is True

    conn = connect()
    try:
        used = conn.execute(
            "SELECT used_hint FROM attempt_answers WHERE attempt_id = ? AND question_index = 0",
            (out["attempt_id"],),
        ).fetchone()["used_hint"]
        assert bool(used) is True
        # ...but the hint down-weights the raw mastery signal (1.0 clean -> 0.5 hinted).
        qscore = conn.execute(
            "SELECT score FROM question_mastery WHERE notebook_id = ? AND question_key = ?",
            (NB, session.question_key(prep["questions"][0]["question"])),
        ).fetchone()["score"]
        assert qscore == 0.5
    finally:
        conn.close()


def test_miss_increments_question_miss_count():
    prep = _prepare()
    # Answer question 0 wrong (pick an index that isn't the correct one), rest unanswered.
    wrong = 0 if _correct_index(prep, 0) != 0 else 1
    out = session.cmd_grade(prep["session_id"], {"0": wrong})
    assert out["review"][0]["is_correct"] is False
    assert out["review"][0]["chosen_rationale"]  # the miss explains why the pick was wrong

    conn = connect()
    try:
        miss = conn.execute(
            "SELECT miss_count FROM question_mastery WHERE notebook_id = ? AND question_key = ?",
            (NB, session.question_key(prep["questions"][0]["question"])),
        ).fetchone()["miss_count"]
        assert miss == 1
    finally:
        conn.close()


def test_reflect_persists_reflection():
    out = session.cmd_reflect(NB, "Felt shaky on Hyrum's Law.", episode_artifact_id=EP, grasp_rating=3)
    conn = connect()
    try:
        row = conn.execute(
            "SELECT notebook_id, body, grasp_rating FROM reflections WHERE id = ?",
            (out["reflection_id"],),
        ).fetchone()
        assert row["notebook_id"] == NB
        assert "Hyrum" in row["body"]
        assert row["grasp_rating"] == 3
    finally:
        conn.close()


def _correct_index(prep, q_index):
    """Read the correct option index from the session file (test helper only)."""
    stored = json.loads((session._sessions_dir() / f"{prep['session_id']}.json").read_text())
    opts = stored["raw"]["questions"][q_index]["answerOptions"]
    return next(i for i, o in enumerate(opts) if o["isCorrect"])
