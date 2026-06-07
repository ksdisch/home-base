"""Phase-4 mastery decay model — the pure, clock-injected math the queue ranks on.

No DB, no time-travel: every function takes ``now`` explicitly, so half-life decay, the due
threshold, priority ordering, and timestamp parsing are all deterministic to assert.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.store import mastery as m


def _ago(now: datetime, days: float) -> str:
    """A stored-style ``"YYYY-MM-DD HH:MM:SS"`` timestamp ``days`` before ``now``."""
    return (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


NOW = datetime(2026, 6, 7, 12, 0, 0)


# -- timestamp parsing ---------------------------------------------------------

def test_parse_ts_handles_stored_naive_form():
    assert m.parse_ts("2026-06-07 12:00:00") == datetime(2026, 6, 7, 12, 0, 0)


def test_parse_ts_normalizes_tz_aware_to_naive_utc():
    # 12:00 at +02:00 == 10:00 UTC, returned naive.
    assert m.parse_ts("2026-06-07T12:00:00+02:00") == datetime(2026, 6, 7, 10, 0, 0)


def test_parse_ts_accepts_trailing_z_and_bare_date():
    assert m.parse_ts("2026-06-07T12:00:00Z") == datetime(2026, 6, 7, 12, 0, 0)
    assert m.parse_ts("2026-06-07") == datetime(2026, 6, 7, 0, 0, 0)


def test_parse_ts_none_and_garbage_are_none():
    assert m.parse_ts(None) is None
    assert m.parse_ts("") is None
    assert m.parse_ts("not-a-date") is None


# -- decay ---------------------------------------------------------------------

def test_decay_factor_at_zero_and_half_lives():
    assert m.decay_factor(0) == 1.0
    assert m.decay_factor(m.HALF_LIFE_DAYS) == pytest.approx(0.5)
    assert m.decay_factor(2 * m.HALF_LIFE_DAYS) == pytest.approx(0.25)


def test_decayed_mastery_fresh_review_keeps_score():
    assert m.decayed_mastery(1.0, _ago(NOW, 0), NOW) == pytest.approx(1.0)


def test_decayed_mastery_halves_after_one_half_life():
    assert m.decayed_mastery(1.0, _ago(NOW, m.HALF_LIFE_DAYS), NOW) == pytest.approx(0.5, abs=1e-3)
    assert m.decayed_mastery(0.8, _ago(NOW, 2 * m.HALF_LIFE_DAYS), NOW) == pytest.approx(0.2, abs=1e-3)


def test_decayed_mastery_never_reviewed_is_zero():
    assert m.decayed_mastery(1.0, None, NOW) == 0.0


def test_decayed_mastery_clamps_out_of_range_score():
    assert m.decayed_mastery(5.0, _ago(NOW, 0), NOW) == 1.0
    assert m.decayed_mastery(-2.0, _ago(NOW, 0), NOW) == 0.0


# -- due + priority ------------------------------------------------------------

def test_is_due_threshold_boundary():
    assert m.is_due(0.49) is True
    assert m.is_due(0.5) is False  # exactly at threshold is not yet due
    assert m.is_due(0.51) is False


def test_priority_rises_as_retention_falls():
    assert m.review_priority(1.0, 0) == pytest.approx(0.0)
    assert m.review_priority(0.0, 0) == pytest.approx(100.0)
    assert m.review_priority(0.5, 0) < m.review_priority(0.2, 0)


def test_priority_misses_break_ties_and_are_bounded():
    same_retention = 0.6
    clean = m.review_priority(same_retention, 0)
    shaky = m.review_priority(same_retention, 3)
    assert shaky > clean
    assert shaky == pytest.approx(clean + 3 * m.MISS_WEIGHT)
    # Never runs away unbounded.
    assert m.review_priority(0.0, 10_000) == m.PRIORITY_CAP


def test_days_since_none_when_never_reviewed():
    assert m.days_since(None, NOW) is None
    assert m.days_since(_ago(NOW, 3), NOW) == pytest.approx(3.0, abs=1e-6)
