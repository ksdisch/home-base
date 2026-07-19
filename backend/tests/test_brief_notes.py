"""M2 item ids + /api/brief/notes — inline notes on Today-brief items.

Synthetic sweep folders + roster only (never the real data/sweeps or sweeps/topics.json).
Under test: the read-time item id (stable across requests, unique within a brief, dup
headlines suffixed), the notes CRUD flow (create → joined inline onto the served brief →
browsable per topic → delete), and the snapshot invariant: a note outlives the sweep file
it annotated because the row carries topic/date/headline itself. House rules: empty note
bodies are a 400, deleting a missing note is a 404, and a legacy md-only day (no items,
no ids) must keep working untouched.
"""

from __future__ import annotations

import json
import re

VALID_BRIEF = {
    "topic": "ai-llms",
    "date": "2026-07-14",
    "as_of": "2026-07-14 07:05 CDT",
    "top_line": "One release actually worth your time.",
    "context_note": None,
    "items": [
        {
            "headline": "OpenAI lifts caps",
            "attribution": "Bleeping Computer, July 13, 2026",
            "digest": "OpenAI removed the rolling 5-hour cap.",
            "why_it_matters": "Shapes your agent session budget.",
            "sources": [{"title": "Bleeping Computer", "url": "https://example.com/a"}],
        },
        {
            "headline": "Anthropic ships a compute update",
            "attribution": "TechCrunch, July 14, 2026",
            "digest": "Details.",
            "why_it_matters": "Directly relevant.",
            "sources": [{"title": "TechCrunch", "url": "https://example.com/b"}],
        },
    ],
}

LEGACY_MD = """# fantasy-football — as of 2026-07-13 16:47 CDT

**Quiet camp-eve Monday.**

### An item — PFR, July 11
Digest here.
**Sources:** [PFR](https://example.com/pfr)
"""

PILOT_ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "fantasy-football", "title": "Fantasy football", "paused": False},
]

ITEM_ID = re.compile(r"^[0-9a-f]{12}(-\d+)?$")


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _env(tmp_path, monkeypatch, name: str, roster=PILOT_ROSTER):
    """Fresh store + fresh sweeps dir + synthetic roster file, all isolated under tmp_path."""
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    roster_file = tmp_path / name / "topics.json"
    roster_file.write_text(json.dumps(roster), encoding="utf-8")
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("ROSTER_FILE", str(roster_file))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    return sweeps


def _write_day(sweeps, date: str, files: dict[str, str]):
    day = sweeps / date
    day.mkdir(parents=True, exist_ok=True)
    for fname, text in files.items():
        (day / fname).write_text(text, encoding="utf-8")
    return day


def _note_payload(item, date="2026-07-14", slug="ai-llms", body="My take."):
    return {
        "item_id": item["id"],
        "topic_slug": slug,
        "brief_date": date,
        "item_headline": item["headline"],
        "body": body,
    }


# -- item ids -----------------------------------------------------------------------


def test_brief_items_carry_stable_unique_ids(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "ids")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        items1 = client.get("/api/brief").json()["topics"][0]["items"]
        items2 = client.get("/api/brief").json()["topics"][0]["items"]
        ids = [i["id"] for i in items1]
        assert all(ITEM_ID.fullmatch(i) for i in ids)
        assert len(set(ids)) == len(ids)  # unique within the brief
        assert ids == [i["id"] for i in items2]  # stable across requests
    finally:
        get_settings.cache_clear()


def test_brief_duplicate_headlines_get_suffixed_ids(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "dupids")
    dup = {
        **VALID_BRIEF,
        "items": [VALID_BRIEF["items"][0], dict(VALID_BRIEF["items"][0])],
    }
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(dup)})
    from app.config import get_settings

    try:
        ids = [i["id"] for i in _client().get("/api/brief").json()["topics"][0]["items"]]
        assert len(set(ids)) == 2
        assert ids[1] == f"{ids[0]}-2"
    finally:
        get_settings.cache_clear()


def test_legacy_md_day_still_serves_without_ids_or_notes(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "legacy")
    _write_day(sweeps, "2026-07-13", {"fantasy-football.md": LEGACY_MD})
    from app.config import get_settings

    try:
        topic = _client().get("/api/brief").json()["topics"][0]
        assert topic["items"] == []
        assert topic["raw_markdown"] is not None
    finally:
        get_settings.cache_clear()


# -- the notes flow -------------------------------------------------------------------


def test_note_roundtrip_appears_inline_on_the_brief(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "roundtrip")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        items = client.get("/api/brief").json()["topics"][0]["items"]
        assert all(i["notes"] == [] for i in items)

        created = client.post("/api/brief/notes", json=_note_payload(items[1])).json()
        assert created["id"] > 0
        assert created["item_id"] == items[1]["id"]
        assert created["topic_title"] == "AI / LLMs"  # resolved from the roster
        assert created["body"] == "My take."

        # Two notes on one item render oldest-first (reading order).
        client.post("/api/brief/notes", json=_note_payload(items[1], body="Second thought."))
        served = client.get("/api/brief").json()["topics"][0]["items"]
        assert [n["body"] for n in served[1]["notes"]] == ["My take.", "Second thought."]
        assert served[0]["notes"] == []  # the other item is untouched
    finally:
        get_settings.cache_clear()


