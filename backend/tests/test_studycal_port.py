"""app.studycal.port — the CalendarPort seam + the in-memory FakeCalendarPort.

The API depends only on this Protocol, so the whole feature runs against the fake in tests while the
real Google adapter stays one isolated implementation. These lock the fake's contract (the seam the
router + planner rely on) — including the disconnected posture that drives the honest 'connect your
calendar' degrade.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.studycal.port import CalendarNotConnected, FakeCalendarPort, FlakyCalendarPort

CT = ZoneInfo("America/Chicago")


def test_connected_fake_ensures_a_stable_study_calendar_id() -> None:
    port = FakeCalendarPort()
    assert port.is_connected() is True
    cal = port.ensure_study_calendar()
    assert cal and port.ensure_study_calendar() == cal  # stable across calls


def test_free_busy_returns_only_intervals_overlapping_the_window() -> None:
    inside = (datetime(2026, 7, 22, 18, 0, tzinfo=CT), datetime(2026, 7, 22, 19, 0, tzinfo=CT))
    outside = (datetime(2026, 7, 25, 9, 0, tzinfo=CT), datetime(2026, 7, 25, 10, 0, tzinfo=CT))
    port = FakeCalendarPort(busy=[inside, outside])
    got = port.free_busy(datetime(2026, 7, 22, 0, 0, tzinfo=CT), datetime(2026, 7, 23, 0, 0, tzinfo=CT))
    assert got == [inside]


def test_create_returns_sequential_ids_and_stores_payloads() -> None:
    port = FakeCalendarPort()
    cal = port.ensure_study_calendar()
    ids = port.create_events(
        cal,
        [
            {"summary": "Study · ep1", "start": "2026-07-22T18:00:00-05:00", "end": "2026-07-22T18:45:00-05:00"},
            {"summary": "Study · quiz", "start": "2026-07-23T18:00:00-05:00", "end": "2026-07-23T18:45:00-05:00"},
        ],
    )
    assert len(ids) == 2 and len(set(ids)) == 2
    stored = port.events()
    assert stored[ids[0]]["summary"] == "Study · ep1"
    assert stored[ids[0]]["calendar_id"] == cal


def test_delete_removes_known_ids_and_ignores_unknown() -> None:
    port = FakeCalendarPort()
    cal = port.ensure_study_calendar()
    ids = port.create_events(cal, [{"summary": "s", "start": "x", "end": "y"}])
    port.delete_events(cal, [ids[0], "never-existed"])
    assert ids[0] not in port.events()
    assert port.deleted == [ids[0], "never-existed"]  # both recorded, no raise on the unknown


def test_busy_events_carry_titles_for_conflict_flagging() -> None:
    dinner = (datetime(2026, 7, 23, 14, 0, tzinfo=CT), datetime(2026, 7, 23, 15, 0, tzinfo=CT), "GF: dinner")
    plain = (datetime(2026, 7, 23, 16, 0, tzinfo=CT), datetime(2026, 7, 23, 17, 0, tzinfo=CT))  # 2-tuple
    outside = (datetime(2026, 7, 30, 9, 0, tzinfo=CT), datetime(2026, 7, 30, 10, 0, tzinfo=CT), "later")
    port = FakeCalendarPort(busy=[dinner, plain, outside])
    got = port.busy_events(datetime(2026, 7, 23, 0, 0, tzinfo=CT), datetime(2026, 7, 24, 0, 0, tzinfo=CT))
    assert [(e["title"]) for e in got] == ["GF: dinner", "Busy"]  # titled + the 2-tuple default
    assert got[0]["start"] == dinner[0] and got[0]["end"] == dinner[1]
    # free_busy still returns bare intervals (unchanged contract) even for titled busy.
    fb = port.free_busy(datetime(2026, 7, 23, 0, 0, tzinfo=CT), datetime(2026, 7, 24, 0, 0, tzinfo=CT))
    assert fb == [(dinner[0], dinner[1]), (plain[0], plain[1])]


def test_disconnected_fake_refuses_every_calendar_call() -> None:
    port = FakeCalendarPort(connected=False)
    assert port.is_connected() is False
    with pytest.raises(CalendarNotConnected):
        port.ensure_study_calendar()
    with pytest.raises(CalendarNotConnected):
        port.free_busy(datetime.now(CT), datetime.now(CT))
    with pytest.raises(CalendarNotConnected):
        port.busy_events(datetime.now(CT), datetime.now(CT))
    with pytest.raises(CalendarNotConnected):
        port.create_events("c", [{"summary": "s", "start": "x", "end": "y"}])
    with pytest.raises(CalendarNotConnected):
        port.create_event("c", {"summary": "s", "start": "x", "end": "y"})
    # An EMPTY batch must still refuse — otherwise a loop-based create_events silently
    # drops the disconnected contract for the zero-block case.
    with pytest.raises(CalendarNotConnected):
        port.create_events("c", [])


# -- single-event create: the seam that lets confirm ledger each event as it lands ---------------


def test_create_event_writes_one_event_and_shares_the_batch_id_sequence() -> None:
    port = FakeCalendarPort()
    cal = port.ensure_study_calendar()
    first = port.create_event(cal, {"summary": "solo", "start": "x", "end": "y"})
    rest = port.create_events(cal, [{"summary": "batch", "start": "x", "end": "y"}])
    # One id space, so a confirm that mixes both paths can never collide.
    assert first != rest[0] and len({first, *rest}) == 2
    assert port.events()[first]["summary"] == "solo"
    assert port.events()[first]["calendar_id"] == cal


# -- feed-back mode: written study blocks become visible busy ------------------------------------


def test_fake_hides_written_events_from_free_busy_by_default() -> None:
    port = FakeCalendarPort()
    cal = port.ensure_study_calendar()
    port.create_event(cal, {"summary": "s", "start": "2026-07-22T18:00:00-05:00", "end": "2026-07-22T18:45:00-05:00"})
    # The documented default: a test's propose sees a stable calendar, unperturbed by its own writes.
    assert port.free_busy(datetime(2026, 7, 22, 0, 0, tzinfo=CT), datetime(2026, 7, 23, 0, 0, tzinfo=CT)) == []


def test_feed_back_fake_reports_written_events_as_busy() -> None:
    port = FakeCalendarPort(feed_back=True)
    cal = port.ensure_study_calendar()
    port.create_event(cal, {"summary": "📚 ep1", "start": "2026-07-22T18:00:00-05:00", "end": "2026-07-22T18:45:00-05:00"})
    window = (datetime(2026, 7, 22, 0, 0, tzinfo=CT), datetime(2026, 7, 23, 0, 0, tzinfo=CT))
    # A real calendar cannot un-see what you just wrote to it — this is what makes a
    # self-double-booking re-propose reproducible at all.
    assert port.free_busy(*window) == [
        (datetime(2026, 7, 22, 18, 0, tzinfo=CT), datetime(2026, 7, 22, 18, 45, tzinfo=CT))
    ]
    assert [e["title"] for e in port.busy_events(*window)] == ["📚 ep1"]


def test_feed_back_fake_ignores_an_unparseable_written_event() -> None:
    port = FakeCalendarPort(feed_back=True)
    cal = port.ensure_study_calendar()
    port.create_event(cal, {"summary": "junk", "start": "x", "end": "y"})
    # Best-effort: a garbage payload is skipped, never raised, so it can't break a later propose.
    assert port.free_busy(datetime(2026, 7, 22, 0, 0, tzinfo=CT), datetime(2026, 7, 23, 0, 0, tzinfo=CT)) == []


# -- flaky mode: the mid-batch failure the plain fake structurally cannot produce ----------------


def test_flaky_port_fails_at_the_nth_event_leaving_the_earlier_ones_written() -> None:
    port = FlakyCalendarPort(fail_at=2)
    cal = port.ensure_study_calendar()
    ev = {"summary": "s", "start": "x", "end": "y"}
    assert port.create_event(cal, ev) and port.create_event(cal, ev)
    with pytest.raises(RuntimeError) as exc:
        port.create_event(cal, ev)
    # NOT a CalendarNotConnected — this models a rate limit / transient 5xx, the case the
    # router must translate into honest partial state rather than a bare 500.
    assert not isinstance(exc.value, CalendarNotConnected)
    assert len(port.events()) == 2  # the two that landed really are on the calendar


def test_flaky_port_without_fail_at_behaves_like_the_plain_fake() -> None:
    port = FlakyCalendarPort()
    cal = port.ensure_study_calendar()
    assert len(port.create_events(cal, [{"summary": "s", "start": "x", "end": "y"}] * 3)) == 3
