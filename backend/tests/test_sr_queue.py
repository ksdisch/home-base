"""Phase-6 per-item SR queue (`mastery.sr_plan_items`) over the store.

Drives `record_attempt` with an injected clock so each question's `due_at` is deterministic, then
asserts the queue's due/priority behavior — no time-travel, no real data.
"""

from __future__ import annotations

from datetime import datetime

from app.store import mastery as m
from app.store.db import init_db, record_attempt

OLD = datetime(2026, 1, 1, 12, 0, 0)   # attempts taken here → due_at in early Jan
NOW = datetime(2026, 6, 1, 12, 0, 0)   # ...long past due by now


def _answers(*specs):
    """specs: (question_key, correct, used_hint) tuples → record_attempt answer rows."""
    rows = []
    for i, (key, correct, hint) in enumerate(specs):
        rows.append(
            {
                "question_index": i,
                "question_key": key,
                "chosen_index": 0,
                "correct": correct,
                "used_hint": hint,
            }
        )
    return rows


def test_empty_store_has_no_items(tmp_path):
    db = tmp_path / "empty.sqlite"
    init_db(db)
    assert m.sr_plan_items(NOW, db_path=db) == []


def test_old_attempts_are_due_now_and_fresh_ones_are_not(tmp_path):
    db = tmp_path / "due.sqlite"
    init_db(db)
    # An old clean pass → scheduled 1 day after OLD → long overdue by NOW.
    record_attempt(
        "nb-old", "qz", score=1, total=1,
        answers=_answers(("k-old", True, False)), now=OLD, db_path=db,
    )
    # A fresh clean pass at NOW → due_at = NOW + 1 day → not yet due.
    record_attempt(
        "nb-fresh", "qz", score=1, total=1,
        answers=_answers(("k-fresh", True, False)), now=NOW, db_path=db,
    )

    items = m.sr_plan_items(NOW, db_path=db)
    by_key = {it["question_key"]: it for it in items}
    assert by_key["k-old"]["due"] is True
    assert by_key["k-old"]["days_overdue"] > 0
    assert by_key["k-fresh"]["due"] is False
    # Due items sort ahead of not-due.
    assert items[0]["question_key"] == "k-old"


def test_lapsed_question_outranks_a_clean_one_at_equal_age(tmp_path):
    db = tmp_path / "rank.sqlite"
    init_db(db)
    record_attempt(
        "nb-clean", "qz", score=1, total=1,
        answers=_answers(("k-clean", True, False)), now=OLD, db_path=db,
    )
    record_attempt(
        "nb-shaky", "qz", score=0, total=1,
        answers=_answers(("k-shaky", False, False)), now=OLD, db_path=db,
    )
    items = m.sr_plan_items(NOW, db_path=db)
    order = [it["question_key"] for it in items]
    shaky = next(it for it in items if it["question_key"] == "k-shaky")
    clean = next(it for it in items if it["question_key"] == "k-clean")
    # The missed question carries a lapse + lower ease → higher priority.
    assert shaky["lapses"] == 1
    assert shaky["priority"] > clean["priority"]
    assert order.index("k-shaky") < order.index("k-clean")
