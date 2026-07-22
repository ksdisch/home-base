"""Read + validate learning-path sidecars from disk (M8).

A path is one JSON file keyed by ``notebook_id``:

    <notebook_id>.json   # {title, topic, generated_at, steps: [{id, kind, title, ...}, ...]}

whose steps *reference* the topic's real artifacts (audio/quiz/flashcards/study-guide) by
``artifact_id`` — the path owns no files of its own. Files are discovered from the union of the
bundled examples (shipped in this package, so the vertical slice works on a fresh clone / in tests)
and the user's ``PATHS_DIR`` (user wins on a ``notebook_id`` collision). Parsing is defensive: a
malformed file raises ``PathError`` at load and is skipped by the list, never a bare 500 — the same
posture as the NotebookLM sidecar + course parsers. Read-only; the generator writes files, this
module only reads them."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_settings

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

# Step kinds. Artifact-backed kinds must carry an ``artifact_id`` (a real topic artifact); glue
# kinds are the designer's connective text. Unknown kinds are kept (forward-compatible) but the
# player renders them generically.
_ARTIFACT_KINDS = {"audio", "read", "flashcards", "quiz"}
_GLUE_KINDS = {"intro", "bridge", "reflect", "recap"}

# Step ids land in URLs (POST …/steps/<id>/complete) + SQLite keys, so they must be URL-safe — a
# '/' or space silently makes a step un-completable.
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class PathError(ValueError):
    """A path sidecar file is malformed."""


def _opt_int(value: Any) -> Optional[int]:
    """A rounded int for ``estimated_minutes``, else None (bools aren't numbers here), so a stray
    string/list can't slip through to the response model and 500."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value)


def _opt_str(value: Any) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


# -- discovery -----------------------------------------------------------------

def _path_files() -> Dict[str, Path]:
    """notebook_id -> file, union of bundled examples + the user's PATHS_DIR (user wins)."""
    out: Dict[str, Path] = {}
    for base in (EXAMPLES_DIR, get_settings().paths_dir):
        if not base.is_dir():
            continue
        for child in sorted(base.glob("*.json")):
            if child.is_file():
                out[child.stem] = child  # later base (user) overrides earlier (examples)
    return out


def path_file(notebook_id: str) -> Optional[Path]:
    """The file serving ``notebook_id`` (user file, else the bundled example), or ``None``."""
    return _path_files().get(notebook_id)


def list_path_ids() -> List[str]:
    """The notebook_ids that currently have a path file (well-formed or not)."""
    return sorted(_path_files())


# -- parsing + validation ------------------------------------------------------

def _validate_steps(steps: Any, source: str) -> List[Dict[str, Any]]:
    if not isinstance(steps, list) or not steps:
        raise PathError(f"{source}: 'steps' must be a non-empty list")
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise PathError(f"{source}: step #{i} must be an object")
        sid = _opt_str(s.get("id")) or f"s{i + 1}"
        if not _ID_RE.match(sid):
            raise PathError(f"{source}: step id '{sid}' must be URL-safe ([A-Za-z0-9._-])")
        if sid in seen:
            raise PathError(f"{source}: duplicate step id '{sid}'")
        seen.add(sid)
        kind = _opt_str(s.get("kind"))
        if kind is None:
            raise PathError(f"{source}: step '{sid}' needs a string 'kind'")
        title = _opt_str(s.get("title"))
        if title is None:
            raise PathError(f"{source}: step '{sid}' needs a title")
        artifact_id = _opt_str(s.get("artifact_id"))
        if kind in _ARTIFACT_KINDS and artifact_id is None:
            raise PathError(f"{source}: step '{sid}' (kind '{kind}') needs an 'artifact_id'")
        out.append(
            {
                "id": sid,
                "kind": kind,
                "title": title,
                "focus": _opt_str(s.get("focus")),
                "body": s.get("body") if isinstance(s.get("body"), str) and s["body"].strip() else None,
                "artifact_id": artifact_id,
                "artifact_type": _opt_str(s.get("artifact_type")),
                "estimated_minutes": _opt_int(s.get("estimated_minutes")),
            }
        )
    return out


def validate_path_obj(raw: Any, notebook_id: str, *, source: Optional[str] = None) -> Dict[str, Any]:
    """Validate + shape an already-parsed path object for ``notebook_id`` (identity is the caller's,
    never the body — a stray ``notebook_id`` in ``raw`` can't point a path at the wrong topic). Raises
    ``PathError`` if malformed. Shared by the on-disk loader and the M8 Designer, which validates its
    model output IN MEMORY before writing — so a bad generation never lands. ``source`` labels errors."""
    where = source or notebook_id
    if not isinstance(raw, dict):
        raise PathError(f"{where}: top level must be an object")
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise PathError(f"{where}: 'title' is required")
    return {
        "notebook_id": notebook_id,
        "title": title.strip(),
        "topic": raw.get("topic", "") or "",
        "generated_at": raw.get("generated_at", "") or "",
        "generator": raw.get("generator", "") or "",
        "steps": _validate_steps(raw.get("steps", []), where),
    }


def load_path_file(file: Path) -> Dict[str, Any]:
    """Parse + validate a ``<notebook_id>.json`` path file. Raises ``PathError`` if malformed.

    ``notebook_id`` is forced to the filename stem — the file is the source of truth for identity,
    so a stray ``notebook_id`` in the body can't point a path at the wrong topic's SR/coverage."""
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise PathError(f"no path file {file}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PathError(f"invalid JSON/encoding in {file}: {e}") from e
    return validate_path_obj(raw, file.stem, source=str(file))


def get_path(notebook_id: str) -> Optional[Dict[str, Any]]:
    """The path structure for one topic (no progress — the API merges that in). ``None`` if there's
    no path file for ``notebook_id``; raises ``PathError`` only if the file exists but is malformed."""
    file = path_file(notebook_id)
    if file is None:
        return None
    return load_path_file(file)


# -- writing (the M8 Designer's output) ----------------------------------------

def write_path_file(notebook_id: str, raw: Dict[str, Any]) -> Path:
    """Atomically write a path sidecar to ``PATHS_DIR/<notebook_id>.json`` (same-dir tempfile +
    ``os.replace``, so a crash mid-write can't leave a truncated file the always-on server would
    read). The caller MUST validate ``raw`` first — an invalid path must never land. ``notebook_id``
    is the identity (the filename stem); it wins the ``_path_files`` union, so a generated path
    shadows a bundled example. Returns the written file path."""
    base = get_settings().paths_dir
    base.mkdir(parents=True, exist_ok=True)
    dest = base / f"{notebook_id}.json"
    fd, tmp_name = tempfile.mkstemp(dir=str(base), prefix=f"{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, dest)
    except BaseException:
        # Never leave a stray tempfile behind on any failure (ENOSPC, EACCES, an interrupt).
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return dest
