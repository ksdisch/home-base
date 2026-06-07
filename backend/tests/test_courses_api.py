"""Phase-6 courses HTTP surface — list/detail/material/complete over the on-disk sidecars.

Each test isolates a fresh SQLite store (so progress counts are deterministic); COURSES_DIR is
left empty so the *bundled example* course is what the API serves. Asserts the read contract,
the lesson-complete → progress round-trip, path-traversal rejection, and 404s.
"""

from __future__ import annotations

import pytest

EXAMPLE_SLUG = "learning-how-to-learn"


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Fresh DB; empty user COURSES_DIR -> the bundled example is served.
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


# -- list ----------------------------------------------------------------------

def test_list_returns_bundled_example(client):
    r = client.get("/api/courses")
    assert r.status_code == 200
    body = r.json()
    assert body["generated_at"]
    example = next(c for c in body["courses"] if c["slug"] == EXAMPLE_SLUG)
    assert example["lesson_count"] == 4
    assert example["module_count"] == 2
    assert example["progress_pct"] == 0
    assert example["material_counts"]["lesson"] == 4


# -- detail --------------------------------------------------------------------

def test_detail_has_full_structure(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}")
    assert r.status_code == 200
    course = r.json()
    assert len(course["modules"]) == 2
    first_lesson = course["modules"][0]["lessons"][0]
    assert first_lesson["id"] == "m1l1"
    assert first_lesson["completed"] is False
    assert first_lesson["objectives"]


def test_detail_unknown_course_is_404(client):
    assert client.get("/api/courses/does-not-exist").status_code == 404


# -- complete a lesson ---------------------------------------------------------

def test_complete_lesson_moves_progress(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/lessons/m1l1/complete", json={"completed": True}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["completed"] is True
    assert body["progress_pct"] == 25  # 1 of 4 lessons

    # reflected in detail
    course = client.get(f"/api/courses/{EXAMPLE_SLUG}").json()
    assert course["progress_pct"] == 25
    done = course["modules"][0]["lessons"][0]
    assert done["completed"] is True


def test_uncomplete_lesson_returns_to_zero(client):
    client.post(f"/api/courses/{EXAMPLE_SLUG}/lessons/m1l1/complete", json={"completed": True})
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/lessons/m1l1/complete", json={"completed": False}
    )
    assert r.json()["progress_pct"] == 0


def test_complete_unknown_lesson_is_404(client):
    r = client.post(
        f"/api/courses/{EXAMPLE_SLUG}/lessons/nope/complete", json={"completed": True}
    )
    assert r.status_code == 404


def test_complete_logs_activity_for_streaks(client):
    from app.store import connect

    client.post(f"/api/courses/{EXAMPLE_SLUG}/lessons/m1l1/complete", json={"completed": True})
    conn = connect()
    try:
        n = conn.execute(
            "SELECT COUNT(*) c FROM activity WHERE kind = 'lesson_completed'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert n == 1


# -- materials -----------------------------------------------------------------

def test_material_text_fetch(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/materials", params={"path": "lessons/m1l1.md"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "text"
    assert "forgetting" in body["text"].lower()


def test_material_json_fetch(client):
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/materials", params={"path": "quizzes/m2l2.json"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "json"
    assert len(body["data"]["questions"]) == 5


def test_material_traversal_is_404(client):
    r = client.get(
        f"/api/courses/{EXAMPLE_SLUG}/materials", params={"path": "../../config.py"}
    )
    assert r.status_code == 404


def test_material_missing_is_404(client):
    r = client.get(f"/api/courses/{EXAMPLE_SLUG}/materials", params={"path": "lessons/x.md"})
    assert r.status_code == 404
