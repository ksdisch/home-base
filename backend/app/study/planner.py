"""Phase-6 daily study plan — pure, deterministic session builder.

Phase 4's queue is an unbounded ranked list; this turns it into "what do I do *right now* for
20 minutes": pack the highest-priority **due** questions into a time budget, then interleave the
resulting per-quiz segments so the same topic isn't back-to-back (interleaving is one of the
best-evidenced study techniques, and the topic-grouped queue otherwise blocks on one topic).

Pure by design — no DB, no clock. It takes already-ranked items (from
:func:`app.store.mastery.sr_plan_items`) and a minute budget, so every property (budget
respected, due-first, interleaved) is deterministic to assert.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

SECONDS_PER_ITEM = 40.0   # rough cost of reviewing one question
DEFAULT_MINUTES = 20
MIN_MINUTES = 5
MAX_MINUTES = 120


def clamp_minutes(minutes: int) -> int:
    """Keep a requested budget within sane bounds (defends the endpoint's query param)."""
    return max(MIN_MINUTES, min(MAX_MINUTES, int(minutes)))


def _select(items: List[Mapping[str, Any]], budget: float, per_item: float) -> List[Mapping[str, Any]]:
    """Greedily take items (already ranked due-first) until the next won't fit the budget.

    All items cost the same, so once one doesn't fit, none do. If nothing fits but there's any
    budget and any item, take the single top item so the plan is never empty for a willing user.
    """
    selected: List[Mapping[str, Any]] = []
    total = 0.0
    for it in items:
        if total + per_item <= budget + 1e-9:
            selected.append(it)
            total += per_item
        else:
            break
    if not selected and items and budget > 0:
        selected = [items[0]]
    return selected


def _interleave(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order segments by priority but avoid two consecutive from the same notebook where possible."""
    remaining = sorted(
        segments,
        key=lambda s: (-s["priority"], s["notebook_id"], s["quiz_artifact_id"]),
    )
    out: List[Dict[str, Any]] = []
    last_nb = None
    while remaining:
        pick_idx = next(
            (i for i, s in enumerate(remaining) if s["notebook_id"] != last_nb), 0
        )
        pick = remaining.pop(pick_idx)
        out.append(pick)
        last_nb = pick["notebook_id"]
    return out


def build_study_plan(
    items: List[Mapping[str, Any]],
    *,
    minutes: int,
    seconds_per_item: float = SECONDS_PER_ITEM,
) -> Dict[str, Any]:
    """Build a time-boxed, interleaved review session from ranked per-question items.

    ``items`` are dicts with at least ``notebook_id``, ``quiz_artifact_id``, ``question_key``,
    ``due`` (bool), ``priority`` (float) — i.e. the output of ``mastery.sr_plan_items`` (assumed
    already sorted due-first). Returns a plan with per-quiz segments to retake.
    """
    per_item = seconds_per_item / 60.0
    budget = max(0.0, float(minutes))
    selected = _select(list(items), budget, per_item)

    # Group selected questions into one segment per quiz (the actionable unit: retake that quiz).
    segs: Dict[tuple, Dict[str, Any]] = {}
    order: List[tuple] = []
    for it in selected:
        key = (it["notebook_id"], it["quiz_artifact_id"])
        seg = segs.get(key)
        if seg is None:
            seg = segs[key] = {
                "notebook_id": it["notebook_id"],
                "quiz_artifact_id": it["quiz_artifact_id"],
                "item_count": 0,
                "due_count": 0,
                "priority": 0.0,
            }
            order.append(key)
        seg["item_count"] += 1
        if it.get("due"):
            seg["due_count"] += 1
        seg["priority"] = max(seg["priority"], float(it.get("priority", 0.0)))

    seg_list = [segs[k] for k in order]
    for seg in seg_list:
        seg["minutes"] = round(seg["item_count"] * per_item, 1)
    ordered = _interleave(seg_list)

    return {
        "requested_minutes": int(minutes),
        "total_minutes": round(len(selected) * per_item, 1),
        "total_items": len(selected),
        "due_items": sum(1 for it in selected if it.get("due")),
        "segment_count": len(ordered),
        "has_due": any(s["due_count"] > 0 for s in ordered),
        "segments": ordered,
    }
