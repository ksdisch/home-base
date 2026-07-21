"""Generated learning paths over NotebookLM topics (M8).

A path is a single JSON sidecar — ``<notebook_id>.json`` — whose steps *reference* the topic's
real artifacts (by ``artifact_id``) rather than owning files of their own. Paths are discovered
from the union of the bundled examples (shipped in this package, so the vertical slice works on a
fresh clone / in tests) and the user's ``PATHS_DIR`` (their generated paths; the user file wins on
a ``notebook_id`` collision). This package is read-only over path files; progress lives in SQLite.
"""

from .manifest import PathError, get_path, list_path_ids, load_path_file, path_file

__all__ = ["PathError", "get_path", "list_path_ids", "load_path_file", "path_file"]
