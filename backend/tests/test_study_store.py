"""app.store.study_blocks — the Study Scheduler's opt-in flag + removable block ledger (v0).

Content-on-disk / progress-in-SQLite, same split as ``path_step_progress``: the path sidecar is
read-only; the per-track opt-in and the calendar blocks the scheduler wrote live here. Every block
records its Google ``event_id`` + ``calendar_id`` so it is cleanly removable — the one hard rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.store import study_blocks


@pytest.fixture
def store(tmp_path: Path) -> Path:
    from app.store import db

    p = tmp_path / "t.sqlite"
    db.init_db(p)
    return p


def _block(step_id: str, event_id: str, start_at: str, end_at: str) -> dict:
    return {
        "step_id": step_id,
        "calendar_id": "cal-study",
        "event_id": event_id,
        "title": f"Study · {step_id}",
        "start_at": start_at,
        "end_at": end_at,
    }


def test_opt_in_defaults_off_and_roundtrips(store: Path) -> None:
    # No row yet → opted out at the default session length.
    assert study_blocks.get_study_opt_in("path", "nb-1", db_path=store) == {
        "enabled": False,
        "session_minutes": 45,
    }
    study_blocks.set_study_opt_in("path", "nb-1", True, 30, db_path=store)
    assert study_blocks.get_study_opt_in("path", "nb-1", db_path=store) == {
        "enabled": True,
        "session_minutes": 30,
    }
    # Toggling again upserts (no duplicate row) and another track stays independent.
    study_blocks.set_study_opt_in("path", "nb-1", False, 60, db_path=store)
    assert study_blocks.get_study_opt_in("path", "nb-1", db_path=store) == {
        "enabled": False,
        "session_minutes": 60,
    }
    assert study_blocks.get_study_opt_in("path", "nb-2", db_path=store)["enabled"] is False


def test_add_and_list_blocks_live_only_ordered(store: Path) -> None:
    added = study_blocks.add_study_blocks(
        "path",
        "nb-1",
        [
            _block("quiz", "ev-b", "2026-07-23T18:00:00-05:00", "2026-07-23T18:45:00-05:00"),
            _block("ep1", "ev-a", "2026-07-22T18:00:00-05:00", "2026-07-22T18:45:00-05:00"),
        ],
        db_path=store,
    )
    assert {b["event_id"] for b in added} == {"ev-a", "ev-b"}
    assert all(isinstance(b["id"], int) and b["status"] == "written" for b in added)

    live = study_blocks.list_study_blocks("path", "nb-1", db_path=store)
    # Ordered by start_at so the UI + reconcile read chronologically.
    assert [b["event_id"] for b in live] == ["ev-a", "ev-b"]
    # A different track's ledger is independent.
    assert study_blocks.list_study_blocks("path", "nb-2", db_path=store) == []


def test_mark_blocks_removed_hides_from_live_but_keeps_ledger(store: Path) -> None:
    added = study_blocks.add_study_blocks(
        "path",
        "nb-1",
        [
            _block("ep1", "ev-a", "2026-07-22T18:00:00-05:00", "2026-07-22T18:45:00-05:00"),
            _block("quiz", "ev-b", "2026-07-23T18:00:00-05:00", "2026-07-23T18:45:00-05:00"),
        ],
        db_path=store,
    )
    n = study_blocks.mark_study_blocks_removed("path", "nb-1", [added[0]["id"]], db_path=store)
    assert n == 1

    live = study_blocks.list_study_blocks("path", "nb-1", db_path=store)
    assert [b["event_id"] for b in live] == ["ev-b"]

    # The removed row is still in the ledger (audit) — status flipped, removed_at stamped.
    everything = study_blocks.list_study_blocks(
        "path", "nb-1", include_removed=True, db_path=store
    )
    removed = [b for b in everything if b["event_id"] == "ev-a"][0]
    assert removed["status"] == "removed"
    assert removed["removed_at"]

    # Removing an already-removed id is a no-op (nothing live to flip).
    assert study_blocks.mark_study_blocks_removed("path", "nb-1", [added[0]["id"]], db_path=store) == 0


def test_mark_all_removed_when_no_ids_given(store: Path) -> None:
    study_blocks.add_study_blocks(
        "path",
        "nb-1",
        [
            _block("ep1", "ev-a", "2026-07-22T18:00:00-05:00", "2026-07-22T18:45:00-05:00"),
            _block("quiz", "ev-b", "2026-07-23T18:00:00-05:00", "2026-07-23T18:45:00-05:00"),
        ],
        db_path=store,
    )
    assert study_blocks.mark_study_blocks_removed("path", "nb-1", db_path=store) == 2
    assert study_blocks.list_study_blocks("path", "nb-1", db_path=store) == []
