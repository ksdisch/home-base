"""M7 Phase 3 For You — the profile builder, ranker, and GET /api/news/foryou.

Pure-function tests drive the math with an injected clock (14-day signal half-life,
24-hour freshness half-life); endpoint tests go through the API with a fake fetcher that
never touches the network. House rules under test: cold start is honest (``learning`` +
Top stories, calm even when the feed is dead); clicked/dismissed items never come back;
net-negative items are gone ("Fewer like this" works); near-duplicate headlines collapse;
the profile is built from ``news_events`` only; ``/news/foryou`` isn't swallowed by the
``/news/{slug}`` route.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.foryou import (
    build_profile,
    extract_terms,
    rank_candidates,
    search_feed_url,
    top_search_terms,
)

NOW = datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc)


def _event(kind, slug="top", headline=None, item_id=None, days_ago=0.0):
    return {
        "kind": kind,
        "category_slug": slug,
        "headline": headline,
        "item_id": item_id,
        "created_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


def _item(headline, link, hours_ago=1.0):
    return {
        "id": hashlib.sha1(link.encode()).hexdigest()[:12],
        "headline": headline,
        "url": link,
        "source": "Wire",
        "published_at": (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds"),
    }


# -- terms -----------------------------------------------------------------------


def test_extract_terms_unigrams_bigrams_stopwords():
    terms = extract_terms("The Kansas City Chiefs sign a kicker")
    assert "kansas" in terms and "chiefs" in terms and "kicker" in terms
    assert "kansas city" in terms and "city chiefs" in terms  # bigrams survive
    assert "the" not in terms and "a" not in terms  # stopwords don't
    assert extract_terms(None) == set() and extract_terms("of the and") == set()


# -- profile ---------------------------------------------------------------------


def test_profile_weights_and_14_day_half_life():
    events = [
        _event("click", "technology", "Quantum computing rig ships", "i1", days_ago=0),
        _event("click", "technology", "Quantum computing rig ships", "i2", days_ago=14),
    ]
    p = build_profile(events, now=NOW)
    # +3 now, +1.5 after one half-life — for the category and each headline term.
    assert p["category_scores"]["technology"] == pytest.approx(4.5)
    assert p["term_scores"]["quantum computing"] == pytest.approx(4.5)
    assert p["event_count"] == 2
    assert p["seen_item_ids"] == {"i1", "i2"}


def test_profile_visit_feedback_and_negatives():
    events = [
        _event("visit", "sports"),  # +1, category only — no headline, no terms
        _event("more_like", "sports", "Chiefs camp battle", "a", days_ago=0),  # +5
        _event("not_interested", "sports", "Chiefs camp battle", "b", days_ago=0),  # -8
        _event("hover", "sports", "ignored kind", "c"),  # unknown kind: skipped
    ]
    p = build_profile(events, now=NOW)
    assert p["category_scores"]["sports"] == pytest.approx(1 + 5 - 8)
    assert p["term_scores"]["chiefs"] == pytest.approx(5 - 8)
    assert p["event_count"] == 2  # visit + more_like; not_interested isn't warmth
    assert p["seen_item_ids"] == {"b"}  # dismissed item never comes back; more_like does


def test_profile_survives_malformed_timestamp():
    p = build_profile([{**_event("click", "top", "Hello world", "x"), "created_at": "junk"}], now=NOW)
    assert p["category_scores"]["top"] == 0.0  # decayed to nothing, not a crash


# -- ranking ---------------------------------------------------------------------


def _profile(term_scores=None, category_scores=None, seen=None):
    return {
        "event_count": 99,
        "category_scores": category_scores or {},
        "term_scores": term_scores or {},
        "seen_item_ids": seen or set(),
    }


def test_term_match_outranks_fresher_unmatched():
    quantum = _item("Quantum computing breakthrough", "https://g/q", hours_ago=20)
    gossip = _item("Celebrity gala tonight", "https://g/c", hours_ago=1)
    ranked = rank_candidates(
        _profile(term_scores={"quantum": 10.0}), {"technology": [quantum, gossip]}, now=NOW
    )
    assert [i["headline"] for i in ranked] == [
        "Quantum computing breakthrough",
        "Celebrity gala tonight",  # zero-interest trails, kept for fill
    ]
    assert ranked[0]["category_slug"] == "technology"


def test_seen_and_negative_items_excluded():
    quantum = _item("Quantum computing breakthrough", "https://g/q")
    gossip = _item("Celebrity gala tonight", "https://g/c")
    ranked = rank_candidates(
        _profile(term_scores={"celebrity": -5.0}, seen={quantum["id"]}),
        {"technology": [quantum, gossip]},
        now=NOW,
    )
    assert ranked == []  # one already read, one pushed negative — both gone


def test_near_duplicate_headlines_collapse_keeping_higher_scored():
    a = _item("Chiefs sign veteran kicker after camp injury", "https://g/a", hours_ago=1)
    b = _item("Chiefs sign veteran kicker after injury at camp", "https://g/b", hours_ago=5)
    ranked = rank_candidates(
        _profile(term_scores={"chiefs": 10.0}), {"sports": [b, a]}, now=NOW
    )
    assert len(ranked) == 1
    assert ranked[0]["url"] == "https://g/a"  # fresher copy scored higher, kept


def test_same_item_syndicated_into_two_sections_appears_once():
    item = _item("Market rally continues", "https://g/m")
    ranked = rank_candidates(
        _profile(term_scores={"market": 5.0}), {"business": [item], "top": [dict(item)]}, now=NOW
    )
    assert len(ranked) == 1


def test_zero_interest_items_order_by_freshness():
    old = _item("Alpha story", "https://g/1", hours_ago=30)
    new = _item("Beta story", "https://g/2", hours_ago=2)
    ranked = rank_candidates(_profile(), {"top": [old, new]}, now=NOW)
    assert [i["headline"] for i in ranked] == ["Beta story", "Alpha story"]


# -- search terms ----------------------------------------------------------------


def test_top_search_terms_threshold_bigram_preference_and_cap():
    p = _profile(
        term_scores={
            "quantum computing": 12.0,
            "quantum": 12.0,
            "chiefs": 8.0,
            "kicker": 6.0,
            "gossip": 1.0,  # below the 5.0 floor
        }
    )
    terms = top_search_terms(p)
    assert len(terms) == 3
    assert terms[0] == "quantum computing"  # bigram beats its unigram twin on a tie
    assert "gossip" not in terms


def test_search_feed_url_is_quoted():
    assert "q=quantum%20computing" in search_feed_url("quantum computing")


# -- the endpoint ----------------------------------------------------------------

RSS_HEAD = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>'
RSS_TAIL = "</channel></rss>"
EMPTY_RSS = (RSS_HEAD + RSS_TAIL).encode()


def _rss_item(headline, link):
    return (
        f"<item><title>{headline} - Wire</title><link>{link}</link>"
        f"<pubDate>Sat, 18 Jul 2026 10:00:00 GMT</pubDate>"
        f'<source url="https://wire.example">Wire</source></item>'
    )


def _rss(*items):
    return (RSS_HEAD + "".join(items) + RSS_TAIL).encode()


TOP_FEED = "https://example.test/top"
TECH_FEED = "https://example.test/tech"
CATS = [
    {"slug": "top", "title": "Top stories", "feeds": [TOP_FEED]},
    {"slug": "technology", "title": "Technology", "feeds": [TECH_FEED]},
]


class DefaultingFetcher:
    """URL→bytes map with an empty-feed default (search-term URLs vary), or raise-all."""

    def __init__(self, responses=None, fail=False):
        self.responses = responses or {}
        self.fail = fail
        self.calls: list[str] = []

    def fetch(self, url: str) -> bytes:
        self.calls.append(url)
        if self.fail:
            from app.news import NewsFeedError

            raise NewsFeedError("feed down")
        return self.responses.get(url, EMPTY_RSS)


def _env(tmp_path, monkeypatch):
    import json

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


def test_cold_start_serves_top_stories_labeled_learning(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    f = DefaultingFetcher({TOP_FEED: _rss(_rss_item("Big story", "https://g/big"))})
    body = _client(f).get("/api/news/foryou").json()  # not shadowed by /news/{slug}
    assert body["learning"] is True and body["event_count"] == 0
    assert [i["headline"] for i in body["items"]] == ["Big story"]
    assert body["items"][0]["category_slug"] == "top"
    assert f.calls == [TOP_FEED]  # cold start fetches Top only — not the whole roster


def test_cold_start_with_dead_feed_stays_calm(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    body = _client(DefaultingFetcher(fail=True)).get("/api/news/foryou")
    assert body.status_code == 200
    assert body.json()["learning"] is True and body.json()["items"] == []


def test_warm_profile_ranks_matching_candidates_first_and_pulls_search_feeds(
    tmp_path, monkeypatch
):
    _env(tmp_path, monkeypatch)
    from app.store import record_news_event

    for n in range(20):  # warm the profile: 20 clicks on quantum-computing stories
        record_news_event(
            "click",
            "technology",
            item_id=f"clicked{n:02d}",
            headline="Quantum computing breakthrough at the lab",
        )

    f = DefaultingFetcher(
        {
            TOP_FEED: _rss(
                _rss_item("Celebrity gala tonight", "https://g/gala"),
                _rss_item("Quantum computing hits new milestone", "https://g/q2"),
            ),
            TECH_FEED: _rss(_rss_item("Some other tech story", "https://g/other")),
        }
    )
    body = _client(f).get("/api/news/foryou").json()
    assert body["learning"] is False and body["event_count"] == 20
    assert body["items"][0]["headline"] == "Quantum computing hits new milestone"
    headlines = [i["headline"] for i in body["items"]]
    assert "Celebrity gala tonight" in headlines  # zero-interest fill, ranked below
    # The strong profile terms pulled Google News search feeds into the candidate pool.
    assert any(u.startswith("https://news.google.com/rss/search?q=") for u in f.calls)
