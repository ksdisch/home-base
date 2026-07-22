"""app.studycal.duration — per-kind minutes model for scheduling a path's steps (v0).

To defend calendar time you need per-step minutes. Audio steps carry a real ``estimated_minutes``
(a NotebookLM episode's length); quiz/flashcards/read/bridge don't in the fixture, so each gets a
sensible per-kind default; micro-glue (intro/reflect/recap) is tiny and *folds* into an adjacent
block rather than claiming its own calendar slot (Kyle's call, 2026-07-22). Pure + deterministic —
no clock, no DB, so every rule is trivially assertable."""

from __future__ import annotations

from typing import Any, Mapping, Optional

# Budget for a step whose ``estimated_minutes`` is missing/unusable.
_KIND_DEFAULTS = {
    "audio": 8,       # ~a NotebookLM episode; the real length is usually present and wins
    "read": 12,       # a study-guide read-through
    "flashcards": 8,  # a deck drill
    "quiz": 12,       # the mastery step — ~10-12 questions
    "bridge": 10,     # write an open-recall answer + read the grade
}
# Micro-glue: connective steps with no artifact and a minute of reading — they fold into an
# adjacent block instead of getting a standalone slot.
_FOLD_KINDS = frozenset({"intro", "reflect", "recap"})
_FOLD_MINUTES = 5
_FALLBACK_MINUTES = 10  # an unknown / forward-compatible kind


def _clean_estimate(value: Any) -> Optional[int]:
    """A positive rounded int from ``estimated_minutes``, else None. Bools and non-numbers are
    rejected so a stray ``True`` / ``"abc"`` / 0 can't slip through as a duration."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    n = int(round(value))
    return n if n > 0 else None


def is_foldable(step: Mapping[str, Any]) -> bool:
    """Micro-glue (intro/reflect/recap) folds into an adjacent block — it never claims its own slot.
    A bridge-check is glue but a real recall exercise, so it is NOT foldable."""
    return step.get("kind") in _FOLD_KINDS


def step_minutes(step: Mapping[str, Any]) -> int:
    """Minutes to budget for a step: its explicit ``estimated_minutes`` if usable, else a per-kind
    default (folding glue gets a small one, an unknown kind a modest fallback). Always >= 1."""
    est = _clean_estimate(step.get("estimated_minutes"))
    if est is not None:
        return est
    kind = step.get("kind")
    if kind in _FOLD_KINDS:
        return _FOLD_MINUTES
    return _KIND_DEFAULTS.get(kind, _FALLBACK_MINUTES)
