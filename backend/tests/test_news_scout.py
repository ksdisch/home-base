"""M7 Phase 4 topic scout — suggest_topics + the add/dismiss endpoints.

House rules under test: a suggestion needs real persistence (score ≥ 9 across ≥ 3 distinct
days); anything the Mode-A roster already covers (token overlap, conservative on purpose)
never gets suggested; dismissals stick case-insensitively; "Fewer like this" drags a theme
out of contention; bigrams absorb their own unigrams; the one-click add appends to
sweeps/topics.json preserving existing entries verbatim (409 on a duplicate slug, never a
silent overwrite) — after which coverage silences the suggestion naturally.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.foryou import suggest_topics

NOW = datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc)


def _event(kind, headline, days_ago=0.0, slug="technology", item_id="x"):
    return {
        "kind": kind,
        "category_slug": slug,
        "headline": headline,
        "item_id": item_id,
        "created_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


# Varied headlines sharing one theme bigram — how a real reading streak looks. 4 clicks
# over 3 distinct days: "quantum computing" scores 3·(1 + 1 + 0.95 + 0.91) ≈ 11.6 ≥ 9
# while every incidental bigram appears once (≈3) and stays under the floor.
QUANTUM = "Quantum computing breakthrough at the lab"
QUANTUM_HEADLINES = [
    QUANTUM,
    "IBM quantum computing chip ships early",
    "Quantum computing error rates fall again",
    "Record set in quantum computing race",
]
QUANTUM_EVENTS = [
    _event("click", h, days_ago=d)
    for h, d in zip(QUANTUM_HEADLINES, (0, 0.2, 1, 2))
]

ROSTER = [{"slug": "ai-llms", "title": "AI / LLMs", "paused": False}]


# -- the pure scout --------------------------------------------------------------


def test_persistent_uncovered_theme_is_suggested_once_with_evidence():
    out = suggest_topics(QUANTUM_EVENTS, ROSTER, [], now=NOW)
    assert [s["term"] for s in out] == ["quantum computing"]  # one theme, one card
    assert out[0]["days_seen"] == 3
    assert out[0]["example_headlines"] == QUANTUM_HEADLINES[:2]  # ≤2 recent examples


def test_roster_coverage_silences_a_theme():
    roster = ROSTER + [{"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False}]
    events = [
        _event("click", "Chiefs kicker battle heats up", days_ago=d) for d in (0, 0.2, 1, 2)
    ]
    assert suggest_topics(events, roster, [], now=NOW) == []


def test_dismissal_sticks_case_insensitively():
    out = suggest_topics(QUANTUM_EVENTS, ROSTER, ["Quantum Computing"], now=NOW)
    assert not any(s["term"] == "quantum computing" for s in out)


def test_not_interested_drags_a_theme_out_of_contention():
    events = QUANTUM_EVENTS + [
        _event("not_interested", "Quantum computing hype cycle peaks", days_ago=0)  # −8 now
    ]
    assert not any(
        s["term"] == "quantum computing" for s in suggest_topics(events, ROSTER, [], now=NOW)
    )


def test_two_days_is_a_rabbit_hole_not_an_interest():
    events = [
        _event("more_like", h, days_ago=d)
        for h, d in zip(QUANTUM_HEADLINES[:3], (0, 0.3, 1))  # 15 pts, only 2 distinct days
    ]
    assert suggest_topics(events, ROSTER, [], now=NOW) == []


# -- the endpoints ---------------------------------------------------------------


def _env(tmp_path, monkeypatch):
    cfg = tmp_path / "news_categories.json"
    cfg.write_text(
        json.dumps([{"slug": "top", "title": "Top stories", "feeds": ["https://e.test/top"]}]),
        encoding="utf-8",
    )
    roster = tmp_path / "topics.json"
    roster.write_text(json.dumps(ROSTER, indent=2), encoding="utf-8")
    monkeypatch.setenv("NEWS_CATEGORIES_FILE", str(cfg))
    monkeypatch.setenv("ROSTER_FILE", str(roster))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    return roster


def _seed_quantum_events():
    """4 click rows across 3 calendar days, written straight into the store (the API
    always stamps 'now', so persistence needs raw inserts)."""
    from app.config import get_settings

    conn = sqlite3.connect(str(get_settings().db_path))
    try:
        for n, (headline, days_ago) in enumerate(zip(QUANTUM_HEADLINES, (0, 0.2, 1, 2))):
            ts = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO news_events (kind, category_slug, item_id, headline, created_at) "
                "VALUES ('click', 'technology', ?, ?, ?)",
                (f"item{n}", headline, ts),
            )
        conn.commit()
    finally:
        conn.close()


class EmptyFeedFetcher:
    def fetch(self, url: str) -> bytes:
        return (
            b'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0">'
            b"<channel><title>t</title></channel></rss>"
        )


def _client():
    from fastapi.testclient import TestClient

    from app.deps import get_news_fetcher
    from app.main import app

    app.dependency_overrides[get_news_fetcher] = lambda: EmptyFeedFetcher()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    from app.config import get_settings
    from app.main import app

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_foryou_carries_suggestions_even_while_learning(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    _seed_quantum_events()
    body = _client().get("/api/news/foryou").json()
    assert body["learning"] is True  # 4 positive events — still cold
    assert [s["term"] for s in body["suggestions"]] == ["quantum computing"]
    assert body["suggestions"][0]["days_seen"] == 3


def test_add_appends_to_roster_and_coverage_silences_the_suggestion(tmp_path, monkeypatch):
    roster_file = _env(tmp_path, monkeypatch)
    _seed_quantum_events()
    client = _client()

    res = client.post("/api/news/suggestions/add", json={"term": "quantum computing"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "slug": "quantum-computing", "title": "Quantum Computing"}

    roster = json.loads(roster_file.read_text(encoding="utf-8"))
    assert roster[0] == ROSTER[0]  # existing entry untouched, order preserved
    assert roster[1] == {"slug": "quantum-computing", "title": "Quantum Computing", "paused": False}

    # The roster now covers the theme — the scout goes quiet without a dismissal.
    assert _client().get("/api/news/foryou").json()["suggestions"] == []


def test_add_duplicate_slug_is_409_not_an_overwrite(tmp_path, monkeypatch):
    roster_file = _env(tmp_path, monkeypatch)
    client = _client()
    assert client.post("/api/news/suggestions/add", json={"term": "AI / LLMs"}).status_code == 409
    assert json.loads(roster_file.read_text(encoding="utf-8")) == ROSTER  # untouched


def test_add_blank_term_400(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    assert _client().post("/api/news/suggestions/add", json={"term": "  "}).status_code == 400


def test_dismiss_persists_and_silences(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    _seed_quantum_events()
    client = _client()

    res = client.post("/api/news/suggestions/dismiss", json={"term": "Quantum Computing"})
    assert res.status_code == 200 and res.json()["term"] == "quantum computing"

    from app.store import list_news_dismissals

    assert list_news_dismissals() == ["quantum computing"]
    assert client.get("/api/news/foryou").json()["suggestions"] == []
