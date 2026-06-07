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
