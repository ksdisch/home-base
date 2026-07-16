"""Read + validate course sidecars from disk.

A course lives in a directory:

    <slug>/
      course.json            # manifest: metadata + syllabus structure + material index
      lessons/<id>.md        # written lessons (markdown)
      diagrams/<id>.mmd      # mermaid sources
      flashcards/<id>.json   # [{front, back}, ...]
      quizzes/<id>.json      # hub-shaped quiz (see docs/fixtures/sample-quiz.json)

Course dirs are discovered from the **union** of the bundled examples (shipped in this package,
so the feature works on a fresh clone / in cloud / in tests) and the user's ``COURSES_DIR``
(their generated courses; the user dir wins on a slug collision). Parsing is defensive: a
malformed course dir is skipped, never fatal — same posture as the NotebookLM sidecar parser.
This module is **read-only**; it never writes under a course dir."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_settings

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

# A course's quiz attempts + per-question SM-2 state live in the *shared* store tables under this
# synthetic ``notebook_id`` namespace, so the existing grader/scheduler need no course-specific
# path. Every notebook-facing aggregate filters ``notebook_id LIKE 'course:%'`` back out.
COURSE_NB_PREFIX = "course:"


def course_notebook_id(slug: str) -> str:
    """The synthetic ``notebook_id`` that namespaces a course's attempts/SR in the shared store."""
    return f"{COURSE_NB_PREFIX}{slug}"

_VALID_LEVELS = {"beginner", "intermediate", "advanced"}
# Module/lesson ids land in URLs (e.g. POST …/lessons/<id>/complete) and SQLite keys, so they
# must be URL-safe — a '/' or space silently makes a lesson un-completable.
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# Objectives should be *assessable*; these opening verbs name internal states you can't observe.
# Flagged as a warning so the pedagogy the skill preaches is backed by the validator.
_VAGUE_OBJECTIVE_VERBS = {
    "understand", "know", "learn", "appreciate", "grasp", "comprehend", "familiarize",
    "realize", "internalize",
}
# Material types backed by a file under the course dir (so `validate` checks the file exists).
# Unknown types are kept (forward-compatible) but the UI/loader treat them generically.
# M3 adds ``project``/``capstone`` — longer, rubric-assessable practice items (markdown, like
# ``exercise``); a capstone is the course-ending synthesis project.
_FILE_MATERIALS = {"lesson", "diagram", "flashcards", "quiz", "exercise", "project", "capstone"}
# Material types that may carry a ``rubric`` (a rubrics/<id>.json the learner self-assesses against).
_RUBRIC_MATERIALS = {"exercise", "project", "capstone"}
# Expected folder/extension per file-backed type (a soft convention; mismatch -> warning).
_PATH_CONVENTION = {
    "lesson": ("lessons/", ".md"),
    "exercise": ("exercises/", ".md"),
    "project": ("projects/", ".md"),
    "capstone": ("capstones/", ".md"),
    "diagram": ("diagrams/", ".mmd"),
    "flashcards": ("flashcards/", ".json"),
    "quiz": ("quizzes/", ".json"),
}


class CourseError(ValueError):
    """A course dir / manifest is malformed."""


def _opt_num(value: Any) -> Optional[float]:
    """A number for an optional float field (``estimated_hours``), else None (bools aren't numbers
    here). Keeps a stray string/list out of the field where it would 500 the pydantic response
    model instead of being caught at load time."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _opt_int(value: Any) -> Optional[int]:
    """Like ``_opt_num`` but rounds to an int for ``estimated_minutes`` (typed ``Optional[int]``),
    so a fractional float can't slip through to the model and 500."""
    num = _opt_num(value)
    return None if num is None else round(num)


def _str_list(value: Any) -> List[str]:
    """A list-of-strings for an optional list field, else []. Guards the per-character explosion
    when an author passes a bare string where a list is expected (e.g. ``objectives: "foo"``)."""
    return [str(v) for v in value] if isinstance(value, list) else []


# -- discovery -----------------------------------------------------------------

def _course_dirs() -> Dict[str, Path]:
    """slug -> dir, union of bundled examples + the user's COURSES_DIR (user wins)."""
    out: Dict[str, Path] = {}
    for base in (EXAMPLES_DIR, get_settings().courses_dir):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "course.json").is_file():
                out[child.name] = child  # later base (user) overrides earlier (examples)
    return out


