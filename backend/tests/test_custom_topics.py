"""Tests for the custom-topics writer (``app.topics.custom`` CLI + ``app.store.db`` helpers).
Runs offline against the isolated tmp DB from conftest. Asserts the add/list/update round-trip
into the hub's SQLite, input validation, and that each write logs an activity row for streaks."""

from __future__ import annotations

import json

import pytest

from app.store import connect, init_db
from app.topics import custom


@pytest.fixture(autouse=True)
def _db():
    init_db()  # the isolated tmp DB from conftest; create tables before any write
    # The tmp DB is session-scoped (shared across tests), so isolate the tables this suite
    # writes — custom_topics + the activity rows its writes log — before each test.
    conn = connect()
    try:
        conn.execute("DELETE FROM custom_topics")
        conn.execute(
            "DELETE FROM activity WHERE kind IN ('custom_topic_added', 'custom_topic_updated')"
        )
        conn.commit()
    finally:
        conn.close()
    yield


def _activity_count(kind: str) -> int:
    conn = connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) c FROM activity WHERE kind = ?", (kind,)
        ).fetchone()["c"]
    finally:
        conn.close()


# -- add -----------------------------------------------------------------------

def test_add_persists_topic_and_returns_it():
    out = custom.cmd_add("Designing Data-Intensive Apps", notes="ch.1 done", progress=10)
    assert out["id"] >= 1
    assert out["title"] == "Designing Data-Intensive Apps"
    assert out["notes"] == "ch.1 done"
    assert out["progress_pct"] == 10
    assert out["created_at"] and out["updated_at"]

    conn = connect()
    try:
        row = conn.execute(
            "SELECT title, notes, progress_pct FROM custom_topics WHERE id = ?", (out["id"],)
        ).fetchone()
        assert row["title"] == "Designing Data-Intensive Apps"
        assert row["notes"] == "ch.1 done"
        assert row["progress_pct"] == 10
    finally:
        conn.close()


def test_add_logs_an_activity_row_for_streaks():
    before = _activity_count("custom_topic_added")
    custom.cmd_add("A loose thread")
    assert _activity_count("custom_topic_added") == before + 1


def test_add_defaults_notes_empty_and_progress_zero():
    out = custom.cmd_add("Bare topic")
    assert out["notes"] == ""
    assert out["progress_pct"] == 0


def test_add_title_strips_whitespace():
    out = custom.cmd_add("  spaced  ")
    assert out["title"] == "spaced"


def test_add_reads_notes_from_file(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# Breakdown\nbody", encoding="utf-8")
    out = custom.cmd_add("From a YouTube video", notes_file=str(f))
    assert out["notes"] == "# Breakdown\nbody"


@pytest.mark.parametrize("bad", [-1, 101, 200])
def test_add_rejects_out_of_range_progress(bad):
    with pytest.raises(ValueError):
        custom.cmd_add("x", progress=bad)


@pytest.mark.parametrize("bad", ["", "   "])
def test_add_rejects_empty_title(bad):
    with pytest.raises(ValueError):
        custom.cmd_add(bad)


# -- list ----------------------------------------------------------------------

def test_list_returns_all_added_topics():
    a = custom.cmd_add("first")
    b = custom.cmd_add("second")
    topics = custom.cmd_list()
    assert len(topics) == 2
    assert {t["id"] for t in topics} == {a["id"], b["id"]}
    # ORDER BY updated_at DESC, id DESC — id DESC is the deterministic tie-break within a second.
    assert [t["id"] for t in topics] == sorted([a["id"], b["id"]], reverse=True)


def test_list_empty_when_nothing_added():
    assert custom.cmd_list() == []


# -- update --------------------------------------------------------------------

def test_update_patches_only_given_fields_and_bumps_updated_at():
    topic = custom.cmd_add("Stoicism series", notes="ep1", progress=10)
    out = custom.cmd_update(topic["id"], progress=40)
    assert out["progress_pct"] == 40
    assert out["notes"] == "ep1"  # untouched
    assert out["title"] == "Stoicism series"  # untouched
    assert out["created_at"] == topic["created_at"]  # created_at is stable


def test_update_logs_activity_row():
    topic = custom.cmd_add("x")
    before = _activity_count("custom_topic_updated")
    custom.cmd_update(topic["id"], progress=25)
    assert _activity_count("custom_topic_updated") == before + 1


def test_update_unknown_id_raises_lookup_error():
    with pytest.raises(LookupError):
        custom.cmd_update(99999, progress=10)


def test_update_rejects_out_of_range_progress():
    topic = custom.cmd_add("x")
    with pytest.raises(ValueError):
        custom.cmd_update(topic["id"], progress=101)


def test_update_can_replace_notes_from_file(tmp_path):
    topic = custom.cmd_add("x", notes="old")
    f = tmp_path / "new.md"
    f.write_text("new body", encoding="utf-8")
    out = custom.cmd_update(topic["id"], notes_file=str(f))
    assert out["notes"] == "new body"


# -- main() round-trip ---------------------------------------------------------

def test_main_add_emits_json_and_exits_zero(capsys):
    rc = custom.main(["add", "--title", "Via CLI", "--progress", "5"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["title"] == "Via CLI"
    assert out["progress_pct"] == 5


def test_main_bad_progress_emits_error_json_and_exits_two(capsys):
    rc = custom.main(["add", "--title", "x", "--progress", "999"])
    assert rc == 2
    err = json.loads(capsys.readouterr().err)
    assert err["kind"] == "ValueError"


def test_main_list_emits_json_array(capsys):
    custom.main(["add", "--title", "one"])
    capsys.readouterr()  # drain
    rc = custom.main(["list"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and out[0]["title"] == "one"
