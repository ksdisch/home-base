"""JSON-speaking CLI bridge for **courses** — the seam the ``course-builder`` skill /
``/build-course`` command call to scaffold a course dir and validate generated output before
the hub reads it. Like ``app.topics.custom`` it prints JSON on stdout and follows the repo's
``cd backend && .venv/bin/python -m app.courses.cli <cmd>`` convention.

Subcommands (all JSON on stdout):
  list                                              -> [course summary, ...]
  validate  --path DIR                              -> {ok, slug, errors, warnings, ...counts}
  write     --slug S [--from-file PATH]             -> {written, ok, errors, warnings, ...}
  scaffold  --slug S --title T [--topic ..] [--level ..] [--summary ..] [--estimated-hours N]

Authoring the actual lessons/diagrams/flashcards/quizzes is Claude's job (it writes the files);
this bridge only scaffolds the skeleton and checks well-formedness. It writes only under the
configured ``COURSES_DIR`` — never the bundled examples, never a NotebookLM sidecar."""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_settings
from .manifest import CourseError, list_courses, validate_dir

_VALID_LEVELS = ("beginner", "intermediate", "advanced")
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def _check_slug(slug: str) -> str:
    slug = slug.strip()
    if not _SLUG_RE.match(slug):
        raise ValueError("slug must be kebab-case: lowercase letters, digits, and '-' only")
    return slug


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
    estimated_hours: Optional[float] = None,
) -> Dict[str, Any]:
    slug = _check_slug(slug)
    if not title.strip():
        raise ValueError("title must be non-empty")
    if level not in _VALID_LEVELS:
        raise ValueError(f"level must be one of {_VALID_LEVELS}")

    base = get_settings().courses_dir / slug
    if (base / "course.json").exists():
        raise FileExistsError(f"course '{slug}' already exists at {base}")
    for sub in ("lessons", "exercises", "diagrams", "flashcards", "quizzes"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    manifest = {
        "slug": slug,
        "title": title.strip(),
        "topic": topic,
        "level": level,
        "summary": summary,
        "estimated_hours": estimated_hours,
        "created_at": datetime.date.today().isoformat(),
        "generator": "course-builder v1",
        "modules": [],
    }
    (base / "course.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"path": str(base), "slug": slug, "manifest": "course.json"}


def cmd_write(slug: str, manifest_file: Optional[str]) -> Dict[str, Any]:
    """Write a full ``course.json`` (from a file or stdin) under ``COURSES_DIR/<slug>/`` and
    validate it in one step. The manifest's ``slug`` is forced to ``<slug>`` (the dir is the
    source of identity). Returns the validate report + the path written, so the authoring loop is
    validated-by-construction instead of relying on a hand-edited, separately-checked file."""
    slug = _check_slug(slug)
    text = Path(manifest_file).read_text(encoding="utf-8") if manifest_file else sys.stdin.read()
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"manifest is not valid JSON: {e}")
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    manifest["slug"] = slug

    base = get_settings().courses_dir / slug
    base.mkdir(parents=True, exist_ok=True)
    (base / "course.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report = validate_dir(base)
    return {"written": str(base / "course.json"), **report}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="courses", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all discovered course summaries")

    pv = sub.add_parser("validate", help="validate a course dir end-to-end")
    pv.add_argument("--path", required=True, help="path to the course directory")

    pw = sub.add_parser("write", help="write course.json (from --from-file or stdin) + validate")
    pw.add_argument("--slug", required=True)
    pw.add_argument("--from-file", default=None, help="manifest JSON file (default: read stdin)")

    ps = sub.add_parser("scaffold", help="create an empty course dir under COURSES_DIR")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--title", required=True)
    ps.add_argument("--topic", default="")
    ps.add_argument("--level", default="beginner", choices=_VALID_LEVELS)
    ps.add_argument("--summary", default="")
    ps.add_argument("--estimated-hours", type=float, default=None)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "list":
            out: Any = cmd_list()
        elif args.cmd == "validate":
            out = cmd_validate(args.path)
        elif args.cmd == "write":
            out = cmd_write(args.slug, args.from_file)
        else:  # scaffold
            out = cmd_scaffold(
                args.slug,
                args.title,
                topic=args.topic,
                level=args.level,
                summary=args.summary,
                estimated_hours=args.estimated_hours,
            )
    except (ValueError, CourseError, FileExistsError, FileNotFoundError) as e:
        print(json.dumps({"error": str(e), "kind": type(e).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
