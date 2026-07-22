"""GET/POST /api/paths/{id}/schedule/* — the Study Scheduler router (v0).

House style: a fresh SQLite store + empty PATHS_DIR so the bundled Jacobian example is what's served,
the calendar reached through an injected ``FakeCalendarPort`` (real Google never touched), and the
negotiation lane overridden with a fake claude runner. Covers the opt-in roundtrip, the read-only
propose, the confirm→removable-ledger write, remove, and the honest not-connected degrade.
"""

from __future__ import annotations

import json

import pytest

JACOBIAN = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("PATHS_DIR", str(tmp_path / "hub" / "paths"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    yield tmp_path / "hub"
    get_settings.cache_clear()


def _client(port, *, negotiate_answer=None, code=0):
    from fastapi.testclient import TestClient

    from app.deps import get_calendar_port, get_study_negotiate_client
    from app.main import app

    app.dependency_overrides[get_calendar_port] = lambda: port
    if negotiate_answer is not None:
        from app.chat import BriefChatClient, ChatResult

        def runner(args):
            envelope = json.dumps(
                {
                    "result": negotiate_answer,
                    "total_cost_usd": 0.002,
                    "duration_ms": 9,
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                }
            )
            return ChatResult(list(args), envelope, "", code)

        app.dependency_overrides[get_study_negotiate_client] = lambda: BriefChatClient(
            model="sonnet", runner=runner
        )
    return TestClient(app), app


def _teardown(app):
    app.dependency_overrides.clear()


def _fake(**kw):
    from app.studycal.port import FakeCalendarPort

    return FakeCalendarPort(**kw)


def test_opt_in_roundtrips_and_state_reflects_it(env):
    client, app = _client(_fake())
    try:
        cold = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert cold["enabled"] is False and cold["session_minutes"] == 45 and cold["blocks"] == []
        assert cold["connected"] is True

        got = client.post(
            f"/api/paths/{JACOBIAN}/schedule/opt-in", json={"enabled": True, "session_minutes": 30}
        ).json()
        assert got["enabled"] is True and got["session_minutes"] == 30
    finally:
        _teardown(app)


def test_propose_is_read_only_and_covers_every_incomplete_step(env):
    port = _fake()
    client, app = _client(port)
    try:
        r = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["connected"] is True
        assert len(body["blocks"]) >= 1
        covered = [sid for b in body["blocks"] for sid in b["step_ids"]]
        step_count = client.get(f"/api/paths/{JACOBIAN}").json()["step_count"]
        assert len(covered) == step_count and body["unscheduled_step_ids"] == []  # the whole path
        # Read-only: nothing was written to the ledger or the calendar.
        assert client.get(f"/api/paths/{JACOBIAN}/schedule").json()["blocks"] == []
        assert port.events() == {}
    finally:
        _teardown(app)


def test_confirm_writes_the_batch_and_records_a_removable_ledger(env):
    port = _fake()
    client, app = _client(port)
    try:
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        state = client.post(
            f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]}
        ).json()
        assert len(state["blocks"]) == len(proposal["blocks"])
        # Every written block carries the Google identity that makes it removable.
        for b in state["blocks"]:
            assert b["event_id"].startswith("fake-ev-") and b["calendar_id"] == "study-cal-fake"
            assert b["status"] == "written"
        assert len(port.events()) == len(proposal["blocks"])  # actually hit the calendar
    finally:
        _teardown(app)


def test_remove_deletes_events_and_clears_live_blocks(env):
    port = _fake()
    client, app = _client(port)
    try:
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})
        n = len(proposal["blocks"])

        state = client.post(f"/api/paths/{JACOBIAN}/schedule/remove", json={}).json()
        assert state["blocks"] == []  # no live blocks left
        assert len(port.deleted) == n and port.events() == {}  # events actually deleted
    finally:
        _teardown(app)


