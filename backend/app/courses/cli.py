"""JSON-speaking CLI bridge for **courses** — the seam the ``course-builder`` skill /
``/build-course`` command call to scaffold a course dir and validate generated output before
the hub reads it. Like ``app.topics.custom`` it prints JSON on stdout and follows the repo's
``cd backend && .venv/bin/python -m app.courses.cli <cmd>`` convention.

Subcommands (all JSON on stdout):
  list                                              -> [course summary, ...]
  validate  --path DIR                              -> {ok, errors, warnings, ...counts}
  scaffold  --slug S --title T [--topic ..] [--level ..] [--summary ..]  -> {path, slug}

Authoring the actual lessons/diagrams/flashcards/quizzes is Claude's job (it writes the files);
this bridge only scaffolds the skeleton and checks well-formedness. It writes only under the
configured ``COURSES_DIR`` — never the bundled examples, never a NotebookLM sidecar."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_settings
from .manifest import CourseError, list_courses, validate_dir

_VALID_LEVELS = ("beginner", "intermediate", "advanced")


def cmd_list() -> List[Dict[str, Any]]:
    return list_courses()


def cmd_validate(path: str) -> Dict[str, Any]:
    return validate_dir(Path(path).expanduser())


def cmd_scaffold(
    slug: str,
    title: str,
    *,
    topic: str = "",
    level: str = "beginner",
    summary: str = "",
) -> Dict[str, Any]:
    slug = slug.strip()
    if not slug or "/" in slug or slug.startswith("."):
        raise ValueError("slug must be a simple directory name (no '/' or leading '.')")
    if not title.strip():
        raise ValueError("title must be non-empty")
    if level not in _VALID_LEVELS:
        raise ValueError(f"level must be one of {_VALID_LEVELS}")

    base = get_settings().courses_dir / slug
    if (base / "course.json").exists():
        raise FileExistsError(f"course '{slug}' already exists at {base}")
    for sub in ("lessons", "diagrams", "flashcards", "quizzes"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    manifest = {
        "slug": slug,
        "title": title.strip(),
        "topic": topic,
        "level": level,
        "summary": summary,
        "estimated_hours": None,
        "created_at": "",
        "generator": "course-builder v1",
        "modules": [],
    }
    (base / "course.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"path": str(base), "slug": slug, "manifest": "course.json"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="courses", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all discovered course summaries")

    pv = sub.add_parser("validate", help="validate a course dir end-to-end")
    pv.add_argument("--path", required=True, help="path to the course directory")

    ps = sub.add_parser("scaffold", help="create an empty course dir under COURSES_DIR")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--title", required=True)
    ps.add_argument("--topic", default="")
    ps.add_argument("--level", default="beginner", choices=_VALID_LEVELS)
    ps.add_argument("--summary", default="")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "list":
            out: Any = cmd_list()
        elif args.cmd == "validate":
            out = cmd_validate(args.path)
        else:  # scaffold
            out = cmd_scaffold(
                args.slug,
                args.title,
                topic=args.topic,
                level=args.level,
                summary=args.summary,
            )
    except (ValueError, CourseError, FileExistsError, FileNotFoundError) as e:
        print(json.dumps({"error": str(e), "kind": type(e).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
