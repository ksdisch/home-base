"""app.study.duration — per-kind minutes model for scheduling path steps (v0).

Kyle's call (2026-07-22): audio uses its real ``estimated_minutes``; quiz/flashcards/read/bridge get
sensible per-kind defaults; micro-glue (intro/reflect/recap) folds into an adjacent block rather than
claiming its own calendar slot.
"""

from __future__ import annotations

from app.studycal.duration import is_foldable, step_minutes


def _step(kind: str, **extra) -> dict:
    return {"id": kind, "kind": kind, "title": kind.title(), **extra}


def test_audio_uses_its_real_estimated_minutes() -> None:
    assert step_minutes(_step("audio", estimated_minutes=9)) == 9
    assert step_minutes(_step("audio", estimated_minutes=7)) == 7


def test_untimed_kinds_get_per_kind_defaults() -> None:
    # No estimated_minutes on quiz/flashcards/read/bridge in the real fixture — each gets a
    # sensible, distinct default so it still claims real time.
    assert step_minutes(_step("quiz")) == 12
    assert step_minutes(_step("flashcards")) == 8
    assert step_minutes(_step("read")) == 12
    assert step_minutes(_step("bridge")) == 10


def test_explicit_estimate_overrides_the_default_for_any_kind() -> None:
    # An authored estimate always wins over the per-kind default.
    assert step_minutes(_step("quiz", estimated_minutes=20)) == 20


def test_bogus_estimated_minutes_falls_back_to_the_default() -> None:
    # 0 / negative / non-numeric / bool must not slip through as a duration.
    assert step_minutes(_step("quiz", estimated_minutes=0)) == 12
    assert step_minutes(_step("quiz", estimated_minutes=-5)) == 12
    assert step_minutes(_step("quiz", estimated_minutes="abc")) == 12
    assert step_minutes(_step("quiz", estimated_minutes=True)) == 12


def test_micro_glue_is_foldable_and_small() -> None:
    for kind in ("intro", "reflect", "recap"):
        assert is_foldable(_step(kind)) is True
        assert step_minutes(_step(kind)) <= 5
    # A bridge-check is glue too but is a real recall exercise — NOT foldable.
    assert is_foldable(_step("bridge")) is False
    assert is_foldable(_step("audio", estimated_minutes=8)) is False


def test_unknown_kind_gets_a_modest_default_and_is_not_foldable() -> None:
    assert step_minutes(_step("mystery")) == 10
    assert is_foldable(_step("mystery")) is False
