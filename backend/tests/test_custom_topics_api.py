"""Phase-5 custom-topics HTTP surface — the GET/POST/PATCH round-trip over the existing store.

Each test isolates a fresh DB (like the progress/review API tests) so ordering + counts are
deterministic. The store already owns validation; here we assert it surfaces as 400/404 and that
the create/list/patch contract holds end-to-end through FastAPI.
"""

from __future__ import annotations

import pytest


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _fresh_store(tmp_path, monkeypatch, name: str):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()


@pytest.fixture
def client(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "custom-hub")
    from app.config import get_settings

    c = _client()
    try:
        yield c
    finally:
        get_settings.cache_clear()


# -- read ----------------------------------------------------------------------

def test_get_empty_store_returns_empty_list(client):
    r = client.get("/api/custom-topics")
    assert r.status_code == 200
    body = r.json()
    assert body["topics"] == []
    assert body["generated_at"]


# -- create --------------------------------------------------------------------

def test_post_creates_and_then_appears_in_list(client):
    r = client.post(
        "/api/custom-topics",
        json={"title": "Designing Data-Intensive Apps", "notes": "ch.1", "progress_pct": 10},
    )
    assert r.status_code == 201
    topic = r.json()
    assert topic["id"] >= 1
    assert topic["title"] == "Designing Data-Intensive Apps"
    assert topic["notes"] == "ch.1"
    assert topic["progress_pct"] == 10

    listed = client.get("/api/custom-topics").json()["topics"]
    assert [t["id"] for t in listed] == [topic["id"]]


def test_post_orders_most_recently_updated_first(client):
    a = client.post("/api/custom-topics", json={"title": "first"}).json()
    b = client.post("/api/custom-topics", json={"title": "second"}).json()
    ids = [t["id"] for t in client.get("/api/custom-topics").json()["topics"]]
    # Most-recent first; id DESC is the deterministic within-second tie-break.
    assert ids == sorted([a["id"], b["id"]], reverse=True)


def test_post_defaults_notes_empty_progress_zero(client):
    topic = client.post("/api/custom-topics", json={"title": "Bare"}).json()
    assert topic["notes"] == ""
    assert topic["progress_pct"] == 0


@pytest.mark.parametrize("payload", [{"title": ""}, {"title": "   "}])
def test_post_blank_title_is_400(client, payload):
    assert client.post("/api/custom-topics", json=payload).status_code == 400


@pytest.mark.parametrize("bad", [-1, 101, 200])
def test_post_out_of_range_progress_is_400(client, bad):
    r = client.post("/api/custom-topics", json={"title": "x", "progress_pct": bad})
    assert r.status_code == 400


# -- update --------------------------------------------------------------------

def test_patch_updates_only_given_fields(client):
    topic = client.post(
        "/api/custom-topics", json={"title": "Stoicism", "notes": "ep1", "progress_pct": 10}
    ).json()
    r = client.patch(f"/api/custom-topics/{topic['id']}", json={"progress_pct": 40})
    assert r.status_code == 200
    out = r.json()
    assert out["progress_pct"] == 40
    assert out["notes"] == "ep1"  # untouched
    assert out["title"] == "Stoicism"  # untouched
    assert out["created_at"] == topic["created_at"]  # stable


def test_patch_can_replace_notes(client):
    topic = client.post("/api/custom-topics", json={"title": "x", "notes": "old"}).json()
    out = client.patch(f"/api/custom-topics/{topic['id']}", json={"notes": "new"}).json()
    assert out["notes"] == "new"


def test_patch_unknown_id_is_404(client):
    assert client.patch("/api/custom-topics/99999", json={"progress_pct": 5}).status_code == 404


def test_patch_out_of_range_progress_is_400(client):
    topic = client.post("/api/custom-topics", json={"title": "x"}).json()
    r = client.patch(f"/api/custom-topics/{topic['id']}", json={"progress_pct": 101})
    assert r.status_code == 400


# -- activity signal (streaks) -------------------------------------------------

def test_create_and_update_log_activity_rows(client):
    from app.store import connect

    def count(kind: str) -> int:
        conn = connect()
        try:
            return conn.execute(
                "SELECT COUNT(*) c FROM activity WHERE kind = ?", (kind,)
            ).fetchone()["c"]
        finally:
            conn.close()

    topic = client.post("/api/custom-topics", json={"title": "x"}).json()
    assert count("custom_topic_added") == 1
    client.patch(f"/api/custom-topics/{topic['id']}", json={"progress_pct": 30})
    assert count("custom_topic_updated") == 1
