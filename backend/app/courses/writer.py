"""The **write** path over user course dirs — M5's one writer.

``manifest.py`` stays the read-only loader/validator; this module is its counterpart, extracted
from the CLI bridge so the API's authoring loop and the CLI share one transactional core instead
of growing a second writer. Three invariants live here rather than at every call site:

- Writes land ONLY under the configured ``COURSES_DIR`` — never a bundled example, never a
  NotebookLM sidecar. The editing entry points additionally require the user course to already
  exist (``user_course_dir``): a bundled-only slug has no editable copy.
- Every write is transactional: snapshot what will change, write, ``validate_dir``, and restore
  the snapshots byte-identical when validation fails — a failed write never leaves a course
  worse than it was.
- ``pin_ids`` materializes the loader's positional fallback ids into the raw manifest before a
  structural edit, so a reorder can never silently re-key ``course_lesson_progress`` rows or
  the ``course:<slug>`` material-path stats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..config import get_settings
from .manifest import CourseError, validate_dir


def user_course_dir(slug: str) -> Optional[Path]:
    """The slug's dir under ``COURSES_DIR`` iff an editable course exists there, else ``None``
    (unknown slug, or a bundled-only example — those are read-only). Rejects a slug that names
    anything outside ``COURSES_DIR`` (e.g. ``..``), so no caller can be talked into escaping."""
    base = get_settings().courses_dir
    d = base / slug
    try:
        if d.resolve().parent != base.resolve():
            return None
    except OSError:
        return None
    return d if (d / "course.json").is_file() else None


def write_manifest(slug: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Write ``course.json`` under ``COURSES_DIR/<slug>/`` and validate the dir in one step —
    the transactional core the CLI's ``write`` and every M5 edit go through. The manifest's
    ``slug`` is forced to ``<slug>`` (the dir is the source of identity). On a validation
    failure the prior ``course.json`` (or nothing, on a first write) is restored byte-identical
    and the report says ``rolled_back``."""
    base = get_settings().courses_dir / slug
    if base.resolve().parent != get_settings().courses_dir.resolve():
        raise CourseError(f"slug '{slug}' does not name a directory under COURSES_DIR")
    manifest["slug"] = slug
    base.mkdir(parents=True, exist_ok=True)
    target = base / "course.json"
    backup = target.read_bytes() if target.exists() else None
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report = validate_dir(base)
    if not report.get("ok"):
        if backup is not None:
            target.write_bytes(backup)
        else:
            target.unlink(missing_ok=True)
        return {"written": None, "rolled_back": True, **report}
    return {"written": str(target), "rolled_back": False, **report}


def edit_manifest(slug: str, mutate: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
    """Apply ``mutate`` to the RAW ``course.json`` (not the normalized load, so authored fields
    the loader doesn't model survive the round-trip) and write it back transactionally. Refuses
    a slug with no editable user copy — bundled examples stay read-only. A ``CourseError``
    raised by ``mutate`` aborts before anything touches disk."""
    base = user_course_dir(slug)
    if base is None:
        raise CourseError(f"course '{slug}' has no editable copy under COURSES_DIR")
    path = base / "course.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CourseError(f"can't edit {path}: {e}") from e
    if not isinstance(raw, dict):
        raise CourseError(f"{path}: top level must be an object")
    mutate(raw)
    return write_manifest(slug, raw)


def write_material(
    slug: str, rel_path: str, content: str, *, count: Optional[int] = None
) -> Dict[str, Any]:
    """Replace ONE existing material file's content (and, when ``count`` is given, sync the
    manifest's informational ``count`` for that path) transactionally: if the course no longer
    validates, both the file and the manifest come back byte-identical. Only a file that
    already exists inside the user course dir can be written — this can create nothing and
    touch nothing outside the course."""
    base = user_course_dir(slug)
    if base is None:
        raise CourseError(f"course '{slug}' has no editable copy under COURSES_DIR")
    resolved_base = base.resolve()
    target = (base / rel_path).resolve()
    if resolved_base != target and resolved_base not in target.parents:
        raise CourseError("material path escapes the course directory")
    if not target.is_file():
        raise CourseError(f"no such material: {rel_path}")
    manifest_path = base / "course.json"
    file_backup = target.read_bytes()
    manifest_backup = manifest_path.read_bytes()
    target.write_text(content, encoding="utf-8")
    if count is not None:
        try:
            raw = json.loads(manifest_backup.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            target.write_bytes(file_backup)
            raise CourseError(f"can't edit {manifest_path}: {e}") from e
        _sync_count(raw, rel_path, count)
        raw["slug"] = slug
        manifest_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    report = validate_dir(base)
    if not report.get("ok"):
        target.write_bytes(file_backup)
        manifest_path.write_bytes(manifest_backup)
        return {"written": None, "rolled_back": True, **report}
    return {"written": str(target), "rolled_back": False, **report}


def _sync_count(raw: Dict[str, Any], rel_path: str, count: int) -> None:
    """Point every material entry that declares ``rel_path`` WITH a ``count`` at the new item
    count — the field is informational, but ``validate`` warns when it disagrees with the file,
    so a regenerated deck/quiz must keep it honest. Entries without a count stay without one."""
    for m in raw.get("modules") or []:
        if not isinstance(m, dict):
            continue
        for lsn in m.get("lessons") or []:
            if not isinstance(lsn, dict):
                continue
            for mat in lsn.get("materials") or []:
                if isinstance(mat, dict) and mat.get("path") == rel_path and "count" in mat:
                    mat["count"] = count


def pin_ids(raw: Dict[str, Any]) -> None:
    """Materialize the loader's positional fallback ids (``m2``, ``m2l1``, …) as explicit ids
    in the raw manifest — in the CURRENT order, before a reorder mutates it. Progress rows key
    on the loader's *effective* ids, so a fallback id must be pinned or its position changing
    would re-key it. Explicit ids are left untouched (the loader strips them at read time)."""
    modules = raw.get("modules")
    if not isinstance(modules, list):
        return
    for mi, m in enumerate(modules):
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if not (isinstance(mid, str) and mid.strip()):
            m["id"] = f"m{mi + 1}"
        prefix = str(m["id"]).strip()
        lessons = m.get("lessons")
        if not isinstance(lessons, list):
            continue
        for li, lsn in enumerate(lessons):
            if not isinstance(lsn, dict):
                continue
            lid = lsn.get("id")
            if not (isinstance(lid, str) and lid.strip()):
                lsn["id"] = f"{prefix}l{li + 1}"
