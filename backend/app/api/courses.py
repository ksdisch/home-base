"""Courses — the Phase-6 HTTP surface over the on-disk course sidecars.

Course *content* is read from disk (``app.courses.manifest``, read-only); per-lesson completion
comes from the SQLite store and is merged in here, with course progress % derived from it —
exactly how the catalog merges ``episode_progress`` into NotebookLM topics. The hub never writes
to a course dir; the only write is the lesson-complete checkbox, which lands in SQLite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Query

from ..courses import (
    CourseError,
    course_notebook_id,
    get_course,
    list_courses,
    material_path,
    read_material,
)
from ..models import (
    CourseDetail,
    CourseMaterialResponse,
    CourseQuizState,
    CourseQuizzesResponse,
    CoursesResponse,
    CourseSummary,
    LessonComplete,
    QuizPrepareResponse,
)
from ..quiz.grading import QuizValidationError
from ..quiz.session import cmd_prepare
from ..store import course_quiz_progress, get_course_progress, set_lesson_completed

router = APIRouter()


def _quiz_materials(course: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every ``type == 'quiz'`` material in the course, as ``(module_id, lesson_id, material)``."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for m in course["modules"]:
        for lsn in m["lessons"]:
            for mat in lsn["materials"]:
                if mat.get("type") == "quiz" and isinstance(mat.get("path"), str):
                    out.append((m["id"], lsn["id"], mat))
    return out


def _lesson_ids(course: Dict[str, Any]) -> List[str]:
    return [lsn["id"] for m in course["modules"] for lsn in m["lessons"]]


def _progress(lesson_ids: List[str], done: Dict[str, bool]) -> Tuple[int, int]:
    """(completed_count, pct) — only lessons that still exist in the manifest count."""
    completed = sum(1 for lid in lesson_ids if done.get(lid))
    pct = round(completed / len(lesson_ids) * 100) if lesson_ids else 0
    return completed, pct


@router.get("/courses", response_model=CoursesResponse)
def get_courses() -> CoursesResponse:
    summaries: List[CourseSummary] = []
    for s in list_courses():
        course = get_course(s["slug"])  # safe: the summary came from a valid manifest
        ids = _lesson_ids(course) if course else []
        completed, pct = _progress(ids, get_course_progress(s["slug"]))
        summaries.append(CourseSummary(**s, completed_lessons=completed, progress_pct=pct))
    return CoursesResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        courses=summaries,
    )


@router.get("/courses/{slug}", response_model=CourseDetail)
def get_course_detail(slug: str) -> CourseDetail:
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    done = get_course_progress(slug)
    for m in course["modules"]:
        for lsn in m["lessons"]:
            lsn["completed"] = done.get(lsn["id"], False)
    ids = _lesson_ids(course)
    completed, pct = _progress(ids, done)
    return CourseDetail(**course, completed_lessons=completed, progress_pct=pct)


@router.get("/courses/{slug}/materials", response_model=CourseMaterialResponse)
def get_course_material(
    slug: str, path: str = Query(..., description="material path relative to the course dir")
) -> CourseMaterialResponse:
    try:
        return CourseMaterialResponse(**read_material(slug, path))
    except CourseError as e:
        # Missing course/file or a traversal attempt — 404 either way (don't leak which).
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/courses/{slug}/lessons/{lesson_id}/complete")
def complete_lesson(slug: str, lesson_id: str, body: LessonComplete) -> Dict[str, Any]:
    course = get_course(slug)
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")
    ids = _lesson_ids(course)
    if lesson_id not in ids:
        raise HTTPException(status_code=404, detail=f"No lesson '{lesson_id}' in '{slug}'.")
    set_lesson_completed(slug, lesson_id, body.completed)
    completed, pct = _progress(ids, get_course_progress(slug))
    return {"lesson_id": lesson_id, "completed": body.completed, "progress_pct": pct,
            "completed_lessons": completed}


@router.post("/courses/{slug}/quiz/prepare", response_model=QuizPrepareResponse)
def prepare_course_quiz(
    slug: str, path: str = Query(..., description="quiz material path relative to the course dir")
) -> QuizPrepareResponse:
    """Stash a course quiz server-side and return an answer-key-free player view.

    The course quiz lives on disk, so this reuses the same session machinery as the NotebookLM
    player via ``from_file`` (no ``nlm``); the attempt is namespaced ``notebook_id='course:<slug>'``
    so the existing grader + SM-2 scheduler record it per course with no schema change. Never a
    500: a missing/escaping path or a file that isn't a valid hub quiz degrades to a calm error.
    """
    try:
        quiz_file = material_path(slug, path)  # path-confined; rejects traversal / missing file
    except CourseError:
        # Don't leak whether it's a missing course vs. a traversal attempt.
        return QuizPrepareResponse(
            notebook_id=course_notebook_id(slug), quiz_artifact_id=path, ok=False,
            error="Couldn't load this quiz.",
        )
    try:
        out = cmd_prepare(
            course_notebook_id(slug), path, from_file=str(quiz_file),
        )
    except (QuizValidationError, ValueError, OSError) as e:
        msg = getattr(e, "user_message", None) or str(e)
        return QuizPrepareResponse(
            notebook_id=course_notebook_id(slug), quiz_artifact_id=path, ok=False,
            error=f"Couldn't load this quiz: {msg}",
        )
    return QuizPrepareResponse(ok=True, **out)


@router.get("/courses/{slug}/quizzes", response_model=CourseQuizzesResponse)
def get_course_quizzes(slug: str) -> CourseQuizzesResponse:
    """The course's quizzes + the learner's attempt/SM-2 state (last score, due-for-review count).

    Powers the course detail's Quizzes section. Read-only: merges the manifest's quiz materials
    with the shared store's ``course:<slug>`` attempt/mastery rows.
    """
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    stats = course_quiz_progress(slug)
    quizzes: List[CourseQuizState] = []
    for module_id, lesson_id, mat in _quiz_materials(course):
        path = mat["path"]
        count = mat.get("count")
        if not isinstance(count, int):
            try:  # fall back to the file's actual length if the manifest omits/!=int count
                data = read_material(slug, path).get("data") or {}
                qs = data.get("questions") if isinstance(data, dict) else None
                count = len(qs) if isinstance(qs, list) else 0
            except CourseError:
                count = 0
        s = stats.get(path, {})
        quizzes.append(
            CourseQuizState(
                path=path,
                lesson_id=lesson_id,
                module_id=module_id,
                title=mat.get("title") or _lesson_title(course, lesson_id) or path,
                question_count=count or 0,
                attempts=s.get("attempts", 0),
                last_score=s.get("last_score"),
                last_total=s.get("last_total"),
                last_pct=s.get("last_pct"),
                last_attempt_at=s.get("last_attempt_at"),
                tracked_questions=s.get("tracked_questions", 0),
                due_questions=s.get("due_questions", 0),
            )
        )
    return CourseQuizzesResponse(
        slug=slug,
        generated_at=datetime.now(timezone.utc).isoformat(),
        quizzes=quizzes,
    )


def _lesson_title(course: Dict[str, Any], lesson_id: str) -> str:
    for m in course["modules"]:
        for lsn in m["lessons"]:
            if lsn["id"] == lesson_id:
                return lsn["title"]
    return ""
