"""Read-only progress queries over the hub store — the Phase-3 "rich tracking" read layer.

Phase 2 (`record_attempt`) writes the signal; this module reads it back: per-topic score
trends, an activity streak, and the shakiest material. Pure SQL + a pure streak computation —
no decay, no ranking (that's Phase 4). Every function takes an optional ``db_path`` so tests
can point at a throwaway store.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .db import connect


def _pct(score: Optional[int], total: Optional[int]) -> float:
    """Score as a 0–100 percentage, rounded to 1dp. Zero/None total → 0.0 (never divide-by-zero)."""
    if not total:
        return 0.0
    return round(100.0 * (score or 0) / total, 1)


def compute_streaks(days: Iterable[str], today: date) -> tuple[int, int]:
    """Current + longest run of consecutive activity days.

    ``days`` are ``YYYY-MM-DD`` strings (any order, dupes ok). ``current`` only counts when the
    most recent day is ``today`` or yesterday — a streak that lapsed days ago isn't "current".
    Pure (takes ``today``) so it's deterministic to test without time-travel.
    """
    parsed = sorted({date.fromisoformat(d) for d in days if d})
    if not parsed:
        return (0, 0)

    longest = run = 1
    for prev, cur in zip(parsed, parsed[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        longest = max(longest, run)

    # Current streak: walk back from the latest day only if it's today/yesterday.
    latest = parsed[-1]
    if (today - latest).days > 1:
        return (0, longest)
    present = set(parsed)
    current = 0
    cursor = latest
    while cursor in present:
        current += 1
        cursor -= timedelta(days=1)
    return (current, longest)


def overall_summary(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Headline counters: attempts taken, distinct topics practiced, avg score %, last activity day."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)                         AS attempts_total,
                   COUNT(DISTINCT notebook_id)      AS topics_practiced,
                   COALESCE(SUM(score), 0)          AS sum_score,
                   COALESCE(SUM(total), 0)          AS sum_total
            FROM attempts
            WHERE finished_at IS NOT NULL
              -- Course attempts are namespaced 'course:<slug>' and excluded from the notebook
              -- progress headline (they're surfaced per-course). The activity streak below stays
              -- source-agnostic. See app.courses.COURSE_NB_PREFIX.
              AND notebook_id NOT LIKE 'course:%'
            """
        ).fetchone()
        last = conn.execute("SELECT MAX(day) AS d FROM activity").fetchone()
        return {
            "attempts_total": int(row["attempts_total"]),
            "topics_practiced": int(row["topics_practiced"]),
            "avg_pct": _pct(int(row["sum_score"]), int(row["sum_total"])),
            "last_activity": last["d"],
        }
    finally:
        conn.close()


def activity_days(db_path: Optional[Path] = None) -> List[str]:
    """Distinct days (ascending) that had any logged learning activity."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT day FROM activity WHERE day IS NOT NULL ORDER BY day"
        ).fetchall()
        return [r["day"] for r in rows]
    finally:
        conn.close()


def activity_counts(
    days_back: int, today: date, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """A dense per-day activity count for the last ``days_back`` days (oldest→newest).

    Dense (zero-filled) so the UI strip has one cell per calendar day, no gaps to special-case.
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT day, COUNT(*) AS n FROM activity WHERE day IS NOT NULL GROUP BY day"
        ).fetchall()
        counts = {r["day"]: int(r["n"]) for r in rows}
    finally:
        conn.close()
    out: List[Dict[str, Any]] = []
    for i in range(days_back - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append({"day": d, "count": counts.get(d, 0)})
    return out


def topic_breakdowns(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Per-notebook progress: attempt count, last/best/avg pct, last practiced, and the trend.

    ``points`` is every finished attempt (oldest→newest) as ``{finished_at, pct}`` — the series
    the sparkline draws. Ordered by most-recently-practiced topic first.
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT notebook_id, score, total, finished_at
            FROM attempts
            WHERE finished_at IS NOT NULL
              AND notebook_id NOT LIKE 'course:%'   -- per-notebook trends; courses excluded
            ORDER BY notebook_id, finished_at, id
            """
        ).fetchall()
    finally:
        conn.close()

    by_topic: Dict[str, List[Any]] = {}
    for r in rows:
        by_topic.setdefault(r["notebook_id"], []).append(r)

    out: List[Dict[str, Any]] = []
    for notebook_id, attempts in by_topic.items():
        pcts = [_pct(a["score"], a["total"]) for a in attempts]
        points = [
            {"finished_at": a["finished_at"], "pct": p} for a, p in zip(attempts, pcts)
        ]
        out.append(
            {
                "notebook_id": notebook_id,
                "attempts": len(attempts),
                "last_pct": pcts[-1],
                "best_pct": max(pcts),
                "avg_pct": round(sum(pcts) / len(pcts), 1),
                "last_practiced": attempts[-1]["finished_at"],
                "points": points,
            }
        )
    # Most recently practiced first.
    out.sort(key=lambda t: t["last_practiced"] or "", reverse=True)
    return out


def shaky_quizzes(limit: int = 8, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """The shakiest quizzes by accumulated misses, aggregated from ``question_mastery``.

    The question *text* isn't stored (the hub is read-only toward NotebookLM), so we report
    misses + how many distinct questions are shaky per quiz — enough to nudge a retake without
    inventing question prose. Only quizzes with at least one miss are returned, worst first.
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT notebook_id,
                   quiz_artifact_id,
                   SUM(miss_count)                         AS total_misses,
                   SUM(CASE WHEN miss_count > 0 THEN 1 END) AS shaky_questions,
                   MAX(last_review_at)                     AS last_review_at
            FROM question_mastery
            WHERE notebook_id NOT LIKE 'course:%'   -- per-notebook shaky quizzes; courses excluded
            GROUP BY notebook_id, quiz_artifact_id
            HAVING total_misses > 0
            ORDER BY total_misses DESC, last_review_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "notebook_id": r["notebook_id"],
                "quiz_artifact_id": r["quiz_artifact_id"],
                "total_misses": int(r["total_misses"]),
                "shaky_questions": int(r["shaky_questions"] or 0),
                "last_review_at": r["last_review_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()
