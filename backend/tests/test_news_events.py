"""M7 Phase 2 POST /api/news/events — the For-You signal log.

House rules under test: every valid kind lands as a row with its snapshot columns intact
(the feed cache rolls over, so item events must be self-contained — same reasoning as
brief_notes); invalid events 400 and write nothing (a polluted log would quietly skew the
Phase 3 profile); the log is Mode-B-only by construction and newest-first on read.
"""

from __future__ import annotations

import pytest


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    yield
    get_settings.cache_clear()


CLICK = {
    "kind": "click",
    "category_slug": "technology",
    "item_id": "abc123abc123",
    "headline": "Apple raises Apple One prices",
    "source": "Deadline",
    "url": "https://news.example/apple",
}


def test_click_event_recorded_with_snapshot():
    res = _client().post("/api/news/events", json=CLICK)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["id"] >= 1 and body["created_at"]

    from app.store import list_news_events

    rows = list_news_events()
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "click"
    assert row["category_slug"] == "technology"
    assert row["item_id"] == "abc123abc123"
    assert row["headline"] == "Apple raises Apple One prices"  # snapshot survives the cache
    assert row["source"] == "Deadline"
    assert row["url"] == "https://news.example/apple"


def test_visit_event_needs_only_category():
    res = _client().post(
        "/api/news/events", json={"kind": "visit", "category_slug": "sports"}
    )
    assert res.status_code == 200

    from app.store import list_news_events

    row = list_news_events()[0]
    assert row["kind"] == "visit" and row["category_slug"] == "sports"
    assert row["item_id"] is None and row["headline"] is None


@pytest.mark.parametrize("kind", ["more_like", "not_interested"])
def test_feedback_kinds_recorded(kind):
    res = _client().post("/api/news/events", json={**CLICK, "kind": kind})
    assert res.status_code == 200

    from app.store import list_news_events

    assert list_news_events()[0]["kind"] == kind


def test_unknown_kind_400_writes_nothing():
    res = _client().post("/api/news/events", json={**CLICK, "kind": "hover"})
    assert res.status_code == 400
    assert "kind" in res.json()["detail"]

    from app.store import list_news_events

    assert list_news_events() == []


@pytest.mark.parametrize("missing", ["item_id", "headline"])
def test_item_event_without_snapshot_400_writes_nothing(missing):
    payload = {**CLICK, missing: None}
    res = _client().post("/api/news/events", json=payload)
    assert res.status_code == 400
    assert missing in res.json()["detail"] or "headline" in res.json()["detail"]

    from app.store import list_news_events

    assert list_news_events() == []


def test_blank_category_400():
    res = _client().post("/api/news/events", json={"kind": "visit", "category_slug": "  "})
    assert res.status_code == 400


def test_events_read_newest_first():
    client = _client()
    client.post("/api/news/events", json={"kind": "visit", "category_slug": "first"})
    client.post("/api/news/events", json={"kind": "visit", "category_slug": "second"})

    from app.store import list_news_events

    slugs = [r["category_slug"] for r in list_news_events()]
    assert slugs == ["second", "first"]  # id breaks the same-second created_at tie
