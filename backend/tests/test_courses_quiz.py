"""Phase-7 (Courses M2) — course quizzes in the in-hub player + per-course SM-2.

A course quiz is played through the *same* answer-key-free session machinery as a NotebookLM quiz
(via ``from_file``), graded by the same offline oracle, and recorded under the ``course:<slug>``
namespace so the existing SM-2 scheduler tracks it per course — with NO schema change.

These tests pin: the answer-key-free invariant on the course player view; the grade round-trip
persisting a course-scoped attempt + advancing ``question_mastery`` SM-2; the ``/quizzes`` read
surface; path-traversal rejection; calm failure on a non-quiz path; due-question counting against
an injected future clock; and — crucially — that course attempts DON'T leak into the topic-only
surfaces (``/review``, ``/progress``) while now *surfacing* in the cross-notebook ``/study-plan``
(so course quizzes get the same spaced-repetition resurfacing topics do) and still counting toward
the activity streak.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

EXAMPLE_SLUG = "learning-how-to-learn"
QUIZ_PATH = "quizzes/m2l2.json"
COURSE_NB = f"course:{EXAMPLE_SLUG}"


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Fresh DB; empty user COURSES_DIR -> the bundled example course is what the API serves.
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("COURSES_DIR", str(tmp_path / "hub" / "courses"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    c = _client()
    try:
        yield c
    finally:
        get_settings.cache_clear()


def _correct_answers() -> dict:
    """The keyed correct option index per question, read straight from the example quiz file."""
    from app.courses import material_path

    quiz = json.loads(material_path(EXAMPLE_SLUG, QUIZ_PATH).read_text(encoding="utf-8"))
    return {
        i: next(oi for oi, o in enumerate(q["answerOptions"]) if o.get("isCorrect"))
        for i, q in enumerate(quiz["questions"])
    }


def _prepare(client) -> dict:
    r = client.post(f"/api/courses/{EXAMPLE_SLUG}/quiz/prepare", params={"path": QUIZ_PATH})
    assert r.status_code == 200, r.text
    return r.json()


def _take(client, answers: dict) -> dict:
    """Prepare + grade the example course quiz with ``{q_index: option_index}`` answers."""
    prep = _prepare(client)
    payload = {"session_id": prep["session_id"], "answers": {str(k): v for k, v in answers.items()}}
    g = client.post("/api/quiz/grade", json=payload)
    assert g.status_code == 200, g.text
    return g.json()


# -- the read surface ----------------------------------------------------------

def test_quizzes_lists_course_quiz_with_zeroed_stats(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/quizzes")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == EXAMPLE_SLUG and body["generated_at"]
    q = next(q for q in body["quizzes"] if q["path"] == QUIZ_PATH)
    assert q["lesson_id"] == "m2l2"
    assert q["module_id"]
    assert q["question_count"] == 5
    assert q["attempts"] == 0
    assert q["last_score"] is None
    assert q["tracked_questions"] == 0
    assert q["due_questions"] == 0


def test_quizzes_unknown_course_is_404(client):
    assert client.get("/api/courses/nope/quizzes").status_code == 404


# -- the player view is answer-key-free ----------------------------------------

def test_prepare_is_answer_key_free(client):
    body = _prepare(client)
    assert body["ok"] is True
    assert body["session_id"]
    assert body["total"] == 5
    assert body["notebook_id"] == COURSE_NB
    assert body["quiz_artifact_id"] == QUIZ_PATH
    # The keyed fields must NEVER reach the client — assert on the raw serialized blob.
    blob = json.dumps(body)
    assert "isCorrect" not in blob
    assert "rationale" not in blob
    for q in body["questions"]:
        assert q["question"] and isinstance(q["options"], list) and len(q["options"]) >= 2


# -- grade round-trip records a course-scoped attempt + SM-2 --------------------

def test_grade_full_score_records_course_scoped_attempt_and_sm2(client):
    res = _take(client, _correct_answers())
    assert res["score"] == 5 and res["total"] == 5
    # The review payload (post-grade) is where rationales are allowed to appear.
    assert len(res["review"]) == 5

    from app.store import connect

    conn = connect()
    try:
        n_attempts = conn.execute(
            "SELECT COUNT(*) c FROM attempts WHERE notebook_id=?", (COURSE_NB,)
        ).fetchone()["c"]
        n_qm = conn.execute(
            "SELECT COUNT(*) c FROM question_mastery WHERE notebook_id=?", (COURSE_NB,)
        ).fetchone()["c"]
        # quiz_artifact_id is the material path, so SM-2 is keyed per course quiz.
        qids = {
            r["quiz_artifact_id"]
            for r in conn.execute(
                "SELECT DISTINCT quiz_artifact_id FROM question_mastery WHERE notebook_id=?",
                (COURSE_NB,),
            )
        }
    finally:
        conn.close()
    assert n_attempts == 1
    assert n_qm == 5  # one SM-2 row per question
    assert qids == {QUIZ_PATH}

    q = next(
        q for q in client.get(f"/api/courses/{EXAMPLE_SLUG}/quizzes").json()["quizzes"]
        if q["path"] == QUIZ_PATH
    )
    assert q["attempts"] == 1
    assert q["last_score"] == 5 and q["last_total"] == 5
    assert q["last_pct"] == 100.0
    assert q["tracked_questions"] == 5
    # Just answered (correctly) → next review is in the future, so nothing is due *right now*.
    assert q["due_questions"] == 0


def test_quiz_state_tracks_latest_attempt(client):
    _take(client, {i: (idx + 1) % 4 for i, idx in _correct_answers().items()})  # mostly wrong
    _take(client, _correct_answers())  # then a perfect run
    q = next(
        q for q in client.get(f"/api/courses/{EXAMPLE_SLUG}/quizzes").json()["quizzes"]
        if q["path"] == QUIZ_PATH
    )
    assert q["attempts"] == 2
    assert q["last_score"] == 5  # the *latest* attempt, not the best/first


# -- due counting against an injected future clock -----------------------------

def test_due_questions_surface_after_the_interval_elapses(client):
    _take(client, _correct_answers())
    from app.store import course_quiz_progress, scheduler

    # Right now: nothing due. Far in the future: every tracked question is overdue.
    now = scheduler.now_utc()
    assert course_quiz_progress(EXAMPLE_SLUG, now=now)[QUIZ_PATH]["due_questions"] == 0
    later = course_quiz_progress(EXAMPLE_SLUG, now=now + timedelta(days=400))
    assert later[QUIZ_PATH]["due_questions"] == 5
    assert later[QUIZ_PATH]["tracked_questions"] == 5


# -- failure modes are calm (never a 500) --------------------------------------

def test_prepare_rejects_path_traversal(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/quiz/prepare", params={"path": "../../../../etc/passwd"}
    )
    assert r.status_code == 200  # calm, not a crash
    assert r.json()["ok"] is False


def test_prepare_non_quiz_path_is_calm_error(client):
    # A real lesson markdown file: exists, but isn't a quiz → json/contract failure, not a 500.
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/quiz/prepare", params={"path": "lessons/m1l1.md"}
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_prepare_unknown_course_is_calm_error(client):
    r = client.post("/api/courses/nope/quiz/prepare", params={"path": QUIZ_PATH})
    assert r.status_code == 200
    assert r.json()["ok"] is False


# -- the boundary: courses stay out of the topic-only surfaces, but join the plan --------

def test_course_attempt_stays_off_topic_surfaces_but_joins_the_study_plan(client):
    # A miss leaves a shaky question + a topic_mastery row — the strongest pollution case.
    _take(client, {i: (idx + 1) % 4 for i, idx in _correct_answers().items()})

    # Still invisible to the topic-only queue (courses keep their own /review surface)...
    review = client.get("/api/review").json()
    assert all(not it["notebook_id"].startswith("course:") for it in review["items"])

    # ...but the course quiz now DOES join the cross-notebook study plan (spaced-rep resurfacing).
    plan = client.get("/api/study-plan").json()
    assert any(s["notebook_id"] == COURSE_NB for s in plan["segments"])

    prog = client.get("/api/progress").json()
    assert all(not t["notebook_id"].startswith("course:") for t in prog["topics"])
    assert all(not s["notebook_id"].startswith("course:") for s in prog["shaky"])
    # Invisible to the notebook headline counters...
    assert prog["summary"]["topics_practiced"] == 0
    assert prog["summary"]["attempts_total"] == 0
    # ...but the day still registers learning activity (the streak is source-agnostic).
    assert prog["summary"]["last_activity"] is not None
    assert any(day["count"] > 0 for day in prog["activity"])


def test_study_plan_titles_the_course_segment_with_the_course_title(client):
    _take(client, {i: (idx + 1) % 4 for i, idx in _correct_answers().items()})
    plan = client.get("/api/study-plan").json()
    seg = next(s for s in plan["segments"] if s["notebook_id"] == COURSE_NB)
    assert seg["title"] == "Learning How to Learn"  # course title, not the raw 'course:<slug>' id
    assert seg["quiz_artifact_id"] == QUIZ_PATH
    assert seg["topic_url"] is None  # course segments carry no single topic_url; client derives it
