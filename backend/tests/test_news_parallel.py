"""The News fan-out is concurrent, not serial (docs/ideas/parallel-foryou-fanout.md).

Every morning at 06:15 the 15-minute TTL guarantees a cold cache, so the first News tap
of the day pays for *every* feed — 11 categories plus up to 3 search feeds, each a
10s-timeout fetch. Serial, that's the sum (a 10-40s spinner); concurrent, it's the
slowest single feed. These tests use a deliberately slow fake fetcher that never touches
the network and prove both properties directly: feeds overlap in time (a peak-concurrency
counter, not a stopwatch guess), and wall time lands well under the serial sum.

The house rules the parallel path must not break live in the neighbouring files —
per-feed failures stay non-fatal (test_news_api), the ranker's input stays deterministic
(test_news_foryou). Here we only assert the concurrency itself.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

RSS_HEAD = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>'
RSS_TAIL = "</channel></rss>"

# Long enough that a serial run is unmistakable, short enough to keep the suite quick.
DELAY = 0.25


def _rss(*items: str) -> bytes:
    return (RSS_HEAD + "".join(items) + RSS_TAIL).encode("utf-8")


def _rss_item(headline: str, link: str) -> str:
    return (
        f"<item><title>{headline} - Wire</title><link>{link}</link>"
        "<pubDate>Fri, 17 Jul 2026 12:00:00 GMT</pubDate>"
        '<source url="https://wire.test">Wire</source></item>'
    )


class SlowFetcher:
    """Sleeps ``DELAY`` per fetch and records how many fetches were ever in flight at once.

    ``peak == 1`` is the serial signature; anything above proves the loop fanned out.
    Unknown URLs (the search feeds For You derives from the profile) return an empty feed.
    """

    def __init__(self, responses=None, delay: float = DELAY):
        self.responses = responses or {}
        self.delay = delay
        self.calls: list[str] = []
        self.peak = 0
        self._live = 0
        self._lock = threading.Lock()

    def fetch(self, url: str) -> bytes:
        with self._lock:
            self.calls.append(url)
            self._live += 1
            self.peak = max(self.peak, self._live)
        try:
            time.sleep(self.delay)
        finally:
            with self._lock:
                self._live -= 1
        return self.responses.get(url, _rss())


def _feed(slug: str) -> str:
    return f"https://example.test/{slug}"


# Six single-feed categories: one full wave of the max_workers=6 pool.
CATS = [
    {"slug": "top", "title": "Top stories", "feeds": [_feed("top")]},
    {"slug": "us", "title": "U.S.", "feeds": [_feed("us")]},
    {"slug": "world", "title": "World", "feeds": [_feed("world")]},
    {"slug": "business", "title": "Business", "feeds": [_feed("business")]},
    {"slug": "technology", "title": "Technology", "feeds": [_feed("technology")]},
    {"slug": "science", "title": "Science", "feeds": [_feed("science")]},
]

# The real roster's worst multi-feed category (Uplifting) has four.
FOUR_FEED_CATS = [
    {
        "slug": "uplifting",
        "title": "Uplifting",
        "feeds": [_feed("up-a"), _feed("up-b"), _feed("up-c"), _feed("up-d")],
    }
]


def _env(tmp_path, monkeypatch, cats=CATS):
    cfg = tmp_path / "news_categories.json"
    cfg.write_text(json.dumps(cats), encoding="utf-8")
    monkeypatch.setenv("NEWS_CATEGORIES_FILE", str(cfg))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()


def _client(fetcher):
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


def _warm_the_profile():
    """20 clicks on one theme — past COLD_START_EVENTS, so For You fans out the full
    roster instead of fetching Top alone."""
    from app.store import record_news_event

    for n in range(20):
        record_news_event(
            "click",
            "technology",
            item_id=f"clicked{n:02d}",
            headline="Quantum computing breakthrough at the lab",
        )


def test_foryou_fans_out_concurrently_not_serially(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    _warm_the_profile()
    f = SlowFetcher({_feed("top"): _rss(_rss_item("Big story", "https://g/big"))})

    started = time.monotonic()
    body = _client(f).get("/api/news/foryou").json()
    elapsed = time.monotonic() - started

    assert body["learning"] is False
    assert len(f.calls) >= len(CATS)  # every category, plus any profile search feeds
    assert f.peak > 1, "feeds were fetched one at a time — the fan-out is still serial"
    # The point of the change: wall time tracks the slowest feed, not the sum of them.
    assert elapsed < len(f.calls) * DELAY * 0.6


def test_multi_feed_category_fetches_its_feeds_concurrently(tmp_path, monkeypatch):
    """The per-category route (a News tab tap) pays the same sum on a multi-feed
    category — and on the For You path a serial four-feed Uplifting would become the
    critical path, so the inner loop has to fan out too."""
    _env(tmp_path, monkeypatch, cats=FOUR_FEED_CATS)
    f = SlowFetcher()

    started = time.monotonic()
    resp = _client(f).get("/api/news/uplifting")
    elapsed = time.monotonic() - started

    assert resp.status_code == 200
    assert sorted(f.calls) == sorted(FOUR_FEED_CATS[0]["feeds"])
    assert f.peak > 1, "a multi-feed category still fetches its feeds one at a time"
    assert elapsed < len(FOUR_FEED_CATS[0]["feeds"]) * DELAY * 0.6
