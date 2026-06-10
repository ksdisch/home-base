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
    load_flashcard_deck,
    material_path,
    read_material,
)
from ..models import (
    CourseDetail,
    CourseFlashcardDeckState,
    CourseFlashcardsResponse,
    CourseMaterialResponse,
    CourseQuizState,
    CourseQuizzesResponse,
    CoursesResponse,
    CourseSummary,
    FlashcardGradeRequest,
    FlashcardGradeResponse,
    FlashcardSessionCard,
    FlashcardSessionResponse,
    LessonComplete,
    QuizPrepareResponse,
)
from ..quiz.grading import QuizValidationError
from ..quiz.session import cmd_prepare
from ..store import (
    course_flashcard_progress,
    course_quiz_progress,
    flashcard_card_states,
    get_course_progress,
    record_flashcard_review,
    set_lesson_completed,
)
from ..store import mastery, scheduler

router = APIRouter()


def _typed_materials(
    course: Dict[str, Any], mtype: str
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every ``type == mtype`` material in the course, as ``(module_id, lesson_id, material)``."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for m in course["modules"]:
        for lsn in m["lessons"]:
            for mat in lsn["materials"]:
                if mat.get("type") == mtype and isinstance(mat.get("path"), str):
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
    for module_id, lesson_id, mat in _typed_materials(course, "quiz"):
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


# -- flashcards (Phase 7 M3) -----------------------------------------------------
# Deck content stays on disk; per-card SM-2 state lives in the hub's flashcard_mastery table.
# Unlike quizzes there's no answer key to protect — the learner self-grades, so front+back both
# belong on the client and the "session" fetch is a pure read (GET, nothing stashed server-side).

@router.get("/courses/{slug}/flashcards", response_model=CourseFlashcardsResponse)
def get_course_flashcards(slug: str) -> CourseFlashcardsResponse:
    """The course's flashcard decks + the learner's review state (tracked/due cards, last
    review). Powers the Review-deck buttons + due badges on the course detail. Read-only."""
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    stats = course_flashcard_progress(slug)
    decks: List[CourseFlashcardDeckState] = []
    for module_id, lesson_id, mat in _typed_materials(course, "flashcards"):
        path = mat["path"]
        try:
            # The deduped count — what a review session will actually hold (may differ from the
            # manifest's informational `count` if the file changed or has duplicate fronts).
            count = len(load_flashcard_deck(slug, path))
        except CourseError:
            count = mat.get("count") if isinstance(mat.get("count"), int) else 0
        s = stats.get(path, {})
        decks.append(
            CourseFlashcardDeckState(
                path=path,
                lesson_id=lesson_id,
                module_id=module_id,
                title=mat.get("title") or _lesson_title(course, lesson_id) or path,
                card_count=count or 0,
                tracked_cards=s.get("tracked_cards", 0),
                due_cards=s.get("due_cards", 0),
                last_review_at=s.get("last_review_at"),
            )
        )
    return CourseFlashcardsResponse(
        slug=slug,
        generated_at=datetime.now(timezone.utc).isoformat(),
        decks=decks,
    )


@router.get("/courses/{slug}/flashcards/session", response_model=FlashcardSessionResponse)
def get_flashcard_session(
    slug: str, path: str = Query(..., description="deck path relative to the course dir")
) -> FlashcardSessionResponse:
    """The full deck with per-card review state, ordered most-overdue → new → not-yet-due.

    The player builds its queue from the ``due`` flags (and can offer "review anyway" with the
    rest). Never a 500: a missing/escaping path or a file that isn't a well-formed deck degrades
    to a calm ``ok:false`` — same posture as the quiz prepare endpoint.
    """
    try:
        deck = load_flashcard_deck(slug, path)
    except CourseError:
        # Don't leak whether it's a missing course vs. a traversal attempt.
        return FlashcardSessionResponse(
            slug=slug, path=path, ok=False, error="Couldn't load this deck."
        )

    states = flashcard_card_states(slug, path)
    now = scheduler.now_utc()

    def to_card(c: Dict[str, str]) -> FlashcardSessionCard:
        st = states.get(c["key"])
        return FlashcardSessionCard(
            card_key=c["key"],
            front=c["front"],
            back=c["back"],
            new=st is None,
            due=st is None or mastery.item_is_due(st["due_at"], now),
            reps=int(st["reps"]) if st else 0,
            due_at=st["due_at"] if st else None,
        )

    cards = [to_card(c) for c in deck]

    def order(pair: Tuple[int, FlashcardSessionCard]) -> Tuple[int, float, int]:
        idx, card = pair
        od = mastery.days_overdue(card.due_at, now)
        if od is None:  # never scheduled → after the overdue backlog, in deck order
            return (1, 0.0, idx)
        # Overdue first (most overdue leading); not-yet-due last (soonest first).
        return (0, -od, idx) if od >= 0 else (2, -od, idx)

    cards = [c for _, c in sorted(enumerate(cards), key=order)]

    title = None
    try:
        course = get_course(slug)
        if course is not None:
            mat = next(
                (m for _, _, m in _typed_materials(course, "flashcards") if m["path"] == path),
                None,
            )
            if mat is not None:
                title = mat.get("title")
    except CourseError:
        pass

    return FlashcardSessionResponse(
        slug=slug,
        path=path,
        title=title,
        total=len(cards),
        due_count=sum(1 for c in cards if c.due),
        cards=cards,
    )


@router.post("/courses/{slug}/flashcards/grade", response_model=FlashcardGradeResponse)
def grade_flashcard(slug: str, body: FlashcardGradeRequest) -> FlashcardGradeResponse:
    """Record one self-graded card review and return its advanced SM-2 state.

    The card must exist in the deck file (guards junk ``flashcard_mastery`` rows); a junk grade
    is already a 422 via the request model's ``Literal``. Graded card-by-card so abandoning a
    session mid-way loses nothing.
    """
    try:
        deck = load_flashcard_deck(slug, body.path)
    except CourseError:
        # Missing course/deck or a traversal attempt — 404 either way (don't leak which).
        raise HTTPException(status_code=404, detail="No such deck.")
    if not any(c["key"] == body.card_key for c in deck):
        raise HTTPException(status_code=404, detail="No such card in this deck.")
    return FlashcardGradeResponse(
        **record_flashcard_review(slug, body.path, body.card_key, body.grade)
    )
