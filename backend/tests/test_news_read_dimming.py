"""Read-dimming: play the already-logged click signal back into the feed.

News.tsx has fired ``signal("click", item)`` into ``news_events`` since M7 Phase 2, and the
For-You ranker eats those clicks — but Kyle's own eyes never got the replay. The headline
anchor is custom-styled, so the browser's native ``:visited`` never applies: a story he
opened at 06:45 comes back pixel-identical at lunch (docs/ideas/news-read-dimming.md).

Ids are ``sha1(link)[:12]``, stable across refetches, so a set-membership pass is the whole
mechanism. Zero new storage — the rows are already there.

One structural note the tests pin: the WARM For-You feed can never carry a clicked item,
because ``rank_candidates`` already drops everything in ``seen_item_ids`` — a stronger form
of the same idea. The COLD-START path serves Top stories unranked, so it can and does.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.foryou import CLICKED_LOOKBACK_HOURS, recently_clicked_ids

NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)


def _event(kind: str, item_id: str, hours_ago: float = 1.0) -> dict:
    return {
        "kind": kind,
        "category_slug": "top",
        "item_id": item_id,
        "headline": "A story",
        "created_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
    }


# -- the lookback ------------------------------------------------------------------


def test_a_recent_click_marks_its_item(tmp_path):
    assert recently_clicked_ids([_event("click", "abc", 2)], now=NOW) == {"abc"}


def test_an_old_click_stops_muting_the_story(tmp_path):
    """A 48h window, not forever: a genuinely re-newsworthy story must be able to come
    back undimmed rather than stay greyed out because it was read once last week."""
    events = [
        _event("click", "fresh", CLICKED_LOOKBACK_HOURS - 1),
        _event("click", "stale", CLICKED_LOOKBACK_HOURS + 1),
    ]
    assert recently_clicked_ids(events, now=NOW) == {"fresh"}


def test_only_clicks_count(tmp_path):
    """Dimming means "you opened this". A visit isn't reading, and not_interested has its
    own stronger treatment (the item is dropped, not greyed)."""
    events = [
        _event("click", "clicked"),
        _event("more_like", "liked"),
        _event("not_interested", "dismissed"),
        _event("visit", "visited"),
    ]
    assert recently_clicked_ids(events, now=NOW) == {"clicked"}


def test_junk_rows_are_skipped_never_fatal(tmp_path):
    events = [
        _event("click", "good"),
        {"kind": "click"},  # no item_id
        {"kind": "click", "item_id": "nodate"},  # no timestamp
        {"kind": "click", "item_id": "bad", "created_at": "not-a-timestamp"},
        _event("click", "also-good"),
    ]
    assert recently_clicked_ids(events, now=NOW) == {"good", "also-good"}


def test_no_events_is_an_empty_set(tmp_path):
    assert recently_clicked_ids([], now=NOW) == set()


# -- through the API ---------------------------------------------------------------

RSS_HEAD = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>'
RSS_TAIL = "</channel></rss>"
TOP_FEED = "https://example.test/top"


def _rss_item(headline: str, link: str) -> str:
    return (
        f"<item><title>{headline} - Wire</title><link>{link}</link>"
        "<pubDate>Sat, 25 Jul 2026 12:00:00 GMT</pubDate>"
        '<source url="https://wire.test">Wire</source></item>'
    )


def _rss(*items: str) -> bytes:
    return (RSS_HEAD + "".join(items) + RSS_TAIL).encode("utf-8")


def _id(link: str) -> str:
    return hashlib.sha1(link.encode()).hexdigest()[:12]


CATS = [{"slug": "top", "title": "Top stories", "feeds": [TOP_FEED]}]

READ_LINK = "https://g/already-read"
NEW_LINK = "https://g/brand-new"


class Fetcher:
    def __init__(self, body):
        self.body = body

    def fetch(self, url: str) -> bytes:
        return self.body


def _env(tmp_path, monkeypatch):
    cfg = tmp_path / "news_categories.json"
    cfg.write_text(json.dumps(CATS), encoding="utf-8")
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


FEED = _rss(_rss_item("Already read", READ_LINK), _rss_item("Brand new", NEW_LINK))


def test_a_category_feed_marks_the_story_you_opened(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    from app.store import record_news_event

    record_news_event("click", "top", item_id=_id(READ_LINK), headline="Already read")

    items = _client(Fetcher(FEED)).get("/api/news/top").json()["items"]

    by_headline = {i["headline"]: i for i in items}
    assert by_headline["Already read"]["clicked"] is True
    assert by_headline["Brand new"]["clicked"] is False


def test_an_untouched_feed_marks_nothing(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    items = _client(Fetcher(FEED)).get("/api/news/top").json()["items"]
    assert not any(i["clicked"] for i in items)


def test_cold_start_foryou_dims_what_was_already_opened(tmp_path, monkeypatch):
    """Cold start serves Top stories UNRANKED, so it's the one For-You path that can carry
    a clicked item — and the 6:45am/lunch repeat visit is exactly when it matters."""
    _env(tmp_path, monkeypatch)
    from app.store import record_news_event

    record_news_event("click", "top", item_id=_id(READ_LINK), headline="Already read")

    body = _client(Fetcher(FEED)).get("/api/news/foryou").json()

    assert body["learning"] is True  # still cold: one click is far short of the threshold
    by_headline = {i["headline"]: i for i in body["items"]}
    assert by_headline["Already read"]["clicked"] is True
    assert by_headline["Brand new"]["clicked"] is False


def test_a_warm_foryou_feed_structurally_has_none(tmp_path, monkeypatch):
    """rank_candidates already drops seen_item_ids, which is a stronger form of dimming.
    This pins that: if a future ranker change lets clicked items back in, they arrive
    already marked rather than silently undimmed."""
    _env(tmp_path, monkeypatch)
    from app.store import record_news_event

    for n in range(20):  # warm the profile past COLD_START_EVENTS
        record_news_event("click", "top", item_id=f"warm{n:02d}", headline="Quantum computing")
    record_news_event("click", "top", item_id=_id(READ_LINK), headline="Already read")

    body = _client(Fetcher(FEED)).get("/api/news/foryou").json()

    assert body["learning"] is False
    assert "Already read" not in [i["headline"] for i in body["items"]]  # excluded outright
    assert all(i["clicked"] is False for i in body["items"])