def test_propose_when_calendar_not_connected_degrades_honestly(env):
    client, app = _client(_fake(connected=False))
    try:
        body = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        assert body["ok"] is False and body["connected"] is False and body["blocks"] == []
        # A confirm against a disconnected calendar is a clean 409, never a 500.
        r = client.post(
            f"/api/paths/{JACOBIAN}/schedule/confirm",
            json={"blocks": [{"start": "x", "end": "y", "minutes": 45, "title": "t", "step_ids": ["ep1"]}]},
        )
        assert r.status_code == 409
    finally:
        _teardown(app)


def test_confirm_with_no_blocks_is_422(env):
    client, app = _client(_fake())
    try:
        assert client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": []}).status_code == 422
    finally:
        _teardown(app)


def test_unparseable_note_falls_back_to_claude_and_logs_usage(env):
    # A phrasing the local parser can't read falls through to the claude lane, which sets knobs +
    # logs a usage row like the other claude lanes.
    answer = json.dumps({"day_start_hour": 7, "day_end_hour": 9, "message": "Mornings, 7-9am it is."})
    client, app = _client(_fake(), negotiate_answer=answer)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "whatever's best for my retention"},
        ).json()
        assert body["ok"] is True
        assert body["message"] == "Mornings, 7-9am it is."
        assert body["applied"]["day_start_hour"] == 7 and body["applied"]["day_end_hour"] == 9
        ledger = env / "study-negotiate.jsonl"
        assert ledger.is_file() and ledger.read_text().strip()
    finally:
        _teardown(app)


def test_parseable_note_skips_claude_entirely(env):
    # "mornings only" is handled by the local parser — the claude lane must NOT run (no ledger row),
    # even though a (would-be) answer is wired up.
    answer = json.dumps({"day_start_hour": 3, "message": "should not be used"})
    client, app = _client(_fake(), negotiate_answer=answer)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose", json={"preference": "mornings only"}
        ).json()
        assert body["applied"]["day_start_hour"] == 8 and body["applied"]["day_end_hour"] == 12  # parser
        assert body["message"] is None  # parser path is silent; the UI describes the plan itself
        assert not (env / "study-negotiate.jsonl").exists()  # claude never ran
    finally:
        _teardown(app)


def test_unreadable_note_is_honest_not_a_silent_noop(env):
    # Parser can't read it AND the claude lane errors → the plan is unchanged and the user is told,
    # rather than the old bug where the untouched default was shown as if it were the answer.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose", json={"preference": "do the thing you do"}
        ).json()
        assert body["ok"] is True
        assert "couldn't read that" in body["message"].lower()
        assert body["applied"]["day_start_hour"] == 9 and body["applied"]["day_end_hour"] == 17  # default, untouched
    finally:
        _teardown(app)


def test_schedule_404_for_an_unknown_path(env):
    client, app = _client(_fake())
    try:
        assert client.get("/api/paths/not-a-real-topic/schedule").status_code == 404
    finally:
        _teardown(app)


def _starts(body):
    from datetime import datetime

    return [datetime.fromisoformat(b["start"]) for b in body["blocks"]]


def test_propose_honors_explicit_controls_without_a_preference(env):
    # Structured controls drive the planner directly — no claude call needed. "weekday mornings"
    # via day-of-week + a daytime window is honored (the bug the rework fixes).
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={
                "days_of_week": [0, 1, 2, 3, 4],
                "day_start_hour": 8,
                "day_end_hour": 14,
                "session_minutes": 30,
            },
        ).json()
        assert body["ok"] is True and body["connected"] is True and len(body["blocks"]) >= 1
        applied = body["applied"]  # echoed effective knobs, so the UI can reflect them
        assert applied["days_of_week"] == [0, 1, 2, 3, 4]
        assert applied["day_start_hour"] == 8 and applied["day_end_hour"] == 14
        assert applied["session_minutes"] == 30
        for s in _starts(body):  # real clock → assert shape, not absolute dates
            assert s.weekday() in {0, 1, 2, 3, 4}
            assert 8 <= s.hour < 14
    finally:
        _teardown(app)


