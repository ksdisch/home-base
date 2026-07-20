"""Overnight Chief of Staff v0 — the draft-only queue's serve side.

``sweeps/actions_queue.py`` appends proposal rows to ``<data_dir>/overnight.jsonl``
after each sweep; the approve/discard endpoints append status rows. This module is the
reduce over that append-only event log: first proposal per id wins (a forced redraft can
never double the queue), a status row resolves a proposal exactly once, and anything
malformed is skipped, never fatal — a junk line or a missing file is just a quieter
morning. Scope decisions from the 2026-07-20 gate conversation
(docs/ideas/overnight-chief-of-staff.md): in-repo data only, v0 sends/executes nothing,
approve is the one real write (a note through the existing notes path), undo = discard.
The queue rides the LIVE ``GET /api/brief`` only — an archived ``?date=`` morning is a
record, not a to-do list.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_RESOLUTIONS = ("approved", "discarded")
_PROPOSAL_FIELDS = ("id", "date", "slug", "item_id", "item_headline", "body")


def _read_rows(path: Path) -> List[Dict[str, Any]]:
    """Every well-formed row in overnight.jsonl, in file order — a junk line is
    skipped, never fatal, and the file not existing yet is just an empty queue."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _valid_proposal(row: Dict[str, Any]) -> bool:
    if row.get("kind") != "proposal" or row.get("type") != "draft_note":
        return False
    return all(isinstance(row.get(f), str) and row[f].strip() for f in _PROPOSAL_FIELDS)


def load_queue(ledger_path: Path) -> Dict[str, Dict[str, Any]]:
    """id → proposal with its current resolution, insertion-ordered.

    First proposal per id wins; a status row applies only to a known, still-``proposed``
    id (resolution is single-shot — later or junk statuses can't flip a resolved row)."""
    queue: Dict[str, Dict[str, Any]] = {}
    for row in _read_rows(ledger_path):
        if _valid_proposal(row) and row["id"] not in queue:
            queue[row["id"]] = {
                "id": row["id"],
                "date": row["date"],
                "type": "draft_note",
                "slug": row["slug"],
                "item_id": row["item_id"],
                "item_headline": row["item_headline"],
                "body": row["body"],
                "status": "proposed",
                "note_id": None,
                "created_at": str(row.get("created_at") or ""),
            }
        elif row.get("kind") == "status":
            target = queue.get(row.get("id"))
            status = row.get("status")
            if target is None or target["status"] != "proposed" or status not in _RESOLUTIONS:
                continue
            target["status"] = status
            note_id = row.get("note_id")
            target["note_id"] = note_id if isinstance(note_id, int) else None
    return queue


def build_overnight(ledger_path: Path, date: str, titles: Dict[str, str]) -> Dict[str, Any]:
    """The served day's queue for the live brief payload — every proposal drafted for
    ``date`` with its resolution (the page hides discarded ones; they stay in the
    payload because the queue is an after-action record, not just a to-do list)."""
    proposals = [
        {**p, "title": titles.get(p["slug"], p["slug"])}
        for p in load_queue(ledger_path).values()
        if p["date"] == date
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "proposals": proposals,
    }


def append_status(ledger_path: Path, proposal_id: str, status: str, note_id: int | None = None) -> None:
    """One resolution row — the approve/discard endpoints' only write to the ledger."""
    row: Dict[str, Any] = {
        "kind": "status",
        "id": proposal_id,
        "status": status,
        "note_id": note_id,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
