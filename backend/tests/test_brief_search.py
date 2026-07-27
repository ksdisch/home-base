"""GET /api/brief/search — "where did I read that?" over every brief + note.

The archive index made the corpus browsable but not findable, and no search exists anywhere
over Kyle's own history (News-mode's term feeds query Google, not him). The corpus grows by
8 files a day forever (docs/ideas/archive-search.md).

Zero LLM by construction: a deterministic newest-first walk of ``data/sweeps/*/<topic>.json``
plus ``brief_notes``, plain case-insensitive substring matching, capped. Read-only — the
backend never writes under data/sweeps.

Hits carry the day so the UI can deep-link to ``?date=``, which is the whole point: finding
the item is only useful if it opens the morning it belongs to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DAY_A = "2026-07-20"
DAY_B = "2026-07-22"


def _brief(top_line: str, *items: dict) -> dict:
    return {
        "as_of": "2026-07-22",
        "top_line": top_line,
        "context_note": None,
        "items": list(items),
    }


def _item(headline: str, digest: str = "", why: str = "") -> dict:
    return {
        "headline": headline,
        "attribution": "Wire, July 2026",
        "digest": digest,
        "why_it_matters": why,
        "sources": [{"title": "Wire", "url": "https://example.test/a"}],
    }


def _sweeps(tmp_path: Path, days: dict) -> Path:
    root = tmp_path / "sweeps"
    for date, topics in days.items():
        day = root / date
        day.mkdir(parents=True, exist_ok=True)
        for slug, payload in topics.items():
            (day / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")
            (day / f"{slug}.md").write_text(f"# {slug}\n", encoding="utf-8")
    return root


CORPUS = {
    DAY_A: {
        "ai-llms": _brief(
            "A quiet week for models.",
            _item("Anthropic ships a new context window", digest="A longer window lands."),
            _item("Nothing to see here", digest="Filler about widgets."),
        ),
    },
    DAY_B: {
        "ai-llms": _brief(
            "Context windows everywhere.",
            _item("A rival matches the context window", why="Anthropic's lead narrows."),
        ),
        "chiefs": _brief(
            "Camp opens.",
            _item("Chiefs camp battle at guard", digest="Two linemen compete."),
        ),
    },
}


def _client(tmp_path, monkeypatch, corpus=CORPUS):
    sweeps = _sweeps(tmp_path, corpus)
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    roster = tmp_path / "topics.json"
    roster.write_text(
        json.dumps([{"slug": "ai-llms", "title": "AI / LLMs", "paused": False}]), encoding="utf-8"
    )
    monkeypatch.setenv("ROSTER_FILE", str(roster))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    from app.config import get_settings

    get_settings.cache_clear()


def _search(client, q: str, **params):
    return client.get("/api/brief/search", params={"q": q, **params}).json()


# -- matching ----------------------------------------------------------------------


def test_a_headline_match_carries_its_day_for_the_deep_link(tmp_path, monkeypatch):
    body = _search(_client(tmp_path, monkeypatch), "context window")

    briefs = [h for h in body["hits"] if h["kind"] == "item"]
    assert {h["date"] for h in briefs} == {DAY_A, DAY_B}
    assert all(h["topic_slug"] == "ai-llms" for h in briefs)
    # The item anchor the archive page already understands.
    assert all(h["item_id"] for h in briefs)


def test_the_digest_and_why_it_matters_are_searched_too(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    assert any(h["headline"] == "Chiefs camp battle at guard" for h in _search(client, "linemen")["hits"])
    assert any(h["headline"] == "A rival matches the context window" for h in _search(client, "lead narrows")["hits"])


def test_matching_is_case_insensitive(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert len(_search(client, "ANTHROPIC")["hits"]) == len(_search(client, "anthropic")["hits"]) > 0


def test_newest_day_first(tmp_path, monkeypatch):
    dates = [h["date"] for h in _search(_client(tmp_path, monkeypatch), "context window")["hits"]]
    assert dates == sorted(dates, reverse=True)


def test_a_miss_is_an_honest_empty_result(tmp_path, monkeypatch):
    body = _search(_client(tmp_path, monkeypatch), "kryptonite")
    assert body["hits"] == [] and body["total"] == 0


def test_a_blank_query_searches_nothing_rather_than_everything(tmp_path, monkeypatch):
    """An empty box must not dump the whole corpus — that's a browse, and /archive is it."""
    client = _client(tmp_path, monkeypatch)
    assert _search(client, "")["hits"] == []
    assert _search(client, "   ")["hits"] == []