def _dir_for(slug: str) -> Optional[Path]:
    return _course_dirs().get(slug)


# -- parsing + validation ------------------------------------------------------

def load_manifest(course_dir: Path) -> Dict[str, Any]:
    """Parse + validate ``<course_dir>/course.json``. Raises ``CourseError`` if malformed.

    Returns the manifest as a dict with the ``slug`` forced to the directory name (the dir is
    the source of truth for identity) and light normalization of optional fields."""
    path = course_dir / "course.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise CourseError(f"no course.json in {course_dir}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CourseError(f"invalid JSON/encoding in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise CourseError(f"{path}: top level must be an object")

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise CourseError(f"{path}: 'title' is required")

    level = raw.get("level", "beginner")
    if level not in _VALID_LEVELS:
        level = "beginner"

    modules = _validate_modules(raw.get("modules", []), path)

    return {
        "slug": course_dir.name,
        "title": title.strip(),
        "topic": raw.get("topic", "") or "",
        "level": level,
        "summary": raw.get("summary", "") or "",
        "prerequisites": _str_list(raw.get("prerequisites")),
        "estimated_hours": _opt_num(raw.get("estimated_hours")),
        "created_at": raw.get("created_at", "") or "",
        "generator": raw.get("generator", "") or "",
        "modules": modules,
    }


def _resolve_id(raw_id: Any, fallback: str, kind: str, path: Path) -> str:
    """An explicit id must be a URL-safe string (it lands in URLs + SQLite keys); a missing/blank
    one falls back to a generated id. A non-string or URL-unsafe id is a hard error so it can't
    pass `validate` and then 404 the complete endpoint or break progress."""
    if raw_id is None or (isinstance(raw_id, str) and not raw_id.strip()):
        return fallback
    if not isinstance(raw_id, str):
        raise CourseError(f"{path}: {kind} 'id' must be a string, got {type(raw_id).__name__}")
    rid = raw_id.strip()
    if not _ID_RE.match(rid):
        raise CourseError(f"{path}: {kind} id '{rid}' must be URL-safe ([A-Za-z0-9._-])")
    return rid


def _validate_modules(modules: Any, path: Path) -> List[Dict[str, Any]]:
    if not isinstance(modules, list):
        raise CourseError(f"{path}: 'modules' must be a list")
    out: List[Dict[str, Any]] = []
    seen_lessons: set[str] = set()
    seen_modules: set[str] = set()
    for mi, m in enumerate(modules):
        if not isinstance(m, dict):
            raise CourseError(f"{path}: module #{mi} must be an object")
        mid = _resolve_id(m.get("id"), f"m{mi + 1}", f"module #{mi}", path)
        if mid in seen_modules:
            raise CourseError(f"{path}: duplicate module id '{mid}'")
        seen_modules.add(mid)
        if not isinstance(m.get("title"), str) or not m["title"].strip():
            raise CourseError(f"{path}: module '{mid}' needs a title")
        lessons_raw = m.get("lessons", []) or []
        if not isinstance(lessons_raw, list):
            raise CourseError(f"{path}: module '{mid}' lessons must be a list")
        lessons: List[Dict[str, Any]] = []
        for li, lsn in enumerate(lessons_raw):
            if not isinstance(lsn, dict):
                raise CourseError(f"{path}: lesson #{li} in '{mid}' must be an object")
            lid = _resolve_id(lsn.get("id"), f"{mid}l{li + 1}", f"lesson #{li} in '{mid}'", path)
            if lid in seen_lessons:
                raise CourseError(f"{path}: duplicate lesson id '{lid}'")
            seen_lessons.add(lid)
            if not isinstance(lsn.get("title"), str) or not lsn["title"].strip():
                raise CourseError(f"{path}: lesson '{lid}' needs a title")
            lessons.append(
                {
                    "id": lid,
                    "title": lsn["title"].strip(),
                    "objectives": _str_list(lsn.get("objectives")),
                    "estimated_minutes": _opt_int(lsn.get("estimated_minutes")),
                    "materials": _validate_materials(lsn.get("materials", []), lid, path),
                }
            )
        out.append(
            {
                "id": mid,
                "title": m["title"].strip(),
                "summary": m.get("summary", "") or "",
                "lessons": lessons,
            }
        )
    return out


def _validate_materials(materials: Any, lesson_id: str, path: Path) -> List[Dict[str, Any]]:
    if not isinstance(materials, list):
        raise CourseError(f"{path}: materials for '{lesson_id}' must be a list")
    out: List[Dict[str, Any]] = []
    for material in materials:
        if not isinstance(material, dict):
            raise CourseError(f"{path}: a material in '{lesson_id}' must be an object")
        mtype = material.get("type")
        if not isinstance(mtype, str) or not mtype.strip():
            raise CourseError(f"{path}: a material in '{lesson_id}' needs a string 'type'")
        out.append(material)  # kept as-authored; file existence is checked lazily on read
    return out


# -- public read API -----------------------------------------------------------

def _counts(manifest: Dict[str, Any]) -> Dict[str, Any]:
    lessons = [lsn for m in manifest["modules"] for lsn in m["lessons"]]
    material_counts: Dict[str, int] = {}
    for lsn in lessons:
        for material in lsn["materials"]:
            material_counts[material["type"]] = material_counts.get(material["type"], 0) + 1
    return {
        "module_count": len(manifest["modules"]),
        "lesson_count": len(lessons),
        "material_counts": material_counts,
    }


def _summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "slug": manifest["slug"],
        "title": manifest["title"],
        "topic": manifest["topic"],
        "level": manifest["level"],
        "summary": manifest["summary"],
        "prerequisites": manifest["prerequisites"],
        "estimated_hours": manifest["estimated_hours"],
        "created_at": manifest["created_at"],
        "generator": manifest["generator"],
        **_counts(manifest),
    }


