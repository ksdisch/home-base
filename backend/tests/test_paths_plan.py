"""GET /api/paths — the Plan's Continue lane (M8 #12): every composed path + its resume point.

Same posture as test_paths_api: a fresh SQLite store per test, PATHS_DIR left empty so the bundled
Jacobian example is what the API serves — which is exactly why the Continue lane is non-empty on a
cold clone / day one.
"""

from __future__ import annotations

import json

import pytest

JACOBIAN = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4"


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def paths_dir(tmp_path):
    return tmp_path / "hub" / "paths"


@pytest.fixture
def client(tmp_path, paths_dir, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("PATHS_DIR", str(paths_dir))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    c = _client()
    try:
        yield c
    finally:
        get_settings.cache_clear()


def _item_for(body, notebook_id):
    return next((it for it in body["items"] if it["notebook_id"] == notebook_id), None)


def test_continue_lane_non_empty_day_one(client):
    # No user paths generated yet -> the bundled Jacobian example still makes Continue non-empty.
    r = client.get("/api/paths")
    assert r.status_code == 200
    jac = _item_for(r.json(), JACOBIAN)
    assert jac is not None
    assert jac["step_count"] == 9
    assert jac["completed_steps"] == 0
    assert jac["progress_pct"] == 0
    assert jac["next_step"] is not None
    assert jac["next_step"]["completed"] is False


def test_next_step_is_the_first_incomplete_and_advances(client):
    full = client.get(f"/api/paths/{JACOBIAN}").json()
    first_id = full["steps"][0]["id"]
    # cold: the resume point is the very first step
    jac = _item_for(client.get("/api/paths").json(), JACOBIAN)
    assert jac["next_step"]["id"] == first_id

    # completing the first step advances the resume point + coverage
    client.post(f"/api/paths/{JACOBIAN}/steps/{first_id}/complete", json={"completed": True})
    jac2 = _item_for(client.get("/api/paths").json(), JACOBIAN)
    assert jac2["completed_steps"] == 1
    assert jac2["progress_pct"] == round(1 / 9 * 100)
    assert jac2["next_step"]["id"] != first_id


def test_fully_completed_path_has_no_next_step(client):
    steps = client.get(f"/api/paths/{JACOBIAN}").json()["steps"]
    for s in steps:
        client.post(f"/api/paths/{JACOBIAN}/steps/{s['id']}/complete", json={"completed": True})
    jac = _item_for(client.get("/api/paths").json(), JACOBIAN)
    assert jac["completed_steps"] == 9
    assert jac["progress_pct"] == 100
    assert jac["next_step"] is None


def test_a_generated_user_path_appears_with_its_resume_point(client, paths_dir):
    paths_dir.mkdir(parents=True, exist_ok=True)
    (paths_dir / "topic-x.json").write_text(
        json.dumps(
            {
                "title": "A Made Path",
                "topic": "x",
                "steps": [
                    {"id": "a", "kind": "intro", "title": "Start here", "body": "hi"},
                    {
                        "id": "b",
                        "kind": "audio",
                        "title": "Listen",
                        "artifact_id": "aud-1",
                        "artifact_type": "audio",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    item = _item_for(client.get("/api/paths").json(), "topic-x")
    assert item is not None
    assert item["title"] == "A Made Path"
    assert item["step_count"] == 2
    assert item["next_step"]["id"] == "a"


def test_malformed_path_file_is_skipped_never_500(client, paths_dir):
    paths_dir.mkdir(parents=True, exist_ok=True)
    (paths_dir / "broken.json").write_text("{ this is not valid json", encoding="utf-8")
    r = client.get("/api/paths")
    assert r.status_code == 200  # tolerant: a bad file never 500s the lane
    assert _item_for(r.json(), "broken") is None  # and it isn't surfaced
    assert _item_for(r.json(), JACOBIAN) is not None  # the good bundled example is still there


def test_confidence_is_the_mean_self_rating_none_until_rated(client):
    # The list endpoint carries the confidence axis for Progress (#13). Cold: nothing rated yet ->
    # an honest None (the Progress card shows an em-dash, not a fake 0).
    jac = _item_for(client.get("/api/paths").json(), JACOBIAN)
    assert jac["confidence"] is None

    # Rating two steps 5 and 2 -> the path's confidence is their mean (3.5), rated-steps only.
    steps = client.get(f"/api/paths/{JACOBIAN}").json()["steps"]
    client.post(f"/api/paths/{JACOBIAN}/steps/{steps[0]['id']}/confidence", json={"rating": 5})
    client.post(f"/api/paths/{JACOBIAN}/steps/{steps[1]['id']}/confidence", json={"rating": 2})
    jac2 = _item_for(client.get("/api/paths").json(), JACOBIAN)
    assert jac2["confidence"] == 3.5