# -- notes are part of the corpus --------------------------------------------------


def test_notes_are_searched_beside_the_briefs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    from app.store import add_brief_note

    add_brief_note(
        item_id="abc123abc123",
        topic_slug="ai-llms",
        brief_date=DAY_A,
        item_headline="Anthropic ships a new context window",
        body="Remember to check the pricing math on this",
    )

    hits = _search(client, "pricing math")["hits"]

    assert len(hits) == 1
    assert hits[0]["kind"] == "note"
    assert hits[0]["date"] == DAY_A  # deep-links to the morning the note is attached to
    assert "pricing math" in hits[0]["snippet"]


def test_briefs_and_notes_are_labeled_so_one_list_stays_readable(tmp_path, monkeypatch):
    """Idea-doc question 1: one blended newest-first list, each hit labeled by kind —
    two separate groups would make "where did I read that?" a two-place search."""
    client = _client(tmp_path, monkeypatch)
    from app.store import add_brief_note

    add_brief_note(
        item_id="abc123abc123",
        topic_slug="ai-llms",
        brief_date=DAY_B,
        item_headline="A rival matches the context window",
        body="context window race is on",
    )

    kinds = {h["kind"] for h in _search(client, "context window")["hits"]}
    assert kinds == {"item", "note"}


# -- honesty + robustness ----------------------------------------------------------


def test_the_cap_is_reported_so_a_truncated_result_says_so(tmp_path, monkeypatch):
    corpus = {
        f"2026-06-{d:02d}": {
            "ai-llms": _brief("t", *[_item(f"widget number {d}-{n}") for n in range(10)])
        }
        for d in range(1, 12)
    }
    client = _client(tmp_path, monkeypatch, corpus)

    body = _search(client, "widget", limit=25)

    assert len(body["hits"]) == 25
    assert body["total"] == 110  # what was actually found, not what fit
    assert body["truncated"] is True


def test_an_unparseable_day_is_skipped_never_fatal(tmp_path, monkeypatch):
    sweeps = _sweeps(tmp_path, CORPUS)
    bad = sweeps / "2026-07-21"
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "ai-llms.json").write_text("{not json", encoding="utf-8")
    (bad / "ai-llms.md").write_text("# broken\n", encoding="utf-8")
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app
    from app.store import init_db

    get_settings.cache_clear()
    init_db()

    resp = TestClient(app).get("/api/brief/search", params={"q": "context window"})

    assert resp.status_code == 200
    assert len(resp.json()["hits"]) == 2  # the two good days still answer


def test_no_sweeps_at_all_is_200_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEEPS_DIR", str(tmp_path / "nothing"))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app
    from app.store import init_db

    get_settings.cache_clear()
    init_db()

    resp = TestClient(app).get("/api/brief/search", params={"q": "anything"})

    assert resp.status_code == 200 and resp.json()["hits"] == []


def test_the_search_writes_nothing_under_data_sweeps(tmp_path, monkeypatch):
    """The backend's standing rule: data/sweeps is read-only to it."""
    sweeps = _sweeps(tmp_path, CORPUS)
    before = {p: p.stat().st_mtime_ns for p in sorted(sweeps.rglob("*")) if p.is_file()}
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    TestClient(app).get("/api/brief/search", params={"q": "context window"})

    after = {p: p.stat().st_mtime_ns for p in sorted(sweeps.rglob("*")) if p.is_file()}
    assert after == before
