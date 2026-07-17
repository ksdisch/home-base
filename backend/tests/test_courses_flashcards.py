"""Courses M2 remainder — the flashcard review surface + per-card SM-2.

A flashcard self-grade advances the SAME per-item scheduler a quiz answer does — one
``question_mastery`` row per card, keyed ``(course:<slug>, <deck path>, <card key>)`` — with NO
schema change. These tests pin: the decks read surface; per-card state aligned to the deck file's
order; the review round-trip (good = growing intervals, again = a lapse with consecutive-miss
tracking); server-side card identity (duplicate fronts stay distinct); calm failure modes
(traversal, non-deck paths, bad index/rating); that deck rows never masquerade as quizzes; the
next-up integration; and the M2 boundary — flashcard rows stay OUT of the notebook surfaces while
still counting toward the activity streak.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

EXAMPLE_SLUG = "learning-how-to-learn"
DECK_PATH = "flashcards/m1l2.json"
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


def _review(client, index: int, rating: str, slug: str = EXAMPLE_SLUG, path: str = DECK_PATH) -> dict:
    r = client.post(
        f"/api/courses/{slug}/flashcards/review",
        params={"path": path},
        json={"index": index, "rating": rating},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _deck(client, slug: str = EXAMPLE_SLUG, path: str = DECK_PATH) -> dict:
    body = client.get(f"/api/courses/{slug}/flashcards").json()
    return next(d for d in body["decks"] if d["path"] == path)


# -- the decks read surface ------------------------------------------------------

def test_decks_listed_with_zeroed_stats(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/flashcards")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == EXAMPLE_SLUG and body["generated_at"]
    d = next(d for d in body["decks"] if d["path"] == DECK_PATH)
    assert d["lesson_id"] == "m1l2"
    assert d["module_id"]
    assert d["card_count"] == 6
    assert d["tracked_cards"] == 0
    assert d["due_cards"] == 0


def test_flashcards_unknown_course_is_404(client):
    assert client.get("/api/courses/nope/flashcards").status_code == 404


def test_state_all_new_before_any_review(client):
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/state", params={"path": DECK_PATH}
    )
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert [c["index"] for c in cards] == list(range(6))
    assert all(not c["tracked"] and not c["due"] and c["due_at"] is None for c in cards)


# -- the review round-trip advances SM-2 ------------------------------------------

def test_review_good_tracks_the_card_and_schedules_it_out(client):
    res = _review(client, 0, "good")
    assert res["tracked"] is True
    assert res["reps"] == 1 and res["lapses"] == 0
    assert res["due"] is False and res["due_at"]

    cards = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/state", params={"path": DECK_PATH}
    ).json()["cards"]
    assert cards[0]["tracked"] and not cards[0]["due"]
    assert not cards[1]["tracked"]  # only the graded card gained state

    d = _deck(client)
    assert d["tracked_cards"] == 1
    assert d["due_cards"] == 0  # just reviewed -> next review is in the future


def test_review_again_is_a_lapse_with_miss_count(client):
    res = _review(client, 1, "again")
    assert res["reps"] == 0 and res["lapses"] == 1

    from app.store import connect

    conn = connect()
    try:
        row = conn.execute(
            "SELECT score, miss_count, lapses FROM question_mastery "
            "WHERE notebook_id = ? AND quiz_artifact_id = ?",
            (COURSE_NB, DECK_PATH),
        ).fetchone()
    finally:
        conn.close()
    assert row["score"] == 0.0
    assert row["miss_count"] == 1
    assert row["lapses"] == 1


def test_repeat_good_grows_the_interval(client):
    first = _review(client, 0, "good")
    second = _review(client, 0, "good")
    assert second["reps"] == 2
    assert second["due_at"] > first["due_at"]  # 1d -> ~6d; ISO-ish strings compare in time order


def test_reviewed_cards_come_due_after_the_interval_elapses(client):
    _review(client, 0, "good")
    _review(client, 1, "good")
    from app.store import course_flashcard_states, course_quiz_progress, scheduler

    now = scheduler.now_utc()
    states = course_flashcard_states(EXAMPLE_SLUG, DECK_PATH, now=now)
    assert len(states) == 2 and not any(s["due"] for s in states.values())
    later = course_flashcard_states(EXAMPLE_SLUG, DECK_PATH, now=now + timedelta(days=400))
    assert all(s["due"] for s in later.values())
    # The shared per-artifact aggregation sees the deck's rows too (it powers the due chips).
    agg = course_quiz_progress(EXAMPLE_SLUG, now=now + timedelta(days=400))[DECK_PATH]
    assert agg["tracked_questions"] == 2 and agg["due_questions"] == 2


# -- server-side card identity -----------------------------------------------------

def test_duplicate_fronts_get_distinct_keys(client, tmp_path):
    course_dir = tmp_path / "hub" / "courses" / "deck-course"
    (course_dir / "flashcards").mkdir(parents=True)
    (course_dir / "course.json").write_text(
        json.dumps(
            {
                "title": "Deck Course",
                "modules": [
                    {"id": "m1", "title": "M", "lessons": [
                        {"id": "l1", "title": "L", "materials": [
                            {"type": "flashcards", "title": "Dupes", "path": "flashcards/d.json"},
                        ]},
                    ]},
                ],
            }
        ),
        encoding="utf-8",
    )
    (course_dir / "flashcards" / "d.json").write_text(
        json.dumps([{"front": "Same front", "back": "A"}, {"front": "Same front", "back": "B"}]),
        encoding="utf-8",
    )

    _review(client, 0, "good", slug="deck-course", path="flashcards/d.json")
    _review(client, 1, "again", slug="deck-course", path="flashcards/d.json")

    cards = client.get(
        "/api/courses/deck-course/flashcards/state", params={"path": "flashcards/d.json"}
    ).json()["cards"]
    assert cards[0]["reps"] == 1 and cards[0]["lapses"] == 0
    assert cards[1]["reps"] == 0 and cards[1]["lapses"] == 1  # didn't clobber card 0's row

    from app.store import connect

    conn = connect()
    try:
        n = conn.execute(
            "SELECT COUNT(*) c FROM question_mastery WHERE notebook_id = ?",
            ("course:deck-course",),
        ).fetchone()["c"]
    finally:
        conn.close()
    assert n == 2


# -- failure modes are calm ---------------------------------------------------------

def test_state_rejects_path_traversal(client):
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/state",
        params={"path": "../../../../etc/passwd"},
    )
    assert r.status_code == 404


def test_state_rejects_non_flashcards_material(client):
    # A real quiz file: exists, is a declared material, but isn't a flashcards deck.
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/state", params={"path": "quizzes/m2l2.json"}
    )
    assert r.status_code == 404


def test_review_rejects_bad_rating(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/review",
        params={"path": DECK_PATH},
        json={"index": 0, "rating": "easy-peasy"},
    )
    assert r.status_code == 422


def test_review_rejects_out_of_range_index(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/review",
        params={"path": DECK_PATH},
        json={"index": 99, "rating": "good"},
    )
    assert r.status_code == 422
    r2 = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/review",
        params={"path": DECK_PATH},
        json={"index": -1, "rating": "good"},
    )
    assert r2.status_code == 422


def test_review_unknown_course_is_404(client):
    r = client.post(
        "/api/courses/nope/flashcards/review",
        params={"path": DECK_PATH},
        json={"index": 0, "rating": "good"},
    )
    assert r.status_code == 404


# -- decks and quizzes stay distinct surfaces ----------------------------------------

def test_deck_rows_never_masquerade_as_quizzes(client):
    _review(client, 0, "good")
    quizzes = client.get(f"/api/courses/{EXAMPLE_SLUG}/quizzes").json()["quizzes"]
    assert all(q["path"] != DECK_PATH for q in quizzes)
    # The real quiz's stats are untouched by the deck's rows.
    q = next(q for q in quizzes if q["path"] == "quizzes/m2l2.json")
    assert q["attempts"] == 0 and q["tracked_questions"] == 0


# -- next-up integration ---------------------------------------------------------------

def test_next_surfaces_due_flashcards(client):
    # Backdate a "good" review so its 1-day interval has already elapsed by real now.
    from app.courses import material_path
    from app.quiz.session import question_key
    from app.store import record_flashcard_review, scheduler

    deck = json.loads(material_path(EXAMPLE_SLUG, DECK_PATH).read_text(encoding="utf-8"))
    key = question_key(str(deck[0]["front"]), 0)
    record_flashcard_review(
        EXAMPLE_SLUG, DECK_PATH, key, "good", now=scheduler.now_utc() - timedelta(days=2)
    )

    assert _deck(client)["due_cards"] == 1
    items = client.get(f"/api/courses/{EXAMPLE_SLUG}/next").json()["items"]
    fc = next(it for it in items if it["kind"] == "flashcards_review")
    assert fc["path"] == DECK_PATH
    assert "1 card due" in fc["reason"]


# -- the boundary: courses don't pollute the notebook surfaces ---------------------------

def test_flashcard_reviews_excluded_from_notebook_surfaces_but_count_as_activity(client):
    _review(client, 0, "again")  # a lapse is the strongest pollution case
    _review(client, 1, "good")

    review = client.get("/api/review").json()
    assert all(not it["notebook_id"].startswith("course:") for it in review["items"])

    plan = client.get("/api/study-plan").json()
    assert all(not s["notebook_id"].startswith("course:") for s in plan["segments"])

    prog = client.get("/api/progress").json()
    assert all(not t["notebook_id"].startswith("course:") for t in prog["topics"])
    assert all(not s["notebook_id"].startswith("course:") for s in prog["shaky"])
    assert prog["summary"]["topics_practiced"] == 0
    assert prog["summary"]["attempts_total"] == 0
    # ...but the day still registers learning activity (the streak is source-agnostic).
    assert prog["summary"]["last_activity"] is not None
    assert any(day["count"] > 0 for day in prog["activity"])
