"""CLI for the hub's **custom topics** — non-NotebookLM interests (a book, a YouTube series, a
loose thread) tracked loosely with manual progress + notes. This is the first writer for the
Phase-5 ``custom_topics`` table.

Used by the ``youtube-breakdown`` skill to register a processed video as a hub topic, and
usable directly. Like the ``/episode-review`` CLI it speaks JSON on stdout so a skill can parse
it; like all hub state, everything it writes lives in the hub's SQLite store — never in the
NotebookLM sidecars.

Subcommands (all speak JSON on stdout):
  add     --title T [--notes TEXT | --notes-file PATH] [--progress N]   -> the new topic
  list                                                                  -> [topic, ...]
  update  --id ID [--title T] [--notes TEXT | --notes-file PATH] [--progress N]  -> the topic
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..store import add_custom_topic, init_db, list_custom_topics, update_custom_topic


def _resolve_notes(notes: Optional[str], notes_file: Optional[str]) -> Optional[str]:
    """``--notes-file`` wins when given (FileNotFoundError if missing); else the inline
    ``--notes``; else ``None`` (meaning "leave unchanged" on update / "empty" on add)."""
    if notes_file is not None:
        return Path(notes_file).read_text(encoding="utf-8")
    return notes


# -- add -----------------------------------------------------------------------

def cmd_add(
    title: str,
    *,
    notes: Optional[str] = None,
    notes_file: Optional[str] = None,
    progress: int = 0,
) -> Dict[str, Any]:
    return add_custom_topic(
        title, notes=_resolve_notes(notes, notes_file) or "", progress_pct=progress
    )


# -- list ----------------------------------------------------------------------

def cmd_list() -> List[Dict[str, Any]]:
    return list_custom_topics()


# -- update --------------------------------------------------------------------

def cmd_update(
    topic_id: int,
    *,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    notes_file: Optional[str] = None,
    progress: Optional[int] = None,
) -> Dict[str, Any]:
    updated = update_custom_topic(
        topic_id,
        title=title,
        notes=_resolve_notes(notes, notes_file),
        progress_pct=progress,
    )
    if updated is None:
        raise LookupError(f"No custom topic with id {topic_id}")
    return updated


# -- CLI plumbing --------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="custom-topics", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="create a custom topic")
    pa.add_argument("--title", required=True)
    grp_a = pa.add_mutually_exclusive_group()
    grp_a.add_argument("--notes", default=None, help="inline notes body")
    grp_a.add_argument("--notes-file", default=None, help="read the notes body from a file")
    pa.add_argument("--progress", type=int, default=0, help="0-100 (default 0)")

    sub.add_parser("list", help="list all custom topics (most-recently-updated first)")

    pu = sub.add_parser("update", help="patch a custom topic's fields")
    pu.add_argument("--id", type=int, required=True)
    pu.add_argument("--title", default=None)
    grp_u = pu.add_mutually_exclusive_group()
    grp_u.add_argument("--notes", default=None, help="inline notes body")
    grp_u.add_argument("--notes-file", default=None, help="read the notes body from a file")
    pu.add_argument("--progress", type=int, default=None, help="0-100")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    init_db()  # idempotent; guarantees the tables exist before any write
    try:
        if args.cmd == "add":
            out: Any = cmd_add(
                args.title, notes=args.notes, notes_file=args.notes_file, progress=args.progress
            )
        elif args.cmd == "list":
            out = cmd_list()
        else:  # update
            out = cmd_update(
                args.id,
                title=args.title,
                notes=args.notes,
                notes_file=args.notes_file,
                progress=args.progress,
            )
    except (ValueError, LookupError, FileNotFoundError) as e:
        # Friendly, machine-readable failure for the skill to surface.
        print(json.dumps({"error": str(e), "kind": type(e).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
