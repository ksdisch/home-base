"""Phase-7 (Courses M3) — SM-2-scheduled flashcard review.

A course flashcard deck is reviewed card-by-card: flip → self-grade (again/hard/good/easy →
SM-2 quality 2/3/4/5) → the card's state advances in the hub-owned ``flashcard_mastery`` table
(schema v4). Content stays on disk; only review state lands in SQLite; due counts are derived.

These tests pin: the ``/flashcards`` read surface (per-deck tracked/due counts); the session
fetch (keyed cards, due-first ordering); the grade round-trip mapping all four grades to the
right SM-2 transitions; due counts surfacing once the interval elapses (injected clock); calm
failure on traversal / non-deck paths; 404 on unknown card, 422 on a junk grade; duplicate-front
dedupe; and that flashcard reviews stay OFF the notebook surfaces while still counting toward
the activity streak.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import pytest

EXAMPLE_SLUG = "learning-how-to-learn"
DECK_PATH = "flashcards/m1l2.json"


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


def _key(front: str) -> str:
    """The card-identity recipe, computed independently of the code under test."""
    return hashlib.sha1(front.encode("utf-8")).hexdigest()[:16]


def _deck_cards() -> list:
    from app.courses import material_path

    return json.loads(material_path(EXAMPLE_SLUG, DECK_PATH).read_text(encoding="utf-8"))


def _session(client) -> dict:
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/session", params={"path": DECK_PATH}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _grade(client, card_key: str, grade: str) -> dict:
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/grade",
        json={"path": DECK_PATH, "card_key": card_key, "grade": grade},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _deck_state(client) -> dict:
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/flashcards")
    assert r.status_code == 200, r.text
    return next(d for d in r.json()["decks"] if d["path"] == DECK_PATH)


# -- the read surface ----------------------------------------------------------

def test_flashcards_lists_deck_with_zeroed_state(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/flashcards")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == EXAMPLE_SLUG and body["generated_at"]
    d = next(d for d in body["decks"] if d["path"] == DECK_PATH)
    assert d["lesson_id"] == "m1l2"
    assert d["module_id"]
    assert d["title"]
    assert d["card_count"] == len(_deck_cards())
    assert d["tracked_cards"] == 0
    assert d["due_cards"] == 0
    assert d["last_review_at"] is None


def test_flashcards_unknown_course_is_404(client):
    assert client.get("/api/courses/nope/flashcards").status_code == 404


# -- the session fetch ----------------------------------------------------------

def test_session_returns_every_card_keyed_and_new(client):
    body = _session(client)
    assert body["ok"] is True
    assert body["slug"] == EXAMPLE_SLUG and body["path"] == DECK_PATH
    cards = _deck_cards()
    assert body["total"] == len(cards)
    assert body["due_count"] == len(cards)  # never reviewed → everything is due
    by_key = {c["card_key"]: c for c in body["cards"]}
    for raw in cards:
        c = by_key[_key(raw["front"])]  # identity = sha1(front)[:16], like question_key
        assert c["front"] == raw["front"]
        assert c["back"] == raw["back"]
        assert c["new"] is True
        assert c["due"] is True
        assert c["reps"] == 0
        assert c["due_at"] is None


def test_session_orders_reviewed_not_due_cards_last(client):
    first_front = _deck_cards()[0]["front"]
    _grade(client, _key(first_front), "good")  # due tomorrow → not due right now
    body = _session(client)
    last = body["cards"][-1]
    assert last["card_key"] == _key(first_front)
    assert last["new"] is False
    assert last["due"] is False
    assert last["reps"] == 1
    assert body["due_count"] == body["total"] - 1
    # The still-new cards keep their due flag and lead the ordering.
    assert all(c["due"] for c in body["cards"][:-1])


# -- grade round-trip: the four grades map to the right SM-2 transitions --------

def test_good_first_rep_schedules_one_day_out(client):
    from app.store import scheduler

    key = _key(_deck_cards()[0]["front"])
    res = _grade(client, key, "good")
    assert res["card_key"] == key
    assert res["grade"] == "good"
    assert res["reps"] == 1
    assert res["lapses"] == 0
    assert res["interval_days"] == scheduler.FIRST_INTERVAL_DAYS
    assert res["due_at"] is not None
    # q=4 ("good") is SM-2's neutral grade: ease stays exactly at its prior value.
    assert res["ease"] == pytest.approx(scheduler.INITIAL_EASE)

    d = _deck_state(client)
    assert d["tracked_cards"] == 1
    assert d["due_cards"] == 0  # just reviewed → due tomorrow, not now
    assert d["last_review_at"] is not None


def test_again_is_a_lapse(client):
    key = _key(_deck_cards()[0]["front"])
    _grade(client, key, "good")
    res = _grade(client, key, "again")
    assert res["reps"] == 0
    assert res["lapses"] == 1
    from app.store import scheduler

    assert res["interval_days"] == scheduler.LAPSE_INTERVAL_DAYS
    assert res["ease"] < scheduler.INITIAL_EASE  # ease penalized


def test_easy_outgrows_good_outgrows_hard(client):
    from app.store import scheduler

    cards = _deck_cards()
    k_hard, k_good, k_easy = (_key(cards[i]["front"]) for i in range(3))
    hard = _grade(client, k_hard, "hard")
    good = _grade(client, k_good, "good")
    easy = _grade(client, k_easy, "easy")
    # All three are passes (first rep → same 1d interval), but ease diverges by grade.
    assert hard["reps"] == good["reps"] == easy["reps"] == 1
    assert hard["ease"] < good["ease"] < easy["ease"]
    assert easy["ease"] > scheduler.INITIAL_EASE


def test_state_persists_across_grades_and_due_surfaces_later(client):
    key = _key(_deck_cards()[0]["front"])
    first = _grade(client, key, "good")
    second = _grade(client, key, "good")
    assert second["reps"] == 2
    assert second["interval_days"] > first["interval_days"]

    from app.store import course_flashcard_progress, scheduler

    now = scheduler.now_utc()
    assert course_flashcard_progress(EXAMPLE_SLUG, now=now)[DECK_PATH]["due_cards"] == 0
    later = course_flashcard_progress(EXAMPLE_SLUG, now=now + timedelta(days=400))
    assert later[DECK_PATH]["due_cards"] == 1
    assert later[DECK_PATH]["tracked_cards"] == 1


def test_grade_writes_only_flashcard_mastery(client):
    """Flashcard reviews are not quiz attempts — the quiz-side tables stay empty."""
    _grade(client, _key(_deck_cards()[0]["front"]), "good")
    from app.store import connect

    conn = connect()
    try:
        n_fm = conn.execute("SELECT COUNT(*) c FROM flashcard_mastery").fetchone()["c"]
        n_attempts = conn.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"]
        n_qm = conn.execute("SELECT COUNT(*) c FROM question_mastery").fetchone()["c"]
        n_tm = conn.execute("SELECT COUNT(*) c FROM topic_mastery").fetchone()["c"]
    finally:
        conn.close()
    assert n_fm == 1
    assert n_attempts == 0 and n_qm == 0 and n_tm == 0


# -- failure modes ---------------------------------------------------------------

def test_session_rejects_path_traversal(client):
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/session",
        params={"path": "../../../../etc/passwd"},
    )
    assert r.status_code == 200  # calm, not a crash
    assert r.json()["ok"] is False


def test_session_non_deck_path_is_calm_error(client):
    # A real lesson markdown file: exists, but isn't a flashcard deck.
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/session", params={"path": "lessons/m1l1.md"}
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_session_unknown_course_is_calm_error(client):
    r = client.get("/api/courses/nope/flashcards/session", params={"path": DECK_PATH})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_grade_unknown_card_is_404(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/grade",
        json={"path": DECK_PATH, "card_key": "0" * 16, "grade": "good"},
    )
    assert r.status_code == 404


def test_grade_junk_grade_is_422(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/grade",
        json={"path": DECK_PATH, "card_key": _key(_deck_cards()[0]["front"]), "grade": "meh"},
    )
    assert r.status_code == 422


def test_grade_traversal_path_is_404(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/flashcards/grade",
        json={"path": "../../../etc/passwd", "card_key": "0" * 16, "grade": "good"},
    )
    assert r.status_code == 404


# -- duplicate fronts dedupe ------------------------------------------------------

def test_duplicate_fronts_dedupe_to_one_card(client, tmp_path):
    slug = "dupes"
    course = tmp_path / "hub" / "courses" / slug
    (course / "flashcards").mkdir(parents=True)
    (course / "course.json").write_text(
        json.dumps(
            {
                "title": "Dupes",
                "modules": [
                    {
                        "id": "m1",
                        "title": "M1",
                        "lessons": [
                            {
                                "id": "m1l1",
                                "title": "L1",
                                "materials": [
                                    {"type": "flashcards", "title": "Deck",
                                     "path": "flashcards/d.json"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (course / "flashcards" / "d.json").write_text(
        json.dumps(
            [
                {"front": "Same front", "back": "first wins"},
                {"front": "Same front", "back": "dropped"},
                {"front": "Other", "back": "kept"},
            ]
        ),
        encoding="utf-8",
    )
    r = client.get(f"/api/courses/{slug}/flashcards/session", params={"path": "flashcards/d.json"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["total"] == 2
    backs = {c["card_key"]: c["back"] for c in body["cards"]}
    assert backs[_key("Same front")] == "first wins"


# -- the boundary: flashcard reviews don't pollute the notebook surfaces ---------

def test_reviews_excluded_from_notebook_surfaces_but_count_as_activity(client):
    for raw in _deck_cards():
        _grade(client, _key(raw["front"]), "again")  # misses everywhere — max pollution risk

    review = client.get("/api/review").json()
    assert review["items"] == []

    plan = client.get("/api/study-plan").json()
    assert plan["segments"] == []

    prog = client.get("/api/progress").json()
    assert prog["topics"] == [] and prog["shaky"] == []
    assert prog["summary"]["topics_practiced"] == 0
    assert prog["summary"]["attempts_total"] == 0
    # ...but the day still registers learning activity (the streak is source-agnostic).
    assert prog["summary"]["last_activity"] is not None
    assert any(day["count"] > 0 for day in prog["activity"])
