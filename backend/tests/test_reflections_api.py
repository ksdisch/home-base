"""Phase-6 /api/reflections — the reflection journal read path over the store."""

from __future__ import annotations

from .test_review_api import _client, _fresh_store


def test_reflections_empty_store_degrades_gracefully(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "refl-empty")
    from app.config import get_settings

    try:
        client = _client()
        try:
            body = client.get("/api/reflections").json()
            assert body["has_data"] is False
            assert body["count"] == 0
            assert body["avg_grasp"] is None
            assert body["items"] == []
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


def test_reflections_surface_newest_first_with_avg_grasp(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "refl-data")
    from app.config import get_settings
    from app.store import save_reflection

    try:
        save_reflection("nb-1", "First pass felt shaky", grasp_rating=2)
        save_reflection("nb-1", "Clicked the second time", grasp_rating=4)
        save_reflection("nb-2", "No rating here")

        client = _client()
        try:
            body = client.get("/api/reflections").json()
            assert body["has_data"] is True
            assert body["count"] == 3
            assert body["avg_grasp"] == 3.0  # (2 + 4) / 2, ignoring the unrated one
            # Newest first.
            assert body["items"][0]["body"] == "No rating here"
            assert body["items"][0]["title"] == "nb-2"  # unknown notebook → id fallback

            # Filter to one notebook.
            one = client.get("/api/reflections?notebook_id=nb-1").json()
            assert one["count"] == 2
            assert {i["notebook_id"] for i in one["items"]} == {"nb-1"}
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()
