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
from pathlib import Path

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


def test_persistence_gate_counts_local_days_not_utc_days():
    """Bug #13: evening sittings straddle UTC midnight — naive created_at truncated to a
    UTC date lets TWO Chicago sittings satisfy the '≥3 distinct days' gate. The gate's
    stated intent is a persistent interest, so the bucket is the America/Chicago day."""
    events = [
        {"kind": "click", "category_slug": "technology", "item_id": "x",
         "headline": h, "created_at": ts}
        for h, ts in zip(QUANTUM_HEADLINES, (
            "2026-07-16T15:00:00+00:00",  # Jul 16, 10:00 AM CT
            "2026-07-17T01:00:00+00:00",  # Jul 16,  8:00 PM CT — the same local evening
            "2026-07-17T02:00:00+00:00",  # Jul 16,  9:00 PM CT
            "2026-07-18T01:00:00+00:00",  # Jul 17,  8:00 PM CT
        ))
    ]
    # Three UTC dates (16/17/18) but only TWO Chicago days (16 + 17): score qualifies
    # (~11.3 ≥ 9), the persistence gate must still refuse.
    assert suggest_topics(events, ROSTER, [], now=NOW) == []


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
    # The synthetic stand-in for sweeps/prompts/_template.md — prompts live next to the
    # roster file, exactly like the real sweeps/ layout sweep.sh reads.
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "_template.md").write_text(
        "Sweep **{{TITLE}}** with sourced items only.\n", encoding="utf-8"
    )
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


# -- the add must produce a sweepable topic, not just a roster entry (P1 bug #2) ------
# sweep.sh requires prompts/<slug>.md per roster topic and counts its absence as a
# failure — a roster entry alone means the topic never sweeps and every 06:00 run
# exits 1 forever after (docs/bug-hunt/2026-07-19-post-m7.md).


def test_add_stamps_a_sweep_prompt_from_the_template(tmp_path, monkeypatch):
    """The one-click add writes prompts/<slug>.md from _template.md with the title
    filled in — otherwise the advertised 'tomorrow's sweep picks it up' is false."""
    roster_file = _env(tmp_path, monkeypatch)
    res = _client().post("/api/news/suggestions/add", json={"term": "quantum computing"})
    assert res.status_code == 200
    prompt = (roster_file.parent / "prompts" / "quantum-computing.md").read_text(encoding="utf-8")
    assert prompt == "Sweep **Quantum Computing** with sourced items only.\n"


def test_add_never_overwrites_a_hand_written_prompt(tmp_path, monkeypatch):
    """A prompt file that already exists (hand-tuned) wins — the add only fills gaps."""
    roster_file = _env(tmp_path, monkeypatch)
    hand = roster_file.parent / "prompts" / "quantum-computing.md"
    hand.write_text("Hand-tuned prompt.\n", encoding="utf-8")
    res = _client().post("/api/news/suggestions/add", json={"term": "quantum computing"})
    assert res.status_code == 200
    assert hand.read_text(encoding="utf-8") == "Hand-tuned prompt.\n"


def test_add_without_template_fails_closed_roster_untouched(tmp_path, monkeypatch):
    """No usable template → 400 and NO roster entry — a promptless roster topic is
    exactly the rc=1-forever failure this guard exists to prevent."""
    roster_file = _env(tmp_path, monkeypatch)
    (roster_file.parent / "prompts" / "_template.md").unlink()
    res = _client().post("/api/news/suggestions/add", json={"term": "quantum computing"})
    assert res.status_code == 400
    assert json.loads(roster_file.read_text(encoding="utf-8")) == ROSTER
    assert not (roster_file.parent / "prompts" / "quantum-computing.md").exists()


def test_concurrent_adds_do_not_lose_a_roster_write(tmp_path, monkeypatch):
    """Bug #12: FastAPI runs these sync handlers on a threadpool and the UI shows up to
    3 Add cards — two Adds racing the read→modify→replace on sweeps/topics.json let the
    loser's entry vanish while both report ok. The write section must serialize."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app import news

    roster_file = _env(tmp_path, monkeypatch)

    # Park both racers between the roster read and the roster write (the prompt stamp
    # sits exactly there), so pre-fix each writes from the same pre-add snapshot. After
    # the fix the lock serializes the whole section and the barrier just times out.
    barrier = threading.Barrier(2, timeout=1.0)
    real_stamp = news._write_topic_prompt

    def parked_stamp(roster_file, slug, title):
        real_stamp(roster_file, slug, title)
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass

    monkeypatch.setattr(news, "_write_topic_prompt", parked_stamp)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(news.append_roster_topic, roster_file, term)
            for term in ("quantum computing", "sourdough baking")
        ]
        for f in futures:
            f.result(timeout=10)

    slugs = [t["slug"] for t in json.loads(roster_file.read_text(encoding="utf-8"))]
    assert sorted(slugs) == ["ai-llms", "quantum-computing", "sourdough-baking"]


def test_repo_prompt_template_matches_the_m0_sourcing_bar():
    """The checked-in template the add stamps out carries the real contract: the
    {{TITLE}} placeholder, the strict-JSON output rule, and the M0-tuned hard rules
    (exclusion carries the same sourcing bar as inclusion)."""
    template = (
        Path(__file__).resolve().parents[2] / "sweeps" / "prompts" / "_template.md"
    ).read_text(encoding="utf-8")
    assert "{{TITLE}}" in template
    assert "first character must be `{`" in template
    assert "Never fabricate" in template
    assert "Excluding a story carries the same sourcing bar" in template


def test_dismiss_persists_and_silences(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    _seed_quantum_events()
    client = _client()

    res = client.post("/api/news/suggestions/dismiss", json={"term": "Quantum Computing"})
    assert res.status_code == 200 and res.json()["term"] == "quantum computing"

    from app.store import list_news_dismissals

    assert list_news_dismissals() == ["quantum computing"]
    assert client.get("/api/news/foryou").json()["suggestions"] == []
