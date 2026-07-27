"""app.studycal.planner — the deterministic session planner (v0).

Pure + deterministic: given a path's incomplete steps, a set of busy intervals, and an injected
``now``, it packs whole steps into session-length blocks (never splitting a step), then places each
block in the earliest free slot inside a daily study window — skipping busy time, never the past,
one block per day by default. No clock, no DB, no network, so every property is asserted directly.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.studycal.planner import PlanConfig, plan_sessions

CT = ZoneInfo("America/Chicago")


def _audio(sid: str, mins: int) -> dict:
    return {"id": sid, "kind": "audio", "title": sid, "estimated_minutes": mins}


def _step(sid: str, kind: str, **extra) -> dict:
    return {"id": sid, "kind": kind, "title": sid, **extra}


def _ids(block: dict) -> list[str]:
    return block["step_ids"]


# -- packing (pure, no placement concerns) -------------------------------------

def test_packs_whole_steps_up_to_the_session_cap() -> None:
    steps = [_audio("ep1", 8), _audio("ep2", 9), _audio("ep3", 8), _audio("ep4", 7)]
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    plan = plan_sessions(steps, busy=[], now=now, config=PlanConfig(session_minutes=20))
    # 8+9=17 fits 20; +8 would be 25 → close. Then 8+7=15 → close. Two blocks.
    assert len(plan["blocks"]) == 2
    assert _ids(plan["blocks"][0]) == ["ep1", "ep2"]
    assert _ids(plan["blocks"][1]) == ["ep3", "ep4"]
    # A block defends the negotiated session length, not just the raw content minutes.
    assert plan["blocks"][0]["minutes"] == 20


def test_a_single_over_long_step_gets_its_own_block_never_split() -> None:
    steps = [_audio("ep1", 8), _step("guide", "read", estimated_minutes=12)]
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    plan = plan_sessions(steps, busy=[], now=now, config=PlanConfig(session_minutes=10))
    assert [_ids(b) for b in plan["blocks"]] == [["ep1"], ["guide"]]
    # The 12-min step exceeds the 10-min cap, so its block stretches to hold it whole (no split).
    assert plan["blocks"][1]["minutes"] == 12


def test_foldable_glue_rides_along_and_never_opens_its_own_block() -> None:
    steps = [_step("intro", "intro"), _audio("ep1", 8), _step("reflect", "reflect")]
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    plan = plan_sessions(steps, busy=[], now=now, config=PlanConfig(session_minutes=45))
    assert len(plan["blocks"]) == 1
    assert _ids(plan["blocks"][0]) == ["intro", "ep1", "reflect"]


def test_glue_after_a_full_session_attaches_rather_than_opening_a_block() -> None:
    steps = [_audio("ep1", 40), _audio("ep2", 8), _step("reflect", "reflect")]
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    plan = plan_sessions(steps, busy=[], now=now, config=PlanConfig(session_minutes=45))
    # ep1(40) closes when ep2(+8=48) won't fit; ep2 opens block 2; reflect folds onto block 2.
    assert [_ids(b) for b in plan["blocks"]] == [["ep1"], ["ep2", "reflect"]]


# -- placement against free/busy -----------------------------------------------

def test_places_in_earliest_free_slot_skipping_a_busy_interval() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    busy = [(datetime(2026, 7, 22, 18, 0, tzinfo=CT), datetime(2026, 7, 22, 19, 0, tzinfo=CT))]
    plan = plan_sessions(
        [_audio("ep1", 8)],
        busy=busy,
        now=now,
        config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21),
    )
    # 18:00-19:00 is busy; the 45-min block lands at 19:00 in the same evening window.
    assert plan["blocks"][0]["start"] == "2026-07-22T19:00:00-05:00"
    assert plan["blocks"][0]["end"] == "2026-07-22T19:45:00-05:00"


def test_a_fully_busy_day_is_skipped_to_the_next_day() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    busy = [(datetime(2026, 7, 22, 17, 0, tzinfo=CT), datetime(2026, 7, 22, 22, 0, tzinfo=CT))]
    plan = plan_sessions(
        [_audio("ep1", 8)],
        busy=busy,
        now=now,
        config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21),
    )
    assert plan["blocks"][0]["start"] == "2026-07-23T18:00:00-05:00"


def test_one_block_per_day_spreads_sessions_across_days() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    steps = [_audio("ep1", 40), _audio("ep2", 40), _audio("ep3", 40)]
    plan = plan_sessions(
        steps, busy=[], now=now, config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21)
    )
    starts = [b["start"] for b in plan["blocks"]]
    assert starts == [
        "2026-07-22T18:00:00-05:00",
        "2026-07-23T18:00:00-05:00",
        "2026-07-24T18:00:00-05:00",
    ]


def test_a_long_first_session_never_lets_a_later_one_jump_ahead_of_it() -> None:
    # The curriculum is ordered, so the calendar must be too. An over-long session 1 that can't fit
    # what's left of today used to get pushed to tomorrow while session 2 took today's slot — the
    # calendar then told the learner to study step 2 the day BEFORE step 1.
    now = datetime(2026, 7, 22, 19, 30, tzinfo=CT)  # today's 18-21 window is already half gone
    steps = [_step("long", "read", estimated_minutes=100), _audio("short", 20)]
    plan = plan_sessions(
        steps, busy=[], now=now, config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21)
    )
    assert _ids(plan["blocks"][0]) == ["long"] and _ids(plan["blocks"][1]) == ["short"]
    assert plan["blocks"][0]["start"] < plan["blocks"][1]["start"]


def test_a_second_block_on_the_same_day_lands_after_the_first() -> None:
    # With max_per_day > 1, the earliest-free-slot search hands back the first gap that fits — and
    # a gap too small for the long session but big enough for the short one sits BEFORE the block
    # already placed. Placement has to floor at the previous block's end, not just its day.
    now = datetime(2026, 7, 22, 9, 0, tzinfo=CT)
    steps = [_step("long", "read", estimated_minutes=170), _audio("short", 20)]
    plan = plan_sessions(
        steps,
        busy=[(datetime(2026, 7, 22, 9, 50, tzinfo=CT), datetime(2026, 7, 22, 10, 0, tzinfo=CT))],
        now=now,
        config=PlanConfig(session_minutes=45, day_start_hour=9, day_end_hour=21, max_per_day=2),
    )
    assert len(plan["blocks"]) == 2
    starts = [b["start"] for b in plan["blocks"]]
    assert starts == sorted(starts)  # the docstring's "chronological" promise
    assert plan["blocks"][1]["start"] >= plan["blocks"][0]["end"]


def test_blocks_never_start_in_the_past() -> None:
    now = datetime(2026, 7, 22, 19, 30, tzinfo=CT)  # already inside today's window
    plan = plan_sessions(
        [_audio("ep1", 8)],
        busy=[],
        now=now,
        config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21),
    )
    # Today's window opened at 18:00 but it's 19:30 now — the block starts no earlier than now.
    assert plan["blocks"][0]["start"] == "2026-07-22T19:30:00-05:00"


def test_dst_offsets_are_correct_summer_and_winter() -> None:
    summer = plan_sessions(
        [_audio("ep1", 8)],
        busy=[],
        now=datetime(2026, 7, 22, 12, 0, tzinfo=CT),
        config=PlanConfig(day_start_hour=18, day_end_hour=21),
    )
    winter = plan_sessions(
        [_audio("ep1", 8)],
        busy=[],
        now=datetime(2026, 1, 20, 12, 0, tzinfo=CT),
        config=PlanConfig(day_start_hour=18, day_end_hour=21),
    )
    assert summer["blocks"][0]["start"].endswith("-05:00")  # CDT
    assert winter["blocks"][0]["start"].endswith("-06:00")  # CST


def test_no_incomplete_steps_yields_an_empty_plan() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    plan = plan_sessions([], busy=[], now=now, config=PlanConfig())
    assert plan["blocks"] == []
    assert plan["unscheduled_step_ids"] == []


def test_respects_max_blocks_and_reports_the_rest_unscheduled() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    steps = [_audio("ep1", 40), _audio("ep2", 40), _audio("ep3", 40)]
    plan = plan_sessions(
        steps, busy=[], now=now, config=PlanConfig(session_minutes=45, max_blocks=2)
    )
    assert len(plan["blocks"]) == 2
    assert plan["unscheduled_step_ids"] == ["ep3"]


# -- day-of-week window (weekdays / specific days / morning) -------------------

def test_days_of_week_skips_weekends() -> None:
    # 2026-07-24 is a Friday; the next two weekdays are Mon 07-27 and Tue 07-28 (Sat/Sun skipped).
    now = datetime(2026, 7, 24, 12, 0, tzinfo=CT)
    steps = [_audio("ep1", 40), _audio("ep2", 40), _audio("ep3", 40)]
    plan = plan_sessions(
        steps,
        busy=[],
        now=now,
        config=PlanConfig(
            session_minutes=45, day_start_hour=18, day_end_hour=21, days_of_week=frozenset({0, 1, 2, 3, 4})
        ),
    )
    starts = [b["start"] for b in plan["blocks"]]
    assert starts == [
        "2026-07-24T18:00:00-05:00",  # Fri
        "2026-07-27T18:00:00-05:00",  # Mon (Sat 07-25 + Sun 07-26 skipped)
        "2026-07-28T18:00:00-05:00",  # Tue
    ]


def test_days_of_week_honors_specific_days_only() -> None:
    # Tue+Thu only ({1, 3}) from Wed 07-22: first allowed is Thu 07-23, then Tue 07-28.
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    steps = [_audio("ep1", 40), _audio("ep2", 40)]
    plan = plan_sessions(
        steps,
        busy=[],
        now=now,
        config=PlanConfig(
            session_minutes=45, day_start_hour=18, day_end_hour=21, days_of_week=frozenset({1, 3})
        ),
    )
    starts = [b["start"] for b in plan["blocks"]]
    assert starts == ["2026-07-23T18:00:00-05:00", "2026-07-28T18:00:00-05:00"]


def test_none_days_of_week_allows_every_day_including_weekends() -> None:
    # The default (days_of_week=None) is unchanged: a weekend day is fair game.
    now = datetime(2026, 7, 24, 12, 0, tzinfo=CT)  # Friday
    steps = [_audio("ep1", 40), _audio("ep2", 40), _audio("ep3", 40)]
    plan = plan_sessions(
        steps, busy=[], now=now, config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21)
    )
    starts = [b["start"] for b in plan["blocks"]]
    assert starts == [
        "2026-07-24T18:00:00-05:00",  # Fri
        "2026-07-25T18:00:00-05:00",  # Sat — NOT skipped
        "2026-07-26T18:00:00-05:00",  # Sun
    ]


def test_ignore_busy_double_books_into_a_fully_busy_window() -> None:
    # Both evenings are fully booked. Normal placement can't fit anything; double-book (ignore_busy)
    # places into the window anyway — the "my girlfriend put stuff here but I can study through it" case.
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)  # Wed
    busy = [
        (datetime(2026, 7, 22, 17, 0, tzinfo=CT), datetime(2026, 7, 22, 22, 0, tzinfo=CT)),  # Wed 5-10pm
        (datetime(2026, 7, 23, 17, 0, tzinfo=CT), datetime(2026, 7, 23, 22, 0, tzinfo=CT)),  # Thu 5-10pm
    ]
    steps = [_audio("ep1", 40), _audio("ep2", 40)]
    cfg = PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21, window_days=2)

    normal = plan_sessions(steps, busy=busy, now=now, config=cfg)
    assert normal["blocks"] == [] and set(normal["unscheduled_step_ids"]) == {"ep1", "ep2"}

    dbl = plan_sessions(steps, busy=busy, now=now, config=cfg, ignore_busy=True)
    assert [b["start"] for b in dbl["blocks"]] == [
        "2026-07-22T18:00:00-05:00",
        "2026-07-23T18:00:00-05:00",
    ]
    assert dbl["unscheduled_step_ids"] == []


def test_morning_window_places_before_afternoon() -> None:
    # A daytime window (8am–2pm) is honored, not just the evening default.
    now = datetime(2026, 7, 22, 7, 0, tzinfo=CT)
    plan = plan_sessions(
        [_audio("ep1", 8)],
        busy=[],
        now=now,
        config=PlanConfig(session_minutes=45, day_start_hour=8, day_end_hour=14),
    )
    assert plan["blocks"][0]["start"] == "2026-07-22T08:00:00-05:00"
    assert plan["blocks"][0]["end"] == "2026-07-22T08:45:00-05:00"


def test_a_busy_boundary_block_still_serializes_in_ct_not_utc() -> None:
    # Google free/busy comes back in UTC. A block placed right after a busy interval must be
    # normalized to America/Chicago — not inherit the busy interval's +00:00 offset — so every
    # block time carries the CT offset (the documented invariant).
    utc = ZoneInfo("UTC")
    now = datetime(2026, 7, 22, 12, 0, tzinfo=CT)
    busy = [(datetime(2026, 7, 22, 22, 0, tzinfo=utc), datetime(2026, 7, 22, 23, 15, tzinfo=utc))]  # 17:00-18:15 CDT
    plan = plan_sessions(
        [_audio("ep1", 8)],
        busy=busy,
        now=now,
        config=PlanConfig(session_minutes=45, day_start_hour=18, day_end_hour=21),
    )
    assert plan["blocks"][0]["start"] == "2026-07-22T18:15:00-05:00"
    assert plan["blocks"][0]["end"] == "2026-07-22T19:00:00-05:00"
