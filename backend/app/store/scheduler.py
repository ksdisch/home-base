"""Phase-6 per-item spaced-repetition scheduler — pure, clock-injected SM-2.

Phase 4 fades one mastery score per *topic* against a single uniform half-life
(:mod:`app.store.mastery`). This module makes the **question** the unit of scheduling: each
question carries its own SM-2 state (ease / interval / reps / lapses / ``due_at``) updated from
how it was actually answered, so a well-known item stretches out and a shaky one snaps back.

Like ``mastery.py`` this is deliberately honest and tiny — classic SM-2, not a 17-parameter
FSRS we couldn't validate. Everything is pure and takes ``now`` explicitly, so interval growth,
the ease floor, and lapse resets are all deterministic to assert without time-travel. The DB
layer (:func:`app.store.db.record_attempt`) calls :func:`next_state` and persists the result;
nothing here touches SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# -- tunables (classic SM-2) ---------------------------------------------------
INITIAL_EASE = 2.5        # the SM-2 default ease factor for a brand-new item
MIN_EASE = 1.3            # ease never drops below this (SM-2's floor)
FIRST_INTERVAL_DAYS = 1.0  # first successful recall → review tomorrow
SECOND_INTERVAL_DAYS = 6.0  # second successful recall → review in ~a week
LAPSE_INTERVAL_DAYS = 1.0  # a miss resets the item to relearn tomorrow
PASS_QUALITY = 3          # SM-2 quality >= 3 is a successful recall


@dataclass(frozen=True)
class SrState:
    """A question's spaced-repetition state after a review.

    ``last_review_at`` / ``due_at`` are naive-UTC datetimes; the DB layer serializes them with
    :func:`fmt_ts` into the store's ``"YYYY-MM-DD HH:MM:SS"`` form.
    """

    ease: float
    interval_days: float
    reps: int
    lapses: int
    last_review_at: datetime
    due_at: datetime


def now_utc() -> datetime:
    """Current time as a naive-UTC ``datetime`` — matches the store's ``datetime('now')`` form."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fmt_ts(dt: datetime) -> str:
    """Serialize a datetime to the store's ``"YYYY-MM-DD HH:MM:SS"`` (naive UTC) form."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def quality_from_signal(correct: bool, used_hint: bool) -> int:
    """Map the hub's grading signal to an SM-2 quality (0–5).

    miss → 2 (a lapse), hinted-correct → 3 (a *hard* pass), clean-correct → 5 (a good pass).
    These are the only three signals ``record_attempt`` produces, so we keep the mapping tight.
    """
    if not correct:
        return 2
    return 3 if used_hint else 5


# Flashcard self-grades reuse the exact quality trio the quiz signal produces, so a card and a
# question with the same recall history schedule identically: again = a lapse, hard = a hinted-
# grade pass, good = a clean pass.
FLASHCARD_QUALITY = {"again": 2, "hard": 3, "good": 5}


def _next_ease(ease: float, quality: int) -> float:
    """SM-2 ease update, floored at :data:`MIN_EASE`.

    q=5 → +0.10, q=3 → −0.14, q=2 → −0.32. (The classic ``EF + (0.1 - (5-q)(0.08 + (5-q)0.02))``.)
    """
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    return max(MIN_EASE, ease + delta)


def next_state(
    *,
    ease: float = INITIAL_EASE,
    interval_days: float = 0.0,
    reps: int = 0,
    lapses: int = 0,
    quality: int,
    now: datetime,
) -> SrState:
    """Advance an item's SM-2 state given the quality of this recall.

    A pass (``quality >= PASS_QUALITY``) grows the interval (1d → 6d → ``interval × ease``);
    a lapse resets reps to 0 and schedules a relearn tomorrow. Ease is always nudged by quality.
    """
    new_ease = round(_next_ease(ease, quality), 4)

    if quality < PASS_QUALITY:
        new_reps = 0
        new_lapses = lapses + 1
        new_interval = LAPSE_INTERVAL_DAYS
    else:
        new_reps = reps + 1
        new_lapses = lapses
        if new_reps == 1:
            new_interval = FIRST_INTERVAL_DAYS
        elif new_reps == 2:
            new_interval = SECOND_INTERVAL_DAYS
        else:
            # Grow off the *prior* interval; guard a zero/garbage prior so growth still happens.
            base = interval_days if interval_days > 0 else SECOND_INTERVAL_DAYS
            new_interval = round(base * new_ease, 4)

    return SrState(
        ease=new_ease,
        interval_days=new_interval,
        reps=new_reps,
        lapses=new_lapses,
        last_review_at=now,
        due_at=now + timedelta(days=new_interval),
    )