def list_courses() -> List[Dict[str, Any]]:
    """Summaries for every well-formed course dir (malformed dirs are skipped)."""
    out: List[Dict[str, Any]] = []
    for course_dir in _course_dirs().values():
        try:
            out.append(_summary(load_manifest(course_dir)))
        except CourseError:
            continue  # skip the bad one; don't take down the whole list
    out.sort(key=lambda c: c["title"].lower())
    return out


def get_course(slug: str) -> Optional[Dict[str, Any]]:
    """Full structure for one course (no progress — the API merges that in). ``None`` if the
    slug doesn't resolve; raises ``CourseError`` only if the dir exists but is malformed."""
    course_dir = _dir_for(slug)
    if course_dir is None:
        return None
    manifest = load_manifest(course_dir)
    return {**manifest, **_counts(manifest)}


def material_path(slug: str, rel_path: str) -> Path:
    """Resolve a material file to an absolute ``Path``, confined to the course dir (rejects
    ``../`` traversal). For callers that need the file itself — e.g. the quiz session's
    ``from_file``. Raises ``CourseError`` for a missing course / an escaping path / no such file."""
    course_dir = _dir_for(slug)
    if course_dir is None:
        raise CourseError(f"no course '{slug}'")
    base = course_dir.resolve()
    target = (base / rel_path).resolve()
    if base != target and base not in target.parents:
        raise CourseError("material path escapes the course directory")
    if not target.is_file():
        raise CourseError(f"no such material: {rel_path}")
    return target


def read_material(slug: str, rel_path: str) -> Dict[str, Any]:
    """Return one material file's content. Markdown/mermaid come back as ``text``; JSON
    (flashcards/quizzes) as parsed ``data``. The path is confined to the course dir to reject
    traversal (``../``). Raises ``CourseError`` for a missing course / escaping / unreadable
    path."""
    target = material_path(slug, rel_path)
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise CourseError(f"unreadable material {rel_path}: {e}") from e
    if target.suffix == ".json":
        try:
            return {"path": rel_path, "kind": "json", "data": json.loads(text)}
        except json.JSONDecodeError as e:
            raise CourseError(f"invalid JSON in {rel_path}: {e}") from e
    return {"path": rel_path, "kind": "text", "text": text}


