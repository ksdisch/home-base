"""Phase-6 SM-2 scheduler — the pure, clock-injected math the per-item queue schedules on.

No DB, no time-travel: every transition takes ``now`` explicitly, so interval growth, the ease
floor, and lapse resets are all deterministic to assert.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.store import scheduler as s

NOW = datetime(2026, 6, 7, 12, 0, 0)


# -- signal mapping ------------------------------------------------------------

def test_quality_from_signal_maps_three_cases():
    assert s.quality_from_signal(correct=False, used_hint=False) == 2  # miss → lapse
    assert s.quality_from_signal(correct=False, used_hint=True) == 2   # a miss is a miss
    assert s.quality_from_signal(correct=True, used_hint=True) == 3    # hinted → hard pass
    assert s.quality_from_signal(correct=True, used_hint=False) == 5   # clean → good pass


# -- fresh item progression ----------------------------------------------------

def test_first_clean_pass_schedules_one_day_out():
    st = s.next_state(quality=5, now=NOW)
    assert st.reps == 1
    assert st.interval_days == s.FIRST_INTERVAL_DAYS
    assert st.due_at == NOW + timedelta(days=1)
    assert st.ease == pytest.approx(s.INITIAL_EASE + 0.1)


def test_second_pass_schedules_six_days_out():
    st = s.next_state(ease=2.6, interval_days=1.0, reps=1, quality=5, now=NOW)
    assert st.reps == 2
    assert st.interval_days == s.SECOND_INTERVAL_DAYS
    assert st.due_at == NOW + timedelta(days=6)


def test_third_pass_grows_by_ease():
    # reps already 2, interval 6d, ease 2.6 → next interval = round(6 * new_ease).
    st = s.next_state(ease=2.6, interval_days=6.0, reps=2, quality=5, now=NOW)
    assert st.reps == 3
    assert st.interval_days == pytest.approx(round(6.0 * st.ease, 4))
    assert st.interval_days > 6.0  # genuinely stretched out


def test_intervals_lengthen_monotonically_under_repeated_good_recall():
    """A 6-review simulation of always-correct recall: each interval strictly grows."""
    st = s.next_state(quality=5, now=NOW)
    intervals = [st.interval_days]
    clock = st.due_at
    for _ in range(5):
        st = s.next_state(
            ease=st.ease,
            interval_days=st.interval_days,
            reps=st.reps,
            lapses=st.lapses,
            quality=5,
            now=clock,
        )
        intervals.append(st.interval_days)
        clock = st.due_at
    assert intervals == sorted(intervals)
    assert intervals[-1] > intervals[0]
    assert st.lapses == 0


# -- lapses --------------------------------------------------------------------

def test_miss_resets_reps_and_relearns_tomorrow():
    # A mature item that gets missed collapses back to a 1-day relearn.
    mature = s.next_state(ease=2.6, interval_days=40.0, reps=5, lapses=0, quality=5, now=NOW)
    lapsed = s.next_state(
        ease=mature.ease,
        interval_days=mature.interval_days,
        reps=mature.reps,
        lapses=mature.lapses,
        quality=2,
        now=NOW,
    )
    assert lapsed.reps == 0
    assert lapsed.lapses == 1
    assert lapsed.interval_days == s.LAPSE_INTERVAL_DAYS
    assert lapsed.due_at == NOW + timedelta(days=1)
    assert lapsed.ease < mature.ease  # ease was penalized


def test_hinted_pass_grows_slower_than_clean_pass():
    hinted = s.next_state(ease=2.6, interval_days=6.0, reps=2, quality=3, now=NOW)
    clean = s.next_state(ease=2.6, interval_days=6.0, reps=2, quality=5, now=NOW)
    assert hinted.interval_days < clean.interval_days
    assert hinted.ease < clean.ease


# -- ease floor ----------------------------------------------------------------

def test_ease_never_drops_below_floor():
    ease = s.INITIAL_EASE
    # Hammer it with misses; ease must clamp at the floor, not go below.
    for _ in range(20):
        st = s.next_state(ease=ease, quality=2, now=NOW)
        ease = st.ease
    assert ease == pytest.approx(s.MIN_EASE)


# -- serialization -------------------------------------------------------------

def test_fmt_ts_matches_stored_form():
    assert s.fmt_ts(datetime(2026, 6, 7, 12, 0, 0)) == "2026-06-07 12:00:00"
