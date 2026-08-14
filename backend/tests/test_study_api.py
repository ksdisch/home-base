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


def _flaky(**kw):
    from app.studycal.port import FlakyCalendarPort

    return FlakyCalendarPort(**kw)


def _block_body(**kw):
    """A minimal well-formed confirm block (tz-aware RFC3339, as the planner emits)."""
    return {
        "start": "2099-07-22T18:00:00-05:00",
        "end": "2099-07-22T18:45:00-05:00",
        "minutes": 45,
        "title": "t",
        "step_ids": ["ep1"],
        **kw,
    }


def _opt_in(client, minutes=45):
    """Turn scheduling on. Required before any confirm — calendar writes are opt-in server-side,
    not just hidden in the UI."""
    return client.post(
        f"/api/paths/{JACOBIAN}/schedule/opt-in", json={"enabled": True, "session_minutes": minutes}
    )


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
        _opt_in(client)
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
        _opt_in(client)
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
        _opt_in(client)  # required, or the 409 below would pass for the wrong reason (opted out)
        body = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        assert body["ok"] is False and body["connected"] is False and body["blocks"] == []
        # A confirm against a disconnected calendar is a clean 409, never a 500.
        r = client.post(
            f"/api/paths/{JACOBIAN}/schedule/confirm",
            json={"blocks": [_block_body()]},
        )
        assert r.status_code == 409
        assert "connect" in r.json()["detail"].lower()  # the disconnect, not the opt-in gate
    finally:
        _teardown(app)


def test_confirm_with_no_blocks_is_422(env):
    client, app = _client(_fake())
    try:
        assert client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": []}).status_code == 422
    finally:
        _teardown(app)


# -- opt-in is a server-side gate, not just a hidden panel ---------------------------------------


def test_confirm_without_opt_in_is_409_and_writes_nothing(env):
    port = _fake()
    client, app = _client(port)
    try:
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        r = client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})
        assert r.status_code == 409
        # "Calendar writes only happen when you opt in" is load-bearing — a stale tab or a retried
        # POST must not be able to write events while GET /schedule reports enabled:false.
        assert port.events() == {}
        assert client.get(f"/api/paths/{JACOBIAN}/schedule").json()["blocks"] == []
    finally:
        _teardown(app)


def test_propose_still_works_while_opted_out(env):
    client, app = _client(_fake())
    try:
        # Propose writes no events, so it stays open — the panel needs it to preview a plan.
        assert client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).status_code == 200
    finally:
        _teardown(app)


# -- partial calendar writes: every created event keeps a ledger row -----------------------------


def test_a_mid_batch_calendar_failure_still_ledgers_every_created_event(env):
    port = _flaky(fail_at=2)
    client, app = _client(port)
    try:
        _opt_in(client)
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        assert len(proposal["blocks"]) > 3  # the batch must actually straddle the failure point
        r = client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})

        # Honest partial state, not a bare 500 and not a silent success.
        assert r.status_code == 502
        assert "2 of" in r.json()["detail"]

        written = client.get(f"/api/paths/{JACOBIAN}/schedule").json()["blocks"]
        created = set(port.events())
        # THE hard rule: nothing exists on the calendar without a ledger row to remove it by.
        assert created and {b["event_id"] for b in written} == created
    finally:
        _teardown(app)


def test_blocks_written_before_a_failure_are_still_removable(env):
    port = _flaky(fail_at=2)
    client, app = _client(port)
    try:
        _opt_in(client)
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})

        state = client.post(f"/api/paths/{JACOBIAN}/schedule/remove", json={}).json()
        # The recovery the ledger exists for: one tap clears the orphans a partial write left.
        assert state["blocks"] == [] and port.events() == {}
    finally:
        _teardown(app)


def test_a_failure_on_the_very_first_event_writes_nothing(env):
    port = _flaky(fail_at=0)
    client, app = _client(port)
    try:
        _opt_in(client)
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        r = client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})
        assert r.status_code == 502
        assert port.events() == {}
        assert client.get(f"/api/paths/{JACOBIAN}/schedule").json()["blocks"] == []
    finally:
        _teardown(app)


def test_confirm_rejects_block_times_that_are_not_tz_aware_iso(env):
    port = _fake()
    client, app = _client(port)
    try:
        _opt_in(client)
        r = client.post(
            f"/api/paths/{JACOBIAN}/schedule/confirm",
            json={"blocks": [{"start": "x", "end": "y", "minutes": 45, "title": "t", "step_ids": ["ep1"]}]},
        )
        # Unvalidated strings reach Google as a 400 mid-batch, and land in the ledger as rows a
        # later propose can't parse. Reject them at the door instead.
        assert r.status_code == 422 and port.events() == {}
    finally:
        _teardown(app)