def test_notes_browse_filters_by_topic_newest_first(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "browse")
    _write_day(
        sweeps,
        "2026-07-14",
        {
            "ai-llms.json": json.dumps(VALID_BRIEF),
            "fantasy-football.json": json.dumps({**VALID_BRIEF, "topic": "fantasy-football"}),
        },
    )
    from app.config import get_settings

    try:
        client = _client()
        topics = client.get("/api/brief").json()["topics"]
        ai_item = topics[0]["items"][0]
        ff_item = topics[1]["items"][0]
        client.post("/api/brief/notes", json=_note_payload(ai_item, body="ai note"))
        client.post(
            "/api/brief/notes",
            json=_note_payload(ff_item, slug="fantasy-football", body="ff note"),
        )

        all_notes = client.get("/api/brief/notes").json()["notes"]
        assert [n["body"] for n in all_notes] == ["ff note", "ai note"]  # newest first

        ff_only = client.get("/api/brief/notes?topic=fantasy-football").json()["notes"]
        assert [n["body"] for n in ff_only] == ["ff note"]
        assert ff_only[0]["topic_title"] == "Fantasy football"
    finally:
        get_settings.cache_clear()


def test_note_outlives_a_resweep_via_its_snapshot(tmp_path, monkeypatch):
    """The sweep file is regenerable; the note row is the durable record."""
    sweeps = _env(tmp_path, monkeypatch, "resweep")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        item = client.get("/api/brief").json()["topics"][0]["items"][0]
        client.post("/api/brief/notes", json=_note_payload(item))

        # A same-day re-sweep rewrites the file with different headlines...
        reworded = {
            **VALID_BRIEF,
            "items": [{**VALID_BRIEF["items"][0], "headline": "OpenAI lifts caps (updated)"}],
        }
        _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(reworded)})

        # ...so the inline join no longer matches (new id) — but the note itself is intact,
        # self-described by its snapshot.
        served = client.get("/api/brief").json()["topics"][0]["items"]
        assert all(n == [] for n in (i["notes"] for i in served))
        browse = client.get("/api/brief/notes").json()["notes"]
        assert len(browse) == 1
        assert browse[0]["item_headline"] == "OpenAI lifts caps"
        assert browse[0]["brief_date"] == "2026-07-14"
    finally:
        get_settings.cache_clear()


def test_note_delete_and_404(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "delete")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        item = client.get("/api/brief").json()["topics"][0]["items"][0]
        note_id = client.post("/api/brief/notes", json=_note_payload(item)).json()["id"]

        assert client.delete(f"/api/brief/notes/{note_id}").json()["ok"] is True
        assert client.get("/api/brief/notes").json()["notes"] == []
        assert client.delete(f"/api/brief/notes/{note_id}").status_code == 404
    finally:
        get_settings.cache_clear()


def test_note_empty_body_is_400(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "emptybody")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    from app.config import get_settings

    try:
        client = _client()
        item = client.get("/api/brief").json()["topics"][0]["items"][0]
        res = client.post("/api/brief/notes", json=_note_payload(item, body="   "))
        assert res.status_code == 400
        assert "body" in res.json()["detail"]
        assert client.get("/api/brief/notes").json()["notes"] == []
    finally:
        get_settings.cache_clear()


# -- QU5 notes-on-News: the same write path serves the second surface ----------------
# (docs/ideas/notes-on-news.md — a News/For-You card's note goes through POST /brief/notes
# with the category slug as topic_slug; the snapshot columns were built to make a note
# self-contained, so a slug that never appears in the Mode-A roster must still round-trip.)


def test_note_on_a_news_category_slug_round_trips(tmp_path, monkeypatch):
    """A news-card note (category slug, sha1(link) id, no sweep file anywhere) writes
    through the one notes path and browses on /notes with the humanized title fallback."""
    _env(tmp_path, monkeypatch, "newsnote")
    from app.config import get_settings

    try:
        client = _client()
        res = client.post(
            "/api/brief/notes",
            json={
                "item_id": "loc111loc111",
                "topic_slug": "local",  # a news category — deliberately not in the roster
                "brief_date": "2026-07-19",
                "item_headline": "Lake County story",
                "body": "Worth tracking",
            },
        )
        assert res.status_code == 200
        assert res.json()["topic_title"] == "Local"  # humanized fallback, not a roster title

        browse = client.get("/api/brief/notes").json()["notes"]
        assert [n["item_headline"] for n in browse] == ["Lake County story"]
        assert browse[0]["topic_title"] == "Local"
        assert browse[0]["topic_slug"] == "local"
    finally:
        get_settings.cache_clear()
