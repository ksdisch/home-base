"""app.store.db — learning-path coverage + confidence helpers (M8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.store import db


@pytest.fixture
def store(tmp_path: Path) -> Path:
    p = tmp_path / "t.sqlite"
    db.init_db(p)
    return p


def test_coverage_roundtrip_and_scoping(store: Path) -> None:
    assert db.get_path_progress("nb-1", db_path=store) == {}
    db.set_step_completed("nb-1", "s1", True, db_path=store)
    db.set_step_completed("nb-1", "s2", True, db_path=store)
    assert db.get_path_progress("nb-1", db_path=store) == {"s1": True, "s2": True}
    # unmarking flips just that step
    db.set_step_completed("nb-1", "s1", False, db_path=store)
    assert db.get_path_progress("nb-1", db_path=store) == {"s1": False, "s2": True}
    # another topic's coverage is independent
    assert db.get_path_progress("nb-2", db_path=store) == {}


def test_confidence_roundtrip_and_upsert(store: Path) -> None:
    assert db.get_path_confidence("nb-1", db_path=store) == {}
    db.set_step_confidence("nb-1", "s1", 3, db_path=store)
    assert db.get_path_confidence("nb-1", db_path=store) == {"s1": 3}
    db.set_step_confidence("nb-1", "s1", 5, db_path=store)  # re-rate upserts, not duplicates
    assert db.get_path_confidence("nb-1", db_path=store) == {"s1": 5}


def test_completing_a_step_logs_activity_crediting_the_topic(store: Path) -> None:
    db.set_step_completed("nb-9", "s1", True, db_path=store)
    conn = db.connect(store)
    try:
        rows = conn.execute(
            "SELECT notebook_id, kind FROM activity WHERE kind = 'path_step'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    # coverage of a topic IS activity for that topic — the row credits the real notebook_id
    # (unlike a course lesson, which logs NULL).
    assert rows[0]["notebook_id"] == "nb-9"
