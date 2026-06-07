"""Phase-6 study planner — pure budget/interleave logic over ranked items."""

from __future__ import annotations

from app.study import planner as p


def _item(nb, qz, key, *, due=True, priority=10.0):
    return {
        "notebook_id": nb,
        "quiz_artifact_id": qz,
        "question_key": key,
        "due": due,
        "priority": priority,
    }


# 40s/item → 1.5 items/min. A 4-minute budget holds 6 items exactly.
PER_MIN = 60.0 / p.SECONDS_PER_ITEM


def test_empty_items_yields_empty_plan():
    plan = p.build_study_plan([], minutes=20)
    assert plan["total_items"] == 0
    assert plan["segments"] == []
    assert plan["has_due"] is False


def test_budget_is_respected():
    items = [_item("nb", "qz", f"k{i}") for i in range(50)]
    plan = p.build_study_plan(items, minutes=4)  # room for 6 items
    assert plan["total_items"] == int(4 * PER_MIN)
    assert plan["total_minutes"] <= 4 + 1e-9


def test_plan_is_never_empty_when_budget_and_items_exist():
    # One pricey item vs a tiny budget: still surface the single top item.
    plan = p.build_study_plan([_item("nb", "qz", "k0")], minutes=1, seconds_per_item=600)
    assert plan["total_items"] == 1


def test_due_items_are_selected_before_not_due():
    # 4 not-due (high priority) + 4 due (lower priority); budget of 2 items must still pick due.
    not_due = [_item("nb", "qz", f"n{i}", due=False, priority=99.0) for i in range(4)]
    due = [_item("nb", "qz", f"d{i}", due=True, priority=1.0) for i in range(4)]
    # Caller passes already due-first-sorted items (sr_plan_items guarantees this).
    ordered = due + not_due
    plan = p.build_study_plan(ordered, minutes=2)  # ~3 items
    assert plan["due_items"] == plan["total_items"]
    assert plan["has_due"] is True


def test_segments_group_by_quiz():
    items = [
        _item("nb1", "qzA", "a1"),
        _item("nb1", "qzA", "a2"),
        _item("nb1", "qzB", "b1"),
    ]
    plan = p.build_study_plan(items, minutes=60)
    by_quiz = {(s["notebook_id"], s["quiz_artifact_id"]): s for s in plan["segments"]}
    assert by_quiz[("nb1", "qzA")]["item_count"] == 2
    assert by_quiz[("nb1", "qzB")]["item_count"] == 1


def test_segments_interleave_across_notebooks():
    # Three notebooks, one quiz each, all due. No two consecutive segments share a notebook.
    items = [_item(f"nb{n}", f"qz{n}", f"k{n}", priority=float(10 - n)) for n in range(3)]
    plan = p.build_study_plan(items, minutes=60)
    nbs = [s["notebook_id"] for s in plan["segments"]]
    assert len(nbs) == 3
    assert all(nbs[i] != nbs[i + 1] for i in range(len(nbs) - 1))


def test_clamp_minutes_bounds():
    assert p.clamp_minutes(0) == p.MIN_MINUTES
    assert p.clamp_minutes(9999) == p.MAX_MINUTES
    assert p.clamp_minutes(20) == 20
