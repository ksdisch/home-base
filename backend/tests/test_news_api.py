"""M7 Phase 1 /api/news — the Google-News-style mode's read path.

Synthetic category config + fixture RSS through a fake fetcher only (never the real
sweeps/news_categories.json, never the network). House rules under test: unknown slug
404s; a dead feed with no cache is an honest 502, with an expired cache it serves
``stale``; a malformed item is skipped, never sinks its feed; a broken config file
degrades to no categories, never a 500; the TTL cache means one fetch per window.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

RSS_HEAD = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>'
RSS_TAIL = "</channel></rss>"


def _item(
    headline: str,
    link: str = "https://news.google.com/rss/articles/abc?oc=5",
    source: str | None = "AP News",
    pub: str | None = "Fri, 17 Jul 2026 12:00:00 GMT",
    with_link: bool = True,
) -> str:
    title = f"{headline} - {source}" if source else headline
    parts = [f"<item><title>{title}</title>"]
    if with_link:
        parts.append(f"<link>{link}</link>")
    if pub:
        parts.append(f"<pubDate>{pub}</pubDate>")
    if source:
        parts.append(f'<source url="https://apnews.com">{source}</source>')
    parts.append("</item>")
    return "".join(parts)


def _rss(*items: str) -> bytes:
    return (RSS_HEAD + "".join(items) + RSS_TAIL).encode("utf-8")


class FakeFetcher:
    """Maps feed URL -> bytes (or an exception instance to raise). Records every call."""

    def __init__(self, responses):
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, url: str) -> bytes:
        self.calls.append(url)
        resp = self.responses[url]
        if isinstance(resp, Exception):
            raise resp
        return resp


ONE_FEED = "https://example.test/feed-a"
TWO_FEED = "https://example.test/feed-b"

CATS = [
    {"slug": "top", "title": "Top stories", "feeds": [ONE_FEED]},
    {"slug": "local", "title": "Local", "feeds": [ONE_FEED, TWO_FEED]},
]


def _env(tmp_path, monkeypatch, cats=CATS):
    cfg = tmp_path / "news_categories.json"
    cfg.write_text(json.dumps(cats) if not isinstance(cats, str) else cats, encoding="utf-8")
    monkeypatch.setenv("NEWS_CATEGORIES_FILE", str(cfg))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()


def _client(fetcher: FakeFetcher):
    from fastapi.testclient import TestClient

    from app.deps import get_news_fetcher
    from app.main import app

    app.dependency_overrides[get_news_fetcher] = lambda: fetcher
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    from app.config import get_settings
    from app.main import app

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _expire_cache(slug: str) -> None:
    """Backdate a cached payload past the TTL, straight in the store."""
    from app.config import get_settings

    conn = sqlite3.connect(str(get_settings().db_path))
    try:
        conn.execute(
            "UPDATE news_feed_cache SET fetched_at = '2020-01-01T00:00:00+00:00' "
            "WHERE category_slug = ?",
            (slug,),
        )
        conn.commit()
    finally:
        conn.close()


# -- categories roster -----------------------------------------------------------


def test_categories_in_config_order(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    body = _client(FakeFetcher({})).get("/api/news/categories").json()
    assert [c["slug"] for c in body["categories"]] == ["top", "local"]
    assert body["categories"][0]["title"] == "Top stories"


def test_broken_config_degrades_to_no_categories(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, cats="{not json")
    body = _client(FakeFetcher({})).get("/api/news/categories").json()
    assert body["categories"] == []


def test_bad_entries_skipped_not_fatal(tmp_path, monkeypatch):
    cats = [
        {"slug": "top", "title": "Top stories", "feeds": [ONE_FEED]},
        {"slug": "", "title": "No slug", "feeds": [ONE_FEED]},
        {"slug": "nofeeds", "title": "No feeds", "feeds": []},
        "not-a-dict",
    ]
    _env(tmp_path, monkeypatch, cats=cats)
    body = _client(FakeFetcher({})).get("/api/news/categories").json()
    assert [c["slug"] for c in body["categories"]] == ["top"]


# -- one category's items --------------------------------------------------------


def test_unknown_slug_404(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert _client(FakeFetcher({})).get("/api/news/nope").status_code == 404


def test_items_parsed_cleaned_and_sorted(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    older = _item(
        "Old story", link="https://g/1", pub="Thu, 16 Jul 2026 08:00:00 GMT", source="BBC"
    )
    newer = _item("New story", link="https://g/2", pub="Fri, 17 Jul 2026 09:30:00 GMT")
    f = FakeFetcher({ONE_FEED: _rss(older, newer)})
    body = _client(f).get("/api/news/top").json()

    assert body["slug"] == "top" and body["stale"] is False
    assert [i["headline"] for i in body["items"]] == ["New story", "Old story"]  # newest first
    first = body["items"][0]
    assert first["source"] == "AP News"  # " - Source" suffix stripped into the source field
    assert first["published_at"] == "2026-07-17T09:30:00+00:00"
    assert first["url"] == "https://g/2"
    assert first["id"] == hashlib.sha1(b"https://g/2").hexdigest()[:12]


def test_outlet_feed_items_fall_back_to_channel_title_for_source(tmp_path, monkeypatch):
    """Plain outlet feeds (the Uplifting category's good-news sites) carry no per-item
    <source>; attribution falls back to the channel title. Google-style items with their
    own <source> are untouched — and an outlet headline is never suffix-stripped."""
    _env(tmp_path, monkeypatch)
    outlet_rss = (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<title>Good News Network</title>"
        "<item><title>Daughter Saves Dad's Shoe Shop - With TikTok</title>"
        "<link>https://gnn.example/shop</link>"
        "<pubDate>Sat, 18 Jul 2026 09:00:00 GMT</pubDate></item>"
        + _item("Google style story", link="https://g/gs")
        + "</channel></rss>"
    ).encode("utf-8")
    body = _client(FakeFetcher({ONE_FEED: outlet_rss})).get("/api/news/top").json()
    by_url = {i["url"]: i for i in body["items"]}
    outlet = by_url["https://gnn.example/shop"]
    assert outlet["source"] == "Good News Network"
    assert outlet["headline"] == "Daughter Saves Dad's Shoe Shop - With TikTok"  # no stripping
    assert by_url["https://g/gs"]["source"] == "AP News"  # per-item <source> still wins


def test_item_without_link_skipped(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    good = _item("Kept", link="https://g/keep")
    bad = _item("Dropped", with_link=False)
    body = _client(FakeFetcher({ONE_FEED: _rss(good, bad)})).get("/api/news/top").json()
    assert [i["headline"] for i in body["items"]] == ["Kept"]


def test_undated_items_served_last(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    dated = _item("Dated", link="https://g/d")
    undated = _item("Undated", link="https://g/u", pub=None)
    body = _client(FakeFetcher({ONE_FEED: _rss(undated, dated)})).get("/api/news/top").json()
    assert [i["headline"] for i in body["items"]] == ["Dated", "Undated"]
    assert body["items"][1]["published_at"] is None


def test_multi_feed_merge_dedupes_by_link(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    shared = _item("Same story", link="https://g/same")
    only_b = _item("Only in B", link="https://g/b", pub="Fri, 17 Jul 2026 01:00:00 GMT")
    f = FakeFetcher({ONE_FEED: _rss(shared), TWO_FEED: _rss(shared, only_b)})
    body = _client(f).get("/api/news/local").json()
    assert sorted(i["headline"] for i in body["items"]) == ["Only in B", "Same story"]
    assert f.calls == [ONE_FEED, TWO_FEED]


# -- cache + failure semantics ---------------------------------------------------


def test_second_request_within_ttl_hits_cache(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    f = FakeFetcher({ONE_FEED: _rss(_item("A", link="https://g/a"))})
    client = _client(f)
    first = client.get("/api/news/top").json()
    second = client.get("/api/news/top").json()
    assert f.calls == [ONE_FEED]  # one fetch, second served from the store
    assert second["items"] == first["items"]
    assert second["fetched_at"] == first["fetched_at"]


def test_expired_cache_refetches(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    f = FakeFetcher({ONE_FEED: _rss(_item("A", link="https://g/a"))})
    client = _client(f)
    client.get("/api/news/top")
    _expire_cache("top")
    body = client.get("/api/news/top").json()
    assert f.calls == [ONE_FEED, ONE_FEED]
    assert body["stale"] is False


def test_failed_refresh_serves_expired_cache_as_stale(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    ok = FakeFetcher({ONE_FEED: _rss(_item("Cached story", link="https://g/a"))})
    client = _client(ok)
    client.get("/api/news/top")
    _expire_cache("top")

    from app.news import NewsFeedError

    dead = FakeFetcher({ONE_FEED: NewsFeedError("feed down")})
    body = _client(dead).get("/api/news/top").json()
    assert body["stale"] is True
    assert [i["headline"] for i in body["items"]] == ["Cached story"]


def test_failure_with_no_cache_is_502(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    from app.news import NewsFeedError

    dead = FakeFetcher({ONE_FEED: NewsFeedError("feed down")})
    res = _client(dead).get("/api/news/top")
    assert res.status_code == 502
    assert "unavailable" in res.json()["detail"]


def test_unparseable_xml_with_no_cache_is_502(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    res = _client(FakeFetcher({ONE_FEED: b"<html>not rss"})).get("/api/news/top")
    assert res.status_code == 502
