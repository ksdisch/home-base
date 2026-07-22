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
        assert len(covered) == 9 and body["unscheduled_step_ids"] == []  # the whole 9-step path
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


def test_propose_with_a_preference_runs_negotiation_and_logs_usage(env):
    answer = json.dumps({"day_start_hour": 7, "day_end_hour": 9, "message": "Mornings, 7-9am it is."})
    client, app = _client(_fake(), negotiate_answer=answer)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose", json={"preference": "mornings only"}
        ).json()
        assert body["ok"] is True
        assert body["message"] == "Mornings, 7-9am it is."
        # The negotiation lane logged a usage row (backend data), like the other claude lanes.
        ledger = env / "study-negotiate.jsonl"
        assert ledger.is_file() and ledger.read_text().strip()
    finally:
        _teardown(app)


def test_schedule_404_for_an_unknown_path(env):
    client, app = _client(_fake())
    try:
        assert client.get("/api/paths/not-a-real-topic/schedule").status_code == 404
    finally:
        _teardown(app)
