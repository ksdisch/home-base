"""set_topic_paused + PATCH /api/brief/topics/{slug} — the roster flag finally gets a verb.

``paused`` has been honored end to end since M2 (``load_roster`` reads it, the sweep gate
obeys it), and ``sweeps/README.md``'s official procedure for muting a topic is literally
"flip paused: true by hand" — an SSH-and-edit-JSON errand Kyle can't run from the phone
(docs/ideas/pause-topic-from-phone.md).

The write reuses the machinery ``append_roster_topic`` already owns: the module
``_roster_write_lock`` (sync FastAPI handlers run on a threadpool, so two taps can race a
read-modify-write) and a unique-tempfile atomic replace (``sweep.sh`` reads this file, and
must never see a half-written roster). Every other entry survives byte-for-byte.

The response also has to make the toggle *reversible from the page*: a paused topic produces
no file, so it has no brief card and no jump chip to un-pause from. ``BriefResponse`` now
carries the roster's paused entries so the UI can render them and turn the mute back off.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False},
    {"slug": "celtics", "title": "Boston Celtics", "paused": True},
]


def _roster(tmp_path: Path, entries=ROSTER) -> Path:
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return path


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# -- the writer --------------------------------------------------------------------


def test_pause_flips_only_its_own_entry(tmp_path):
    from app.news import set_topic_paused

    path = _roster(tmp_path)

    entry = set_topic_paused(path, "chiefs", True)

    assert entry == {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": True}
    rows = _read(path)
    assert [r["slug"] for r in rows] == ["ai-llms", "chiefs", "celtics"]  # order preserved
    assert [r["paused"] for r in rows] == [False, True, True]


def test_resume_flips_it_back(tmp_path):
    from app.news import set_topic_paused

    path = _roster(tmp_path)

    assert set_topic_paused(path, "celtics", False)["paused"] is False
    assert _read(path)[2]["paused"] is False


def test_unknown_slug_refuses_rather_than_appending(tmp_path):
    """A typo'd slug must not quietly grow the roster — that's the scout's job, not this one."""
    from app.news import set_topic_paused

    path = _roster(tmp_path)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        set_topic_paused(path, "not-a-topic", True)

    assert path.read_text(encoding="utf-8") == before


def test_unrelated_keys_on_an_entry_survive(tmp_path):
    """The roster is hand-editable; a field this code doesn't know about is not its to drop."""
    from app.news import set_topic_paused

    path = _roster(
        tmp_path, [{"slug": "ai-llms", "title": "AI / LLMs", "paused": False, "note": "keep me"}]
    )

    set_topic_paused(path, "ai-llms", True)

    assert _read(path)[0] == {
        "slug": "ai-llms",
        "title": "AI / LLMs",
        "paused": True,
        "note": "keep me",
    }


def test_an_unusable_roster_refuses_instead_of_clobbering(tmp_path):
    from app.news import set_topic_paused

    path = tmp_path / "topics.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError):
        set_topic_paused(path, "ai-llms", True)

    assert path.read_text(encoding="utf-8") == "{not json"  # untouched


def test_concurrent_toggles_never_lose_an_entry(tmp_path):
    """Bug #12's shape, on this write path: sync handlers run on a threadpool, so two taps
    can race the read-modify-write and silently drop the loser's change."""
    from app.news import set_topic_paused

    path = _roster(tmp_path)
    start = threading.Barrier(2)
    errors: list = []

    def toggle(slug: str):
        try:
            start.wait(timeout=5)
            set_topic_paused(path, slug, True)
        except Exception as e:  # noqa: BLE001 — surfaced as a test failure below
            errors.append(e)

    threads = [threading.Thread(target=toggle, args=(s,)) for s in ("ai-llms", "chiefs")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors
    rows = _read(path)
    assert len(rows) == 3  # nothing dropped
    assert all(r["paused"] for r in rows if r["slug"] in ("ai-llms", "chiefs"))


def test_no_tmp_files_left_behind(tmp_path):
    from app.news import set_topic_paused

    path = _roster(tmp_path)
    set_topic_paused(path, "chiefs", True)
    assert [p.name for p in tmp_path.iterdir()] == ["topics.json"]


# -- the endpoint ------------------------------------------------------------------


def _client(tmp_path, monkeypatch, entries=ROSTER):
    path = _roster(tmp_path, entries)
    monkeypatch.setenv("ROSTER_FILE", str(path))
    monkeypatch.setenv("SWEEPS_DIR", str(tmp_path / "sweeps"))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    return TestClient(app), path


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    from app.config import get_settings

    get_settings.cache_clear()


def test_patch_pauses_a_topic(tmp_path, monkeypatch):
    client, path = _client(tmp_path, monkeypatch)

    body = client.patch("/api/brief/topics/chiefs", json={"paused": True}).json()

    assert body == {
        "ok": True,
        "slug": "chiefs",
        "title": "Kansas City Chiefs",
        "paused": True,
    }
    assert _read(path)[1]["paused"] is True


def test_patch_resumes_a_topic(tmp_path, monkeypatch):
    client, path = _client(tmp_path, monkeypatch)

    assert client.patch("/api/brief/topics/celtics", json={"paused": False}).status_code == 200
    assert _read(path)[2]["paused"] is False


def test_patch_unknown_slug_is_404(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.patch("/api/brief/topics/nope", json={"paused": True}).status_code == 404


def test_patch_an_unusable_roster_is_a_named_failure_not_a_500(tmp_path, monkeypatch):
    path = tmp_path / "topics.json"
    path.write_text("[[[", encoding="utf-8")
    monkeypatch.setenv("ROSTER_FILE", str(path))
    monkeypatch.setenv("SWEEPS_DIR", str(tmp_path / "sweeps"))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()

    resp = TestClient(app).patch("/api/brief/topics/ai-llms", json={"paused": True})

    assert resp.status_code == 400
    assert "roster" in resp.json()["detail"].lower()


# -- the toggle has to be reversible from the page ---------------------------------


def test_the_brief_names_the_paused_topics(tmp_path, monkeypatch):
    """A paused topic produces no file, so it has no card and no jump chip — without this
    the mute would be one-way from the phone."""
    client, _ = _client(tmp_path, monkeypatch)

    body = client.get("/api/brief").json()

    assert body["paused_topics"] == [{"slug": "celtics", "title": "Boston Celtics"}]


def test_pausing_then_reloading_shows_it_as_paused(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    client.patch("/api/brief/topics/chiefs", json={"paused": True})

    slugs = [t["slug"] for t in client.get("/api/brief").json()["paused_topics"]]
    assert slugs == ["chiefs", "celtics"]  # roster order


def test_a_paused_topic_is_not_reported_as_missing(tmp_path, monkeypatch):
    """QU12's banner names topics that *should* have run. A deliberate mute isn't a failure."""
    client, _ = _client(tmp_path, monkeypatch)
    body = client.get("/api/brief").json()
    assert "celtics" not in [t["slug"] for t in body["missing_topics"]]