# -- a second visit must not duplicate what's already on the calendar ---------------------------


def test_re_proposing_after_a_confirm_does_not_re_schedule_written_steps(env):
    port = _fake(feed_back=True)
    client, app = _client(port)
    try:
        _opt_in(client)
        first = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": first["blocks"]})
        written_events = len(port.events())

        again = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        # An innocent revisit re-proposed the identical plan, and confirming it wrote a full
        # duplicate event set. Steps already on the calendar are reported, not re-planned.
        scheduled = [sid for b in first["blocks"] for sid in b["step_ids"]]
        assert sorted(again["already_scheduled_step_ids"]) == sorted(scheduled)
        assert again["blocks"] == []
        assert again["message"] and "already" in again["message"].lower()

        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": again["blocks"]})
        assert len(port.events()) == written_events  # nothing new written
    finally:
        _teardown(app)


def test_confirm_skips_blocks_whose_steps_are_already_on_the_calendar(env):
    port = _fake(feed_back=True)
    client, app = _client(port)
    try:
        _opt_in(client)
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})
        n = len(port.events())

        # A double-tap / retry-after-timeout replays the same reviewed batch verbatim.
        r = client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": proposal["blocks"]})
        assert r.status_code == 409
        assert len(port.events()) == n  # not one duplicate event
    finally:
        _teardown(app)


def test_a_partial_retry_writes_only_the_blocks_that_are_missing(env):
    port = _fake(feed_back=True)
    client, app = _client(port)
    try:
        _opt_in(client)
        proposal = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        blocks = proposal["blocks"]
        assert len(blocks) >= 2
        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": blocks[:1]})

        # Resubmitting the whole batch after a partial write must complete it, not 409 the lot —
        # this is exactly the recovery path a mid-batch failure leaves behind.
        state = client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": blocks}).json()
        assert len(state["blocks"]) == len(blocks)
        assert len(port.events()) == len(blocks)
    finally:
        _teardown(app)


def test_new_blocks_dodge_the_study_blocks_already_written(env):
    port = _fake(feed_back=True)
    client, app = _client(port)
    try:
        _opt_in(client)
        first = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={"max_blocks": 1}).json()
        client.post(f"/api/paths/{JACOBIAN}/schedule/confirm", json={"blocks": first["blocks"]})
        taken = {(b["start"], b["end"]) for b in first["blocks"]}

        again = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).json()
        # free/busy only reads the primary calendar, so without merging the ledger the planner
        # would cheerfully book the learner on top of their own study block.
        assert again["blocks"]
        assert not any((b["start"], b["end"]) in taken for b in again["blocks"])
    finally:
        _teardown(app)


def test_a_ledger_row_with_unparseable_times_cannot_break_a_later_propose(env):
    port = _fake()
    client, app = _client(port)
    try:
        _opt_in(client)
        from app.store import study_blocks

        study_blocks.add_study_blocks(
            "path",
            JACOBIAN,
            [{"step_id": "ghost", "step_ids": ["ghost"], "calendar_id": "c", "event_id": "e",
              "title": "t", "start_at": "not-a-time", "end_at": "also-not"}],
        )
        # Rows predating the confirm-side validation must degrade, not 500 a propose forever.
        assert client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={}).status_code == 200
    finally:
        _teardown(app)


# -- the 7-day testing-mode consent leash, surfaced before it bites ------------------------------


def test_schedule_state_carries_the_token_age_so_the_ui_can_warn(env):
    client, app = _client(_fake(token_age_days=6.2))
    try:
        body = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert body["token_age_days"] == pytest.approx(6.2)
    finally:
        _teardown(app)


def test_schedule_state_token_age_is_null_when_the_port_cannot_say(env):
    client, app = _client(_fake())
    try:
        assert client.get(f"/api/paths/{JACOBIAN}/schedule").json()["token_age_days"] is None
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


