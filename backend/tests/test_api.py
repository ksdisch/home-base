"""API smoke + the end-to-end auth-failure path (mocked nlm), via TestClient."""

from __future__ import annotations

import pytest


def _make_client(crafted_root, *, nlm_runner=None):
    # Lazy imports so the session autouse env fixture has set LEARNING_HUB_DATA first.
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.deps import get_app_settings, get_nlm_client
    from app.main import app
    from app.nlm import NlmClient

    settings = Settings()
    settings.notebooklm_root = crafted_root
    settings.ensure_dirs()

    app.dependency_overrides[get_app_settings] = lambda: settings
    if nlm_runner is not None:
        app.dependency_overrides[get_nlm_client] = lambda: NlmClient(runner=nlm_runner)
    client = TestClient(app)
    client._settings = settings  # type: ignore[attr-defined]
    return client


def _first_topic_id(client) -> str:
    cat = client.get("/api/catalog").json()
    for g in cat["groups"]:
        if g["notebooks"]:
            return g["notebooks"][0]["notebook_id"]
    raise AssertionError("no notebooks in catalog")


def test_catalog_groups_and_links(crafted_root):
    client = _make_client(crafted_root)
    try:
        r = client.get("/api/catalog")
        assert r.status_code == 200
        data = r.json()
        keys = [g["key"] for g in data["groups"]]
        assert keys == ["learning", "interview-prep", "custom"]
        cards = [c for g in data["groups"] for c in g["notebooks"]]
        assert cards, "expected real notebooks"
        for c in cards:
            assert c["notebooklm_url"].startswith("https://notebooklm.google.com/notebook/")
            assert c["topic_url"] == f"/topics/{c['notebook_id']}"
    finally:
        client.app.dependency_overrides.clear()


def test_topic_detail_and_404(crafted_root):
    client = _make_client(crafted_root)
    try:
        nid = _first_topic_id(client)
        r = client.get(f"/api/topics/{nid}")
        assert r.status_code == 200
        body = r.json()
        assert body["auth"]["ok"] is True
        assert "episodes" in body and "quizzes" in body
        assert client.get("/api/topics/nope-nope").status_code == 404
    finally:
        client.app.dependency_overrides.clear()


def test_live_refresh_auth_failure_is_friendly_not_500(crafted_root):
    from app.nlm import NlmResult

    def failing(args):
        return NlmResult(args=list(args), stdout="", stderr="Error: not logged in", returncode=1)

    client = _make_client(crafted_root, nlm_runner=failing)
    try:
        nid = _first_topic_id(client)
        r = client.get(f"/api/topics/{nid}?live=true")
        assert r.status_code == 200  # degraded, not a crash
        body = r.json()
        assert body["auth"]["ok"] is False
        assert "nlm login" in (body["auth"]["message"] or "").lower()
        # still rendered sidecar artifacts despite the live failure
        assert body["counts"]["total"] >= 1
    finally:
        client.app.dependency_overrides.clear()


def test_live_refresh_surfaces_nlm_only_artifacts(crafted_root):
    from app.nlm import NlmResult

    new_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"

    def studio(args):
        payload = f'[{{"id":"{new_id}","type":"flashcards","status":"completed"}}]'
        return NlmResult(args=list(args), stdout=payload, stderr="", returncode=0)

    client = _make_client(crafted_root, nlm_runner=studio)
    try:
        nid = _first_topic_id(client)
        body = client.get(f"/api/topics/{nid}?live=true").json()
        assert body["live"] is True
        ids = {a["artifact_id"] for a in body["other_artifacts"]}
        assert new_id in ids  # nlm-only artifact surfaced
        assert any("found live but not in the sidecar" in w for w in body["warnings"])
    finally:
        client.app.dependency_overrides.clear()


def test_episode_listened_toggle_persists(crafted_root):
    client = _make_client(crafted_root)
    try:
        nid = _first_topic_id(client)
        detail = client.get(f"/api/topics/{nid}").json()
        # pick any audio episode/standalone
        eps = detail["episodes"] + detail["standalones"]
        if not eps:
            pytest.skip("no audio episode in first topic")
        aid = eps[0]["artifact_id"]
        assert client.post(f"/api/topics/{nid}/episodes/{aid}/listened", json={"listened": True}).json()["listened"] is True
        again = client.get(f"/api/topics/{nid}").json()
        match = [e for e in again["episodes"] + again["standalones"] if e["artifact_id"] == aid]
        assert match and match[0]["listened"] is True
    finally:
        client.app.dependency_overrides.clear()
