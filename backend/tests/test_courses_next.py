"""M3 course "what to do next" — the pure ranker + the GET /next endpoint.

The pure ``next_actions`` ranking is asserted on synthetic inputs (no DB/clock, like the study
planner); the endpoint is asserted against the bundled example with a fresh isolated store.
"""

from __future__ import annotations

import pytest

from app.courses.next_actions import next_actions

EXAMPLE_SLUG = "learning-how-to-learn"


def _course() -> dict:
    """2 lessons: l1 has a quiz + a flashcard deck, l2 has a capstone with a rubric."""
    return {
        "modules": [
            {"id": "m1", "title": "M1", "lessons": [
                {"id": "l1", "title": "Lesson one", "materials": [
                    {"type": "lesson", "path": "lessons/l1.md"},
                    {"type": "quiz", "title": "Q1", "path": "quizzes/l1.json"},
                    {"type": "flashcards", "title": "Deck 1", "path": "flashcards/l1.json"},
                ]},
                {"id": "l2", "title": "Lesson two", "materials": [
                    {"type": "capstone", "title": "Cap", "path": "capstones/l2.md",
                     "rubric": "rubrics/l2.json"},
                ]},
            ]},
        ],
    }


# -- pure ranker ---------------------------------------------------------------

def test_fresh_course_says_start():
    items = next_actions(_course(), {}, {}, {}, {})
    assert items[0]["kind"] == "lesson"
    assert items[0]["reason"] == "Start the course"
    assert items[0]["lesson_id"] == "l1"


def test_due_review_outranks_everything():
    quiz_stats = {"quizzes/l1.json": {"attempts": 1, "due_questions": 3}}
    items = next_actions(_course(), {"l1": True}, quiz_stats, {}, {})
    assert items[0]["kind"] == "quiz_review"
    assert items[0]["path"] == "quizzes/l1.json"
    assert "3 questions due" in items[0]["reason"]


def test_due_review_reason_singular():
    quiz_stats = {"quizzes/l1.json": {"attempts": 1, "due_questions": 1}}
    items = next_actions(_course(), {"l1": True}, quiz_stats, {}, {})
    assert "1 question due" in items[0]["reason"]


def test_due_flashcards_outrank_lessons_but_not_quiz_reviews():
    quiz_stats = {"quizzes/l1.json": {"attempts": 1, "due_questions": 2}}
    deck_stats = {"flashcards/l1.json": {"due_cards": 3}}
    items = next_actions(_course(), {}, quiz_stats, deck_stats, {}, limit=None)
    kinds = [it["kind"] for it in items]
    assert kinds.index("quiz_review") < kinds.index("flashcards_review") < kinds.index("lesson")
    fc = next(it for it in items if it["kind"] == "flashcards_review")
    assert fc["path"] == "flashcards/l1.json"
    assert "3 cards due" in fc["reason"]


def test_due_flashcards_reason_singular_and_untracked_deck_is_silent():
    # No due cards -> the deck never appears (a never-reviewed deck isn't nagged about).
    assert not any(
        it["kind"] == "flashcards_review"
        for it in next_actions(_course(), {}, {}, {"flashcards/l1.json": {"due_cards": 0}}, {})
    )
    items = next_actions(_course(), {}, {}, {"flashcards/l1.json": {"due_cards": 1}}, {})
    assert items[0]["kind"] == "flashcards_review"
    assert "1 card due" in items[0]["reason"]


def test_continue_points_at_first_unread_lesson():
    items = next_actions(_course(), {"l1": True}, {}, {}, {})
    lessons = [it for it in items if it["kind"] == "lesson"]
    assert lessons and lessons[0]["lesson_id"] == "l2"
    assert lessons[0]["reason"] == "Continue where you left off"


def test_quiz_new_only_when_its_lesson_done():
    # l1 not done -> no quiz_new for its quiz...
    assert not any(it["kind"] == "quiz_new" for it in next_actions(_course(), {}, {}, {}, {}))
    # ...l1 done + quiz never attempted -> quiz_new surfaces.
    items = next_actions(_course(), {"l1": True}, {"quizzes/l1.json": {"attempts": 0}}, {}, {})
    assert any(it["kind"] == "quiz_new" and it["path"] == "quizzes/l1.json" for it in items)


def test_project_surfaces_then_drops_after_assessing():
    done = {"l1": True, "l2": True}
    items = next_actions(_course(), done, {}, {}, {})
    assert any(it["kind"] == "project" and it["path"] == "capstones/l2.md" for it in items)
    # once an assessment exists for that path, it drops off.
    items2 = next_actions(_course(), done, {}, {}, {"capstones/l2.md": {"self_rating": 3}})
    assert not any(it["kind"] == "project" for it in items2)


def test_project_hidden_until_its_lesson_done():
    items = next_actions(_course(), {"l1": True}, {}, {}, {})  # l2 not done
    assert not any(it["kind"] == "project" for it in items)


def test_limit_caps_items():
    quiz_stats = {"quizzes/l1.json": {"attempts": 1, "due_questions": 2}}
    done = {"l1": True, "l2": True}
    assert len(next_actions(_course(), done, quiz_stats, {}, {}, limit=None)) >= 2
    assert len(next_actions(_course(), done, quiz_stats, {}, {}, limit=1)) == 1


def test_empty_course_yields_nothing():
    assert next_actions({"modules": []}, {}, {}, {}, {}) == []


# -- endpoint ------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("COURSES_DIR", str(tmp_path / "hub" / "courses"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def test_next_endpoint_fresh_course(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/next")
    assert r.status_code == 200
    body = r.json()
    assert body["all_done"] is False
    assert body["items"][0]["kind"] == "lesson"
    assert body["items"][0]["lesson_id"] == "m1l1"


def test_next_endpoint_unknown_course_404(client):
    assert client.get("/api/courses/nope/next").status_code == 404


def test_next_surfaces_and_clears_capstone(client):
    for lid in ["m1l1", "m1l2", "m2l1", "m2l2"]:
        client.post(f"/api/courses/{EXAMPLE_SLUG}/lessons/{lid}/complete", json={"completed": True})
    items = client.get(f"/api/courses/{EXAMPLE_SLUG}/next").json()["items"]
    assert any(it["kind"] == "project" and it["path"] == "capstones/m2l2.md" for it in items)

    client.post(
        f"/api/courses/{EXAMPLE_SLUG}/assess",
        params={"path": "capstones/m2l2.md"},
        json={"ratings": {"Spacing schedule": "Meets"}, "note": ""},
    )
    items2 = client.get(f"/api/courses/{EXAMPLE_SLUG}/next").json()["items"]
    assert not any(it["kind"] == "project" for it in items2)