def _validate_quiz_file(path: Path) -> List[str]:
    """A course quiz must match the hub quiz shape *and* the grader's invariant: exactly one
    correct option per question, with a rationale on every option. ``validate`` checking this is
    what makes the skill's 'one correct answer' promise real."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        return [f"{path.name}: invalid JSON ({e})"]
    qs = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or not qs:
        return [f"{path.name}: must be an object with a non-empty 'questions' list"]
    errors: List[str] = []
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict) or not str(q.get("question", "")).strip():
            errors.append(f"{path.name} Q{i}: missing 'question' text")
            continue
        opts = q.get("answerOptions")
        if not isinstance(opts, list) or len(opts) < 2:
            errors.append(f"{path.name} Q{i}: needs >=2 'answerOptions'")
            continue
        n_correct = sum(1 for o in opts if isinstance(o, dict) and o.get("isCorrect") is True)
        if n_correct != 1:
            errors.append(
                f"{path.name} Q{i}: exactly one option must have isCorrect:true (found {n_correct})"
            )
        if any(not (isinstance(o, dict) and str(o.get("rationale", "")).strip()) for o in opts):
            errors.append(f"{path.name} Q{i}: every option needs a non-empty 'rationale'")
    return errors


def _validate_flashcards_file(path: Path) -> List[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        return [f"{path.name}: invalid JSON ({e})"]
    if not isinstance(data, list) or not data:
        return [f"{path.name}: must be a non-empty JSON array of {{front, back}}"]
    errors: List[str] = []
    for i, c in enumerate(data, 1):
        if not isinstance(c, dict) or not str(c.get("front", "")).strip() or not str(
            c.get("back", "")
        ).strip():
            errors.append(f"{path.name} card {i}: needs non-empty 'front' and 'back'")
    return errors


def _validate_rubric_file(path: Path) -> List[str]:
    """A rubric is ``{criteria: [{name, levels: [{label, description}, ...]}]}``. Each criterion
    needs a name and >=2 levels; each level a label + description. ``validate`` enforcing this is
    what makes the skill's 'self-assessable project/capstone' promise real — the hub renders these
    levels as the self-assessment choices."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        return [f"{path.name}: invalid JSON ({e})"]
    crits = data.get("criteria") if isinstance(data, dict) else None
    if not isinstance(crits, list) or not crits:
        return [f"{path.name}: must be an object with a non-empty 'criteria' list"]
    errors: List[str] = []
    for i, c in enumerate(crits, 1):
        if not isinstance(c, dict) or not str(c.get("name", "")).strip():
            errors.append(f"{path.name} criterion {i}: needs a non-empty 'name'")
            continue
        levels = c.get("levels")
        if not isinstance(levels, list) or len(levels) < 2:
            errors.append(f"{path.name} criterion {i}: needs >=2 'levels'")
            continue
        if any(
            not (
                isinstance(lv, dict)
                and str(lv.get("label", "")).strip()
                and str(lv.get("description", "")).strip()
            )
            for lv in levels
        ):
            errors.append(
                f"{path.name} criterion {i}: every level needs a 'label' and 'description'"
            )
    return errors