def test_a_negated_time_note_does_not_schedule_the_hours_it_rules_out(env):
    # "nothing after 3pm" used to parse as a 3pm START, so the proposal — and the prefs persisted
    # ahead of it — landed on precisely the band the note ruled out, and every later visit
    # hydrated to that inverted reading.
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing after 3pm", "day_start_hour": 9, "day_end_hour": 17},
        ).json()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9  # the control holds — the note names only the end
        assert applied["day_end_hour"] == 15
        assert _starts(body)  # the window is real, not an empty plan that trivially passes
        for s in _starts(body):
            assert s.hour < 15
    finally:
        _teardown(app)


def test_a_negated_end_note_repairs_against_a_late_standing_start(env):
    # Review F3, the configuration the test above deliberately doesn't reach. A negated-end note
    # names only `day_end_hour`, so against a standing evening window it collided with the start
    # and `_apply_overrides` "repaired" it by pushing the END up — a 17:00–18:00 plan from a note
    # that said "nothing after 3pm", persisted for the next visit. The repair now moves the edge
    # the note did NOT name.
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing after 3pm", "day_start_hour": 17, "day_end_hour": 21},
        ).json()
        applied = body["applied"]
        assert applied["day_end_hour"] == 15  # the note is honored, not repaired away
        assert applied["day_start_hour"] < applied["day_end_hour"]
        for s in _starts(body):
            assert s.hour < 15
        # …and the persisted prefs carry the honored window, not the inverted repair.
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_end_hour"] == 15 and state["day_start_hour"] < 15
    finally:
        _teardown(app)


def test_a_plainly_worded_negated_start_never_plans_inside_the_excluded_band(env):
    # Review F6, end to end — the sharpest case in the whole loop. "nothing scheduled before 9am"
    # mis-parsed as an END bound, which the F3 repair then honored by pulling the start below it:
    # every block landed before 9am, the one band the note excluded, and that inverted window was
    # persisted, so the panel hydrated to 08:00–09:00 on the next visit.
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing scheduled before 9am", "day_start_hour": 9, "day_end_hour": 17},
        ).json()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 17
        assert _starts(body)
        for s in _starts(body):
            assert s.hour >= 9
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 17
    finally:
        _teardown(app)


def test_an_unreadable_exclusion_leaves_the_window_alone_instead_of_inverting_it(env):
    # Reviews F8/F11, end to end. "nothing from 9am until 5pm" is a workday exclusion. It has been
    # wrong three different ways: a zero-width parse repaired into a 17:00–18:00 day (F8), and then
    # the range applied verbatim, planning every block inside the very band it rules out (F11).
    # The parser now withholds the window, so the note reaches the claude lane — here wired to
    # fail — and the honest "couldn't read that" degrade holds the controls untouched.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing from 9am until 5pm", "day_start_hour": 9, "day_end_hour": 21},
        ).json()
        assert body["ok"] is True
        assert "couldn't read that" in body["message"].lower()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 21  # controls held
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 21  # nothing inverted
    finally:
        _teardown(app)


def test_a_prepositional_exclusion_never_plans_inside_the_band_it_rules_out(env):
    # Review F10, end to end — the failure this class keeps reproducing. "nothing from home before
    # 9am" fell back to the plain scan, which read the 9am as an END, and the F3 repair honored it:
    # every block landed at 08:00 and the learner's 21:00 end was overwritten with 09:00.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing from home before 9am", "day_start_hour": 9, "day_end_hour": 21},
        ).json()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 21
        assert _starts(body)
        for s in _starts(body):
            assert s.hour >= 9
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 21
    finally:
        _teardown(app)


def test_a_window_plus_a_negated_day_clause_still_applies_the_window(env):
    # Review F14, end to end — and the reason it was invisible: the note is non-empty (the days
    # parse), so the "couldn't read that" degrade never fires. The learner got a 09:00 block from
    # a note that said evenings, with no message to explain it.
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "weekday evenings, nothing on Sundays", "day_start_hour": 9, "day_end_hour": 21},
        ).json()
        applied = body["applied"]
        assert applied["day_start_hour"] == 17 and applied["day_end_hour"] == 21
        assert _starts(body)
        for s in _starts(body):
            assert s.hour >= 17
    finally:
        _teardown(app)


def test_one_readable_negation_does_not_license_an_unreadable_one(env):
    # Review F15, end to end. The two-clause note read the 2pm start and then answered the 3pm
    # exclusion backwards: blocks at 15:00 and 19:00 — all inside the excluded band — and the
    # inverted 15/21 window persisted over the learner's 9/21.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={
                "preference": "nothing from work after 3pm, not before 2pm",
                "day_start_hour": 9, "day_end_hour": 21,
            },
        ).json()
        assert "couldn't read that" in body["message"].lower()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 21
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 21
    finally:
        _teardown(app)