def test_propose_persists_prefs_across_visits(env):
    client, app = _client(_fake())
    try:
        client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"days_of_week": [1, 3], "day_start_hour": 9, "day_end_hour": 17,
                  "session_minutes": 60, "max_blocks": 4},
        )
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["days_of_week"] == [1, 3]
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 17
        assert state["session_minutes"] == 60 and state["max_blocks"] == 4
    finally:
        _teardown(app)


def test_note_refines_the_sent_controls(env):
    # Controls are set to weekday mornings; the note "evenings and weekends" refines them — the note
    # wins for the keys it names (days + window flip), and the keys it doesn't mention hold (session).
    client, app = _client(_fake())  # no claude — the parser handles this note
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={
                "preference": "evenings and weekends",
                "day_start_hour": 8, "day_end_hour": 12, "days_of_week": [0, 1, 2, 3, 4],
                "session_minutes": 30,
            },
        ).json()
        applied = body["applied"]
        assert applied["days_of_week"] == [5, 6]  # note overrode the weekday control
        assert applied["day_start_hour"] == 17 and applied["day_end_hour"] == 21  # evenings
        assert applied["session_minutes"] == 30  # untouched by the note → the control holds
        for s in _starts(body):
            assert s.weekday() in {5, 6} and 17 <= s.hour < 21
    finally:
        _teardown(app)


def test_exclusion_note_refines_current_days(env):
    # "not Mondays" drops Monday from the weekday control the user already has.
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "not Mondays", "days_of_week": [0, 1, 2, 3, 4]},
        ).json()
        assert body["applied"]["days_of_week"] == [1, 2, 3, 4]
        for s in _starts(body):
            assert s.weekday() in {1, 2, 3, 4}
    finally:
        _teardown(app)


def _booked_env(monkeypatch):
    # Fix "now" to Wed 2026-07-22 noon and book the 2-5pm band on Wed + Thu with titled events.
    import app.api.study as study_mod
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ct = ZoneInfo("America/Chicago")
    monkeypatch.setattr(study_mod, "_now", lambda: datetime(2026, 7, 22, 12, 0, tzinfo=ct))
    busy = [
        (datetime(2026, 7, 22, 14, 0, tzinfo=ct), datetime(2026, 7, 22, 17, 0, tzinfo=ct), "GF: dinner"),
        (datetime(2026, 7, 23, 14, 0, tzinfo=ct), datetime(2026, 7, 23, 17, 0, tzinfo=ct), "GF: errands"),
    ]
    return _fake(busy=busy)


def test_booked_window_flags_conflicts_and_offers_double_book(env, monkeypatch):
    port = _booked_env(monkeypatch)
    client, app = _client(port)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"day_start_hour": 14, "day_end_hour": 17, "days": 2, "session_minutes": 45},
        ).json()
        assert body["ok"] is True
        assert len(body["unscheduled_step_ids"]) > 0  # the 2-5pm window is fully booked both days
        assert body["can_double_book"] is True
        titles = [c["title"] for c in body["conflicts"]]
        assert "GF: dinner" in titles and "GF: errands" in titles  # flagged by name
    finally:
        _teardown(app)


def test_double_book_places_over_busy_and_labels_overlaps(env, monkeypatch):
    port = _booked_env(monkeypatch)
    client, app = _client(port)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={
                "day_start_hour": 14, "day_end_hour": 17, "days": 2, "session_minutes": 45,
                "allow_double_book": True,
            },
        ).json()
        assert len(body["blocks"]) > 0  # placed despite the busy calendar
        overlaps = [t for b in body["blocks"] for t in b["overlaps"]]
        assert "GF: dinner" in overlaps  # each block flags what it double-books
        assert body["can_double_book"] is False and body["conflicts"] == []
    finally:
        _teardown(app)
