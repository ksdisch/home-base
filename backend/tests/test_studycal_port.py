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

from app.studycal.port import CalendarNotConnected, FakeCalendarPort

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
