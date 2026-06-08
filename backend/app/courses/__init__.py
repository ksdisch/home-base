"""Generated **courses** — a hub-native course is a sidecar directory (a ``course.json``
manifest + material files: ``lessons/*.md``, ``diagrams/*.mmd``, ``flashcards/*.json``,
``quizzes/*.json``). Claude authors them (the ``course-builder`` skill / ``/build-course``);
the hub reads them **read-only**, exactly like NotebookLM notebook sidecars. Only per-lesson
progress lives in SQLite. See ``docs/COURSE_PIPELINE_SPEC.md``."""

from .manifest import (
    CourseError,
    get_course,
    list_courses,
    load_manifest,
    read_material,
    validate_dir,
)

__all__ = [
    "CourseError",
    "get_course",
    "list_courses",
    "load_manifest",
    "read_material",
    "validate_dir",
]
