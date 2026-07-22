"""GET /api/paths/{id} + step coverage/confidence writes (M8), over the bundled Jacobian fixture.

Each test isolates a fresh SQLite store (deterministic axes); PATHS_DIR is left empty so the
*bundled example path* is what the API serves — the same posture as the courses API tests.
"""

from __future__ import annotations

import pytest

JACOBIAN = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4"


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Fresh DB; empty user PATHS_DIR -> the bundled Jacobian example path is served.
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("PATHS_DIR", str(tmp_path / "hub" / "paths"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    c = _client()
    try:
        yield c
    finally:
        get_settings.cache_clear()


def test_get_path_cold_start(client):
    r = client.get(f"/api/paths/{JACOBIAN}")
    assert r.status_code == 200
    b = r.json()
    assert b["notebook_id"] == JACOBIAN
    assert b["step_count"] == 9
    assert b["completed_steps"] == 0
    assert b["progress_pct"] == 0
    assert b["mastery"] is None  # never tested -> honest em-dash, not an inflated grade
    assert b["confidence"] is None
    assert all(s["completed"] is False for s in b["steps"])


def test_unknown_topic_404(client):
    assert client.get("/api/paths/not-a-real-notebook").status_code == 404


def test_completing_a_step_moves_coverage(client):
    r = client.post(f"/api/paths/{JACOBIAN}/steps/ep1/complete", json={"completed": True})
    assert r.status_code == 200
    b = r.json()
    assert b["completed_steps"] == 1
    assert b["progress_pct"] == round(1 / 9 * 100)
    assert next(s for s in b["steps"] if s["id"] == "ep1")["completed"] is True
    # unmarking flips it back
    b2 = client.post(f"/api/paths/{JACOBIAN}/steps/ep1/complete", json={"completed": False}).json()
    assert b2["completed_steps"] == 0


def test_confidence_sets_the_third_axis(client):
    r = client.post(f"/api/paths/{JACOBIAN}/steps/ep1/confidence", json={"rating": 4})
    assert r.status_code == 200
    b = r.json()
    assert b["confidence"] == 4.0  # mean of a single rating
    assert next(s for s in b["steps"] if s["id"] == "ep1")["confidence"] == 4


def test_confidence_out_of_range_is_422(client):
    r = client.post(f"/api/paths/{JACOBIAN}/steps/ep1/confidence", json={"rating": 9})
    assert r.status_code == 422


def test_write_to_unknown_step_is_404(client):
    r = client.post(f"/api/paths/{JACOBIAN}/steps/nope/complete", json={"completed": True})
    assert r.status_code == 404


def test_coverage_and_confidence_are_independent_axes(client):
    # completing a step does not set confidence, and vice-versa — they are distinct signals
    client.post(f"/api/paths/{JACOBIAN}/steps/ep1/complete", json={"completed": True})
    b = client.get(f"/api/paths/{JACOBIAN}").json()
    ep1 = next(s for s in b["steps"] if s["id"] == "ep1")
    assert ep1["completed"] is True and ep1["confidence"] is None
    assert b["progress_pct"] > 0 and b["confidence"] is None