def test_a_negated_named_window_never_becomes_the_window_to_schedule(env):
    # Review F16, end to end — the headline inversion, re-opened for every phrasing without digits.
    # "nothing in the afternoon" applied 12->17, planned a 12:00 block and persisted 12/17, with
    # message: None to explain any of it.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing in the afternoon", "day_start_hour": 9, "day_end_hour": 21},
        ).json()
        assert "couldn't read that" in body["message"].lower()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 21
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 21
    finally:
        _teardown(app)


def test_a_conjunction_joined_day_exclusion_still_applies_the_window(env):
    # Review F17, end to end: the same note the comma form handles, joined with "and" instead.
    client, app = _client(_fake())
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"preference": "nothing on Fridays and 9am to 5pm", "day_start_hour": 9, "day_end_hour": 21},
        ).json()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 17
        assert _starts(body)
        for s in _starts(body):
            assert 9 <= s.hour < 17
    finally:
        _teardown(app)


def test_an_unreadable_window_reaches_the_fallback_instead_of_planning_the_excluded_band(env):
    # Review F21, end to end and the reason it mattered: withholding only the window left the note
    # non-empty (days + session parsed), so the claude lane never ran, `message` stayed None, and
    # the STANDING 9-21 window was planned — booking 18:00 blocks inside "the evening", the one
    # band the note excludes. Dropping the whole note is what actually reaches the fallback.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={
                "preference": "45 minute blocks, nothing in the evening, 9am to 5pm",
                "day_start_hour": 9, "day_end_hour": 21,
            },
        ).json()
        assert "couldn't read that" in body["message"].lower()
        assert body["applied"]["day_end_hour"] == 21  # controls held; nothing invented
    finally:
        _teardown(app)


def test_an_hours_on_days_exclusion_never_plans_the_band_it_rules_out(env):
    # Review F20, end to end: "nothing on saturdays or sundays after 3pm" applied 15->21 and
    # planned 15:00 blocks — the excluded band — and persisted the inverted window.
    client, app = _client(_fake(), negotiate_answer="boom", code=1)
    try:
        body = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={
                "preference": "nothing on saturdays or sundays after 3pm",
                "day_start_hour": 9, "day_end_hour": 21,
            },
        ).json()
        assert "couldn't read that" in body["message"].lower()
        applied = body["applied"]
        assert applied["day_start_hour"] == 9 and applied["day_end_hour"] == 21
        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 9 and state["day_end_hour"] == 21
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


def test_propose_with_a_midnight_window_does_not_500(env):
    # ``day_end_hour`` is clamped to 1..24, so 24 ("study until midnight") is reachable straight from
    # the request body — the planner has to honour the domain its own callers clamp to.
    client, app = _client(_fake())
    try:
        r = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"day_start_hour": 20, "day_end_hour": 24, "session_minutes": 30},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and len(body["blocks"]) >= 1
        assert body["applied"]["day_start_hour"] == 20 and body["applied"]["day_end_hour"] == 24
        for s in _starts(body):  # real clock → assert shape, not absolute dates
            assert s.hour >= 20
    finally:
        _teardown(app)


def test_a_repaired_23_hour_start_does_not_poison_every_later_propose(env):
    # The inverted-window repair is ``day_end_hour = min(24, day_start_hour + 1)``, so a 23:00 start
    # manufactures 24 — and prefs are persisted BEFORE the plan runs. A planner that can't represent
    # 24 would therefore make the stored window durable poison: every later propose, even with an
    # empty body, would fail on prefs the panel's 6–20 / 7–22 selects can't dial back out of.
    client, app = _client(_fake())
    try:
        first = client.post(
            f"/api/paths/{JACOBIAN}/schedule/propose",
            json={"day_start_hour": 23, "day_end_hour": 23},
        )
        assert first.status_code == 200
        assert first.json()["applied"]["day_end_hour"] == 24  # repaired upward, not rejected

        state = client.get(f"/api/paths/{JACOBIAN}/schedule").json()
        assert state["day_start_hour"] == 23 and state["day_end_hour"] == 24  # persisted as-is

        again = client.post(f"/api/paths/{JACOBIAN}/schedule/propose", json={})
        assert again.status_code == 200
        assert again.json()["applied"] == first.json()["applied"]
    finally:
        _teardown(app)
