"""Phase-4 mastery decay + the spaced-repetition "Review next" queue.

Phases 2–3 capture the raw signal (`topic_mastery`/`question_mastery`, each with a
``last_review_at``); this module fades it against an injected clock and ranks what to review.

The model is deliberately honest, not a fake SuperMemo: mastery is **estimated current
retention** = the last stored score, decayed by time since last review. Half-life decay
(``score * 0.5 ** (days / HALF_LIFE_DAYS)``) — intuitive ("mastery halves every two weeks
unreviewed"), monotonic, and trivial to reason about. Everything pure takes ``now`` explicitly
so tests are deterministic without time-travel; the read helpers take an optional ``db_path``
like ``store/progress.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .db import connect

# -- tunables ------------------------------------------------------------------
HALF_LIFE_DAYS = 14.0  # mastery halves every two weeks without a review
DUE_THRESHOLD = 0.5     # estimated retention below this → "due for review"
MISS_WEIGHT = 5.0       # how hard each unresolved miss pushes a topic up the queue
PRIORITY_CAP = 200.0    # keep the priority score bounded/comparable

# Phase-6 per-item (SM-2) queue tunables.
ITEM_LAPSE_WEIGHT = 2.0   # each accumulated lapse nudges a question up the per-item queue
NEW_ITEM_PRIORITY = 1.0   # base priority for never-scheduled (legacy/no-due_at) questions


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse a stored timestamp into a naive-UTC ``datetime`` (or ``None``).

    The store writes ``datetime('now')`` → ``"YYYY-MM-DD HH:MM:SS"`` (naive UTC). We also accept
    full ISO-8601 (incl. a trailing ``Z`` or offset) and normalize everything to naive UTC so
    arithmetic against :func:`now_utc` is consistent.
    """
    if not ts:
        return None
    raw = ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        try:  # bare date
            dt = datetime.fromisoformat(raw[:10])
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def now_utc() -> datetime:
    """Current time as a naive-UTC ``datetime`` — matches the store's ``datetime('now')`` form."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def days_since(last_review_at: Optional[str], now: datetime) -> Optional[float]:
    """Fractional days between ``last_review_at`` and ``now``; ``None`` if never reviewed."""
    then = parse_ts(last_review_at)
    if then is None:
        return None
    return (now - then).total_seconds() / 86400.0


def decay_factor(days: float, half_life: float = HALF_LIFE_DAYS) -> float:
    """Fraction of mastery retained after ``days`` (1.0 at 0 days, 0.5 at one half-life)."""
    if days <= 0:
        return 1.0
    return 0.5 ** (days / half_life)


def decayed_mastery(
    score: float, last_review_at: Optional[str], now: datetime, *, half_life: float = HALF_LIFE_DAYS
) -> float:
    """Estimated current retention: the stored ``score`` faded by time since last review.

    Never reviewed (``last_review_at is None``) → ``0.0`` (no retention to credit). Clamped to
    ``[0, 1]`` so a bad row can't produce a nonsense mastery.
    """
    d = days_since(last_review_at, now)
    if d is None:
        return 0.0
    return _clamp01(_clamp01(score) * decay_factor(d, half_life))


def is_due(decayed: float, *, threshold: float = DUE_THRESHOLD) -> bool:
    """Has estimated retention fallen below the review threshold?"""
    return decayed < threshold


def review_priority(decayed: float, miss_count: int) -> float:
    """Queue ordering score (higher = review sooner).

    Retention gap dominates (``(1 - decayed) * 100``, so a fully-forgotten topic ≈ 100); each
    unresolved miss adds ``MISS_WEIGHT`` to push shaky material up and break ties between topics
    at similar retention. Bounded by :data:`PRIORITY_CAP`.
    """
    gap = (1.0 - _clamp01(decayed)) * 100.0
    return round(min(PRIORITY_CAP, gap + max(0, miss_count) * MISS_WEIGHT), 1)


def _reason(decayed: float, days: Optional[float], miss_count: int, due: bool) -> str:
    """A short, human "why this surfaced" line — never invented question prose."""
    parts: List[str] = [f"retention ~{round(decayed * 100)}%"]
    if days is not None:
        whole = int(round(days))
        if whole <= 0:
            parts.append("practiced today")
        elif whole == 1:
            parts.append("last practiced yesterday")
        else:
            parts.append(f"last practiced {whole}d ago")
    if miss_count > 0:
        parts.append(f"{miss_count} {'miss' if miss_count == 1 else 'misses'} to clean up")
    lead = "Due — " if due else "On track — "
    return lead + " · ".join(parts)


def review_queue(
    now: Optional[datetime] = None,
    *,
    half_life: float = HALF_LIFE_DAYS,
    threshold: float = DUE_THRESHOLD,
    limit: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Rank practiced topics by how much review they need now.

    Joins ``topic_mastery`` (the stored fraction + ``last_review_at``) with per-notebook
    aggregated ``question_mastery`` misses, applies the decay model, and sorts due-first then by
    priority (then most-stale). One row per topic that has *any* mastery history; topics never
    quizzed don't appear (no signal to decay). Returns plain dicts — the route resolves titles.
    """
    now = now or now_utc()
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT tm.notebook_id                                   AS notebook_id,
                   tm.score                                         AS score,
                   tm.last_review_at                                AS last_review_at,
                   COALESCE(qm.total_misses, 0)                     AS total_misses,
                   COALESCE(qm.shaky_questions, 0)                  AS shaky_questions
            FROM topic_mastery AS tm
            LEFT JOIN (
                SELECT notebook_id,
                       SUM(miss_count)                          AS total_misses,
                       SUM(CASE WHEN miss_count > 0 THEN 1 END) AS shaky_questions
                FROM question_mastery
                GROUP BY notebook_id
            ) AS qm ON qm.notebook_id = tm.notebook_id
            -- Courses namespace their attempts as 'course:<slug>' in these shared tables; the
            -- notebook-facing "Review next" queue + home badges exclude them (courses have their
            -- own review surface). See app.courses.COURSE_NB_PREFIX.
            WHERE tm.notebook_id NOT LIKE 'course:%'
            """
        ).fetchall()
    finally:
        conn.close()

    out: List[Dict[str, Any]] = []
    for r in rows:
        decayed = decayed_mastery(r["score"], r["last_review_at"], now, half_life=half_life)
        d = days_since(r["last_review_at"], now)
        misses = int(r["total_misses"] or 0)
        due = is_due(decayed, threshold=threshold)
        out.append(
            {
                "notebook_id": r["notebook_id"],
                "mastery": round(_clamp01(r["score"] or 0.0), 3),
                "decayed": round(decayed, 3),
                "due": due,
                "priority": review_priority(decayed, misses),
                "days_since_review": None if d is None else round(d, 2),
                "total_misses": misses,
                "shaky_questions": int(r["shaky_questions"] or 0),
                "last_review_at": r["last_review_at"],
                "reason": _reason(decayed, d, misses, due),
            }
        )

    # Due first, then most-urgent priority, then most-stale, then stable by id.
    out.sort(
        key=lambda t: (
            not t["due"],
            -t["priority"],
            -(t["days_since_review"] or 0.0),
            t["notebook_id"],
        )
    )
    return out[:limit] if limit is not None else out


# -- Phase-6 per-item (SM-2) queue ---------------------------------------------

def days_overdue(due_at: Optional[str], now: datetime) -> Optional[float]:
    """Fractional days ``now`` is *past* ``due_at`` (negative if not yet due).

    ``None`` when the question was never scheduled (no ``due_at`` — e.g. a legacy row migrated
    in before its first Phase-6 attempt); callers treat that as "surface it".
    """
    due = parse_ts(due_at)
    if due is None:
        return None
    return (now - due).total_seconds() / 86400.0


def item_is_due(due_at: Optional[str], now: datetime) -> bool:
    """A question is due when it has no schedule yet or its ``due_at`` has arrived."""
    od = days_overdue(due_at, now)
    return True if od is None else od >= 0


def item_priority(due_at: Optional[str], now: datetime, lapses: int, ease: float) -> float:
    """Per-question ordering score (higher = study sooner).

    How overdue dominates; chronic lapses and a low ease (a *hard* item) add a nudge so shaky
    questions surface even when only mildly overdue. Never-scheduled rows get a small base so
    they don't sink below freshly-scheduled ones.
    """
    od = days_overdue(due_at, now)
    base = NEW_ITEM_PRIORITY if od is None else max(0.0, od)
    hard = max(0.0, INITIAL_EASE_REF - ease)
    return round(base + max(0, lapses) * ITEM_LAPSE_WEIGHT + hard, 3)


# Mirror SM-2's starting ease without importing the scheduler at module load (keeps this pure
# module free of cross-module import order concerns); kept in sync with scheduler.INITIAL_EASE.
INITIAL_EASE_REF = 2.5


def sr_plan_items(
    now: Optional[datetime] = None, *, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Every question with SM-2 state, as plan-ready items ranked due-first then by priority.

    One row per ``question_mastery`` entry (each is a question you've answered at least once).
    The pure :func:`app.study.planner.build_study_plan` consumes these to pack a session.
    """
    now = now or now_utc()
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT notebook_id, quiz_artifact_id, question_key,
                   miss_count, ease, interval_days, reps, lapses, due_at, last_review_at
            FROM question_mastery
            -- Exclude course-namespaced SR rows from the cross-notebook study plan (courses are
            -- reviewed from their own page in M2; interleaving them is M3). See COURSE_NB_PREFIX.
            WHERE notebook_id NOT LIKE 'course:%'
            """
        ).fetchall()
    finally:
        conn.close()

    out: List[Dict[str, Any]] = []
    for r in rows:
        od = days_overdue(r["due_at"], now)
        out.append(
            {
                "notebook_id": r["notebook_id"],
                "quiz_artifact_id": r["quiz_artifact_id"],
                "question_key": r["question_key"],
                "due": item_is_due(r["due_at"], now),
                "days_overdue": None if od is None else round(od, 2),
                "priority": item_priority(r["due_at"], now, int(r["lapses"] or 0), float(r["ease"] or INITIAL_EASE_REF)),
                "ease": round(float(r["ease"] or INITIAL_EASE_REF), 3),
                "reps": int(r["reps"] or 0),
                "lapses": int(r["lapses"] or 0),
                "interval_days": round(float(r["interval_days"] or 0.0), 3),
                "miss_count": int(r["miss_count"] or 0),
                "due_at": r["due_at"],
            }
        )

    out.sort(
        key=lambda it: (
            not it["due"],
            -it["priority"],
            -((it["days_overdue"] or 0.0)),
            it["notebook_id"],
            it["quiz_artifact_id"],
            it["question_key"],
        )
    )
    return out


def due_topic_ids(
    now: Optional[datetime] = None,
    *,
    half_life: float = HALF_LIFE_DAYS,
    threshold: float = DUE_THRESHOLD,
    db_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """``notebook_id → {mastery(decayed), due, last_review_at}`` for every practiced topic.

    Powers the home catalog badge + card mastery chip. Returns *all* practiced topics (not just
    due ones) so the card can show a decayed-mastery signal even when a topic isn't yet due.
    """
    return {
        item["notebook_id"]: {
            "mastery": item["decayed"],
            "due": item["due"],
            "last_review_at": item["last_review_at"],
        }
        for item in review_queue(now, half_life=half_life, threshold=threshold, db_path=db_path)
    }
