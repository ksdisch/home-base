"""M6 one-port serving: the app serves frontend/dist when present, and only then.

/api always wins over the SPA catch-all; absent a dist, behavior is exactly the dev
setup (root 404s, healthy API).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>home base shell</html>", encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("console.log('hb')", encoding="utf-8")
    (dist / "sw.js").write_text("// sw v2", encoding="utf-8")
    (dist / "manifest.webmanifest").write_text('{"name": "Home Base"}', encoding="utf-8")
    (dist / "icon.svg").write_text("<svg/>", encoding="utf-8")
    return dist


def _make_client(monkeypatch, dist: Path | None):
    # Lazy imports so the session autouse env fixture has set LEARNING_HUB_DATA first.
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv(
        "FRONTEND_DIST", str(dist) if dist is not None else "/nonexistent/dist"
    )
    get_settings.cache_clear()
    client = TestClient(create_app())
    return client


@pytest.fixture(autouse=True)
def _restore_settings():
    yield
    from app.config import get_settings

    get_settings.cache_clear()


def test_root_serves_index_html(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, _write_dist(tmp_path))
    r = client.get("/")
    assert r.status_code == 200
    assert "home base shell" in r.text


def test_assets_are_served(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, _write_dist(tmp_path))
    r = client.get("/assets/app-abc123.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_root_pwa_files_are_served(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, _write_dist(tmp_path))
    for path, marker in [
        ("/sw.js", "sw v2"),
        ("/manifest.webmanifest", "Home Base"),
        ("/icon.svg", "<svg"),
    ]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert marker in r.text


def test_unknown_spa_path_falls_back_to_index(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, _write_dist(tmp_path))
    r = client.get("/notes")
    assert r.status_code == 200
    assert "home base shell" in r.text


def test_api_wins_over_catch_all(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, _write_dist(tmp_path))
    r = client.get("/api")
    assert r.status_code == 200
    assert r.json()["name"] == "Learning Hub API"
    assert client.get("/api/health").status_code == 200


def test_unknown_api_path_is_json_404_not_shell(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, _write_dist(tmp_path))
    r = client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert "home base shell" not in r.text


def test_traversal_outside_dist_gets_shell_not_file(tmp_path, monkeypatch):
    dist = _write_dist(tmp_path)
    (tmp_path / "secret.txt").write_text("keychain", encoding="utf-8")
    client = _make_client(monkeypatch, dist)
    # Encoded dots survive URL normalization; the resolve() containment check must hold.
    r = client.get("/%2e%2e/secret.txt")
    assert r.status_code == 200
    assert "keychain" not in r.text
    assert "home base shell" in r.text


def test_absent_dist_keeps_dev_behavior(monkeypatch):
    client = _make_client(monkeypatch, None)
    assert client.get("/").status_code == 404
    assert client.get("/notes").status_code == 404
    r = client.get("/api/health")
    assert r.status_code == 200
