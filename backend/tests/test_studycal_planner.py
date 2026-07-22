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