def _json_len(path: Path) -> Optional[int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        return len(data["questions"])
    return None


def validate_dir(course_dir: Path) -> Dict[str, Any]:
    """Validate a course dir end-to-end: manifest shape, that every file-backed material exists,
    and — crucially — that quiz/flashcard JSON is structurally sound (so a broken course can't
    reach the hub). Returns ``{ok, slug, errors, warnings, ...counts}``. Errors block; warnings
    are advisory (the loader stays defensive). Used by the CLI bridge + the course-builder skill."""
    errors: List[str] = []
    warnings: List[str] = []
    try:
        manifest = load_manifest(course_dir)
    except CourseError as e:
        return {"ok": False, "errors": [str(e)], "warnings": []}

    # `load_manifest` silently coerces an invalid level to "beginner"; surface that from the raw.
    try:
        raw = json.loads((course_dir / "course.json").read_text(encoding="utf-8"))
        raw_level = raw.get("level") if isinstance(raw, dict) else None
        if raw_level is not None and raw_level not in _VALID_LEVELS:
            warnings.append(f"level '{raw_level}' is invalid; treated as 'beginner'")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass

    if not manifest["modules"]:
        warnings.append("course has no modules")

    for m in manifest["modules"]:
        if not m["lessons"]:
            warnings.append(f"module '{m['id']}' has no lessons")
        for lsn in m["lessons"]:
            if not lsn["objectives"]:
                warnings.append(f"lesson '{lsn['id']}' has no objectives")
            for obj in lsn["objectives"]:
                first = obj.strip().split(" ", 1)[0].lower().rstrip(":")
                if first in _VAGUE_OBJECTIVE_VERBS:
                    warnings.append(
                        f"lesson '{lsn['id']}' objective starts with the vague verb '{first}' — "
                        f"use an assessable verb (apply, explain, build, compare, …)"
                    )
            for material in lsn["materials"]:
                mtype = material["type"]
                p = material.get("path")
                if mtype in _FILE_MATERIALS:
                    if not isinstance(p, str) or not p:
                        errors.append(f"{mtype} in '{lsn['id']}' has no string 'path'")
                        continue
                    # Confine to the course dir (parity with read_material) — a '../' or absolute
                    # path may exist on disk and pass is_file() here but 404 at serve time.
                    base = course_dir.resolve()
                    target = (base / p).resolve()
                    if base != target and base not in target.parents:
                        errors.append(f"material path escapes the course dir: {p}")
                        continue
                    if not target.is_file():
                        errors.append(f"missing material file: {p}")
                        continue
                    # Soft path convention (folder + extension).
                    folder, ext = _PATH_CONVENTION.get(mtype, ("", ""))
                    if (folder and not p.startswith(folder)) or (ext and not p.endswith(ext)):
                        warnings.append(f"{p}: a '{mtype}' usually lives in {folder}*{ext}")
                    # A blank lesson/diagram/exercise renders as an empty page (JSON types get
                    # their own content checks below).
                    if mtype in {"lesson", "diagram", "exercise"} and not target.read_text(
                        encoding="utf-8", errors="ignore"
                    ).strip():
                        warnings.append(f"{p}: file is empty")
                    # Deep content checks for the JSON material types.
                    if mtype == "quiz":
                        errors.extend(_validate_quiz_file(target))
                    elif mtype == "flashcards":
                        errors.extend(_validate_flashcards_file(target))
                    # 'count' is informational — warn if it disagrees with the file.
                    if mtype in {"quiz", "flashcards"} and isinstance(material.get("count"), int):
                        actual = _json_len(target)
                        if actual is not None and actual != material["count"]:
                            warnings.append(
                                f"{p}: manifest count={material['count']} but file has {actual}"
                            )
                elif mtype == "reading":
                    url = material.get("url")
                    if not url:
                        warnings.append(f"reading in '{lsn['id']}' has no 'url'")
                    elif not isinstance(url, str) or not url.startswith(("http://", "https://")):
                        warnings.append(
                            f"reading in '{lsn['id']}' has a non-http(s) url — the hub links it"
                        )
                elif mtype == "notebooklm":
                    pass  # optional local enrichment; nothing to check on disk
                else:
                    warnings.append(f"unknown material type '{mtype}' in '{lsn['id']}'")
                # A rubric (on exercise/project/capstone) is an optional rubrics/<id>.json the
                # learner self-assesses against — confine + existence-check + content-check it,
                # same posture as a quiz file, so a broken rubric can't reach the hub.
                rubric = material.get("rubric")
                if isinstance(rubric, str) and rubric:
                    base = course_dir.resolve()
                    target = (base / rubric).resolve()
                    if base != target and base not in target.parents:
                        errors.append(f"rubric path escapes the course dir: {rubric}")
                    elif not target.is_file():
                        errors.append(f"missing rubric file: {rubric}")
                    else:
                        if not (rubric.startswith("rubrics/") and rubric.endswith(".json")):
                            warnings.append(f"{rubric}: a rubric usually lives in rubrics/*.json")
                        errors.extend(_validate_rubric_file(target))
                        if mtype not in _RUBRIC_MATERIALS:
                            warnings.append(
                                f"rubric on a '{mtype}' material in '{lsn['id']}' — rubrics attach "
                                f"to exercise/project/capstone"
                            )
                elif rubric is not None and not isinstance(rubric, str):
                    warnings.append(f"rubric in '{lsn['id']}' must be a string path")

    report = {"ok": not errors, "slug": manifest["slug"], "errors": errors,
              "warnings": warnings}
    report.update(_counts(manifest))
    return report
