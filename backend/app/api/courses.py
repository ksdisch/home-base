"""Courses — the Phase-6 HTTP surface over the on-disk course sidecars.

Course *content* is read from disk (``app.courses.manifest``, read-only); per-lesson completion
comes from the SQLite store and is merged in here, with course progress % derived from it —
exactly how the catalog merges ``episode_progress`` into NotebookLM topics.

M5 narrows the old "the hub never writes to a course dir" rule instead of keeping it absolute:
the authoring-loop endpoints (objectives, order, regenerate) write through
``app.courses.writer`` — the same transactional validate-or-rollback core the CLI bridge uses —
and only ever under ``COURSES_DIR`` (bundled examples stay read-only; NotebookLM sidecars were
never in reach). Progress still lives exclusively in SQLite.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..catalog.build import to_card
from ..catalog.ingest import load_sidecars
from ..config import get_settings
from ..courses import (
    CourseError,
    course_dir,
    course_notebook_id,
    get_course,
    list_courses,
    material_path,
    next_actions,
    read_material,
)
from ..courses.regen import (
    REGENERABLE_TYPES,
    CourseRegenClient,
    CourseRegenError,
    append_regen_ledger,
    build_prompt,
    extract_content,
    max_guidance_chars,
)
from ..courses.writer import edit_manifest, pin_ids, user_course_dir, write_material
from ..deps import get_course_regen_client
from ..models import (
    CourseAssessment,
    CourseAssessmentRequest,
    CourseDetail,
    CourseEditResponse,
    CourseFlashcardDeck,
    CourseFlashcardsResponse,
    CourseFlashcardStateResponse,
    CourseMaterialResponse,
    CourseNextItem,
    CourseNextResponse,
    CourseObjectivesUpdate,
    CourseOrderUpdate,
    CourseQuizState,
    CourseRegenRequest,
    CourseRegenResponse,
    CourseQuizzesResponse,
    CoursesResponse,
    CourseSummary,
    FlashcardCardState,
    FlashcardReviewRequest,
    LessonComplete,
    QuizPrepareResponse,
)
from ..quiz.grading import QuizValidationError
from ..quiz.session import cmd_prepare, question_key
from ..store import (
    course_flashcard_states,
    course_quiz_progress,
    get_course_assessments,
    get_course_progress,
    record_flashcard_review,
    scheduler,
    set_course_assessment,
    set_lesson_completed,
)

router = APIRouter()


def _attach_notebook_refs(course: Dict[str, Any]) -> None:
    """M4: join each ``notebooklm`` material's ``notebook_id`` against the sidecar catalog and
    merge a small ``notebook`` ref (found/title/link/counts) onto the material, so the course
    page cross-links straight to the real topic surfaces instead of rendering a dead note.
    Best-effort and read-only: a missing root / unparseable sidecars never break the course page
    (materials simply keep no ``notebook`` ref or come back ``found=False``)."""
    mats = [
        mat
        for m in course["modules"]
        for lsn in m["lessons"]
        for mat in lsn["materials"]
        if mat.get("type") == "notebooklm"
        and isinstance(mat.get("notebook_id"), str)
        and mat["notebook_id"]
    ]
    if not mats:
        return
    try:
        sidecars = load_sidecars(get_settings().notebooklm_root).sidecars
    except Exception:  # the catalog is an enrichment here — never 500 the course over it
        return
    by_id = {sc.notebook_id: sc for sc in sidecars}
    for mat in mats:
        sc = by_id.get(mat["notebook_id"])
        if sc is None:
            mat["notebook"] = {"notebook_id": mat["notebook_id"], "found": False}
            continue
        card = to_card(sc)
        mat["notebook"] = {
            "notebook_id": card.notebook_id,
            "found": True,
            "title": card.title,
            "topic_url": card.topic_url,
            "notebooklm_url": card.notebooklm_url,
            "counts": card.counts,
        }


def _quiz_materials(course: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every ``type == 'quiz'`` material in the course, as ``(module_id, lesson_id, material)``."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for m in course["modules"]:
        for lsn in m["lessons"]:
            for mat in lsn["materials"]:
                if mat.get("type") == "quiz" and isinstance(mat.get("path"), str):
                    out.append((m["id"], lsn["id"], mat))
    return out


def _flashcard_materials(course: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every ``type == 'flashcards'`` material, as ``(module_id, lesson_id, material)``."""
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for m in course["modules"]:
        for lsn in m["lessons"]:
            for mat in lsn["materials"]:
                if mat.get("type") == "flashcards" and isinstance(mat.get("path"), str):
                    out.append((m["id"], lsn["id"], mat))
    return out


def _flashcard_deck_stats(
    course: Dict[str, Any], stats: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, int]]:
    """Per-deck tracked/due card counts. ``course_quiz_progress`` aggregates the SM-2 rows of
    *any* artifact under the course namespace — a deck's cards are artifacts too — so this just
    translates its per-artifact slots into card-shaped counts for the deck paths."""
    out: Dict[str, Dict[str, int]] = {}
    for _, _, mat in _flashcard_materials(course):
        s = stats.get(mat["path"], {})
        out[mat["path"]] = {
            "tracked_cards": int(s.get("tracked_questions", 0) or 0),
            "due_cards": int(s.get("due_questions", 0) or 0),
        }
    return out


def _deck_cards(slug: str, course: Dict[str, Any], path: str) -> List[Dict[str, Any]]:
    """The deck file's cards, in file order. 404s unless ``path`` is a flashcards material the
    manifest actually declares (you can't review an arbitrary file — same posture as ``assess``),
    422 if the file isn't a well-formed deck."""
    mat = _material_by_path(course, path)
    if mat is None or mat.get("type") != "flashcards":
        raise HTTPException(status_code=404, detail=f"No flashcards material '{path}'.")
    try:
        data = read_material(slug, path).get("data")
    except CourseError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not isinstance(data, list) or not all(isinstance(c, dict) for c in data):
        raise HTTPException(status_code=422, detail=f"'{path}' is not a flashcards deck.")
    return data


def _card_keys(cards: List[Dict[str, Any]]) -> List[str]:
    """Stable per-card identity in deck order — ``question_key`` over the front text, duplicate
    fronts disambiguated by occurrence exactly like duplicate quiz stems."""
    seen: Dict[str, int] = {}
    keys: List[str] = []
    for c in cards:
        front = str(c.get("front", ""))
        occ = seen.get(front, 0)
        seen[front] = occ + 1
        keys.append(question_key(front, occ))
    return keys


def _lesson_ids(course: Dict[str, Any]) -> List[str]:
    return [lsn["id"] for m in course["modules"] for lsn in m["lessons"]]


def _material_by_path(course: Dict[str, Any], path: str) -> Dict[str, Any] | None:
    """The first material whose ``path`` matches — the manifest is the source of truth for what a
    course contains, so an ``assess`` target must be a material the course actually declares."""
    for m in course["modules"]:
        for lsn in m["lessons"]:
            for mat in lsn["materials"]:
                if mat.get("path") == path:
                    return mat
    return None


def _progress(lesson_ids: List[str], done: Dict[str, bool]) -> Tuple[int, int]:
    """(completed_count, pct) — only lessons that still exist in the manifest count."""
    completed = sum(1 for lid in lesson_ids if done.get(lid))
    pct = round(completed / len(lesson_ids) * 100) if lesson_ids else 0
    return completed, pct


def _editable_course(slug: str, lesson_id: Optional[str] = None) -> Dict[str, Any]:
    """The loaded course, guaranteed editable — the shared front door of every M5 write:
    404 unknown course / 422 malformed / 409 bundled-only (no user copy under ``COURSES_DIR``),
    plus 404 for a ``lesson_id`` the course doesn't contain."""
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")
    if user_course_dir(slug) is None:
        raise HTTPException(
            status_code=409,
            detail=f"'{slug}' is a bundled example — read-only. Its files ship with the app.",
        )
    if lesson_id is not None and lesson_id not in _lesson_ids(course):
        raise HTTPException(status_code=404, detail=f"No lesson '{lesson_id}' in '{slug}'.")
    return course


def _raw_lesson(raw: Dict[str, Any], lesson_id: str) -> Optional[Dict[str, Any]]:
    """The raw manifest's lesson whose EFFECTIVE id is ``lesson_id`` — call ``pin_ids`` first so
    fallback-id lessons are findable. The loader strips explicit ids, so compare stripped."""
    for m in raw.get("modules") or []:
        if not isinstance(m, dict):
            continue
        for lsn in m.get("lessons") or []:
            if isinstance(lsn, dict) and str(lsn.get("id", "")).strip() == lesson_id:
                return lsn
    return None


def _edit(slug: str, mutate: Callable[[Dict[str, Any]], None]) -> CourseEditResponse:
    """Run one manifest edit through the transactional writer. A ``CourseError`` (bad addressing,
    a rejected permutation) is a 422 with nothing written; a validation failure comes back as a
    calm ``ok=False`` + errors with the course rolled back untouched."""
    try:
        report = edit_manifest(slug, mutate)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CourseEditResponse(
        ok=bool(report.get("ok")),
        errors=report.get("errors", []),
        warnings=report.get("warnings", []),
    )


@router.get("/courses", response_model=CoursesResponse)
def get_courses() -> CoursesResponse:
    summaries: List[CourseSummary] = []
    for s in list_courses():
        course = get_course(s["slug"])  # safe: the summary came from a valid manifest
        ids = _lesson_ids(course) if course else []
        completed, pct = _progress(ids, get_course_progress(s["slug"]))
        summaries.append(
            CourseSummary(
                **s,
                completed_lessons=completed,
                progress_pct=pct,
                editable=user_course_dir(s["slug"]) is not None,
            )
        )
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
    assessments = get_course_assessments(slug)  # {material_path: {...}} — merged onto materials
    for m in course["modules"]:
        for lsn in m["lessons"]:
            lsn["completed"] = done.get(lsn["id"], False)
            for mat in lsn["materials"]:
                saved = assessments.get(mat.get("path"))
                if saved is not None:
                    mat["assessment"] = saved
    _attach_notebook_refs(course)  # M4: notebooklm materials cross-link to the catalog
    ids = _lesson_ids(course)
    completed, pct = _progress(ids, done)
    return CourseDetail(
        **course,
        completed_lessons=completed,
        progress_pct=pct,
        editable=user_course_dir(slug) is not None,
    )


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


@router.put(
    "/courses/{slug}/lessons/{lesson_id}/objectives", response_model=CourseEditResponse
)
def edit_lesson_objectives(
    slug: str, lesson_id: str, body: CourseObjectivesUpdate
) -> CourseEditResponse:
    """M5: replace one lesson's objectives. Objectives key nothing in the store, so this can
    never orphan progress; the edit still rides the transactional writer so a course that fails
    validation (e.g. a missing material file) bounces with the course untouched."""
    _editable_course(slug, lesson_id=lesson_id)
    objectives = [o.strip() for o in body.objectives if o.strip()]

    def mutate(raw: Dict[str, Any]) -> None:
        pin_ids(raw)
        lesson = _raw_lesson(raw, lesson_id)
        if lesson is None:  # the manifest changed underneath us between check and write
            raise CourseError(f"no lesson '{lesson_id}' in '{slug}'")
        lesson["objectives"] = objectives

    return _edit(slug, mutate)


@router.put("/courses/{slug}/order", response_model=CourseEditResponse)
def reorder_course(slug: str, body: CourseOrderUpdate) -> CourseEditResponse:
    """M5: reorder modules, and lessons within their module. The body must be a complete
    bijection of the current structure — every module id exactly once, and per module every one
    of its current lesson ids exactly once (cross-module moves are out of scope). Ids are pinned
    before permuting, so ``course_lesson_progress`` rows and the ``course:<slug>``
    material-path stats can never re-key. Any mismatch is a 422 with nothing written."""
    _editable_course(slug)

    def mutate(raw: Dict[str, Any]) -> None:
        pin_ids(raw)
        modules = raw.get("modules")
        if not isinstance(modules, list):
            raise CourseError("manifest has no modules list")
        by_id: Dict[str, Dict[str, Any]] = {
            str(m.get("id", "")).strip(): m for m in modules if isinstance(m, dict)
        }
        want = [m.id for m in body.modules]
        if sorted(want) != sorted(by_id):
            raise CourseError(
                f"module ids must be exactly {sorted(by_id)} in some order (got {want})"
            )
        new_modules: List[Dict[str, Any]] = []
        for om in body.modules:
            m = by_id[om.id]
            lesson_by_id = {
                str(lsn.get("id", "")).strip(): lsn
                for lsn in (m.get("lessons") or [])
                if isinstance(lsn, dict)
            }
            if sorted(om.lessons) != sorted(lesson_by_id):
                raise CourseError(
                    f"module '{om.id}' lessons must be exactly {sorted(lesson_by_id)} in "
                    f"some order (got {om.lessons})"
                )
            m["lessons"] = [lesson_by_id[lid] for lid in om.lessons]
            new_modules.append(m)
        raw["modules"] = new_modules

    return _edit(slug, mutate)


def _lesson_material(
    course: Dict[str, Any], lesson_id: str, path: str
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """(module, lesson, material) for a material THAT lesson declares at ``path`` — you can't
    regenerate an arbitrary file (same posture as ``assess``). 404 otherwise."""
    for m in course["modules"]:
        for lsn in m["lessons"]:
            if lsn["id"] != lesson_id:
                continue
            for mat in lsn["materials"]:
                if mat.get("path") == path:
                    return m, lsn, mat
    raise HTTPException(
        status_code=404, detail=f"No material '{path}' in lesson '{lesson_id}'."
    )


@router.post(
    "/courses/{slug}/lessons/{lesson_id}/regenerate", response_model=CourseRegenResponse
)
def regenerate_material(
    slug: str,
    lesson_id: str,
    body: CourseRegenRequest,
    client: CourseRegenClient = Depends(get_course_regen_client),
) -> CourseRegenResponse:
    """M5's flagship: rewrite ONE of a lesson's materials on the headless claude lane
    (subscription billing, API key scrubbed, no tools — the chat.py precedent). Validation is
    the gate: the new content lands only if the whole course still validates; otherwise it
    rolls back byte-identical and the errors come back as ``ok=False``. Regenerating a deck or
    quiz resets the replaced items' SM-2/attempt stats by design (identity is content/path
    keyed). Every run — success, rollback, or failure — lands in the course-regen ledger."""
    guidance = body.guidance.strip()
    if len(guidance) > max_guidance_chars():
        raise HTTPException(
            status_code=400,
            detail=f"guidance is limited to {max_guidance_chars()} characters",
        )
    course = _editable_course(slug, lesson_id=lesson_id)
    module, lesson, material = _lesson_material(course, lesson_id, body.path)
    if material.get("type") not in REGENERABLE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{material.get('type')}' materials can't be regenerated — only "
                f"{sorted(REGENERABLE_TYPES)}"
            ),
        )
    try:
        current = material_path(slug, body.path).read_text(encoding="utf-8")
    except (CourseError, OSError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=404, detail=str(e))

    settings = get_settings()

    def ledger(**kw: Any) -> None:
        append_regen_ledger(
            settings.course_regen_ledger,
            slug=slug,
            lesson_id=lesson_id,
            material_path=body.path,
            material_type=material["type"],
            model=client.model,
            **kw,
        )

    prompt = build_prompt(course, module, lesson, material, current, guidance)
    try:
        out = client.ask(prompt)
    except CourseRegenError as e:
        ledger(error=f"{e}: {e.detail}"[:300] if e.detail else str(e))
        raise HTTPException(status_code=502, detail=str(e))
    envelope = out["envelope"]
    try:
        content, count = extract_content(material["type"], out["answer"])
    except CourseRegenError as e:
        ledger(envelope=envelope, error=str(e))
        return CourseRegenResponse(
            ok=False,
            path=body.path,
            error=str(e),
            duration_ms=envelope.get("duration_ms"),
            total_cost_usd=envelope.get("total_cost_usd"),
        )
    try:
        report = write_material(slug, body.path, content, count=count)
    except CourseError as e:
        ledger(envelope=envelope, error=str(e))
        raise HTTPException(status_code=422, detail=str(e))
    ledger(envelope=envelope, rolled_back=bool(report.get("rolled_back")))
    return CourseRegenResponse(
        ok=bool(report.get("ok")),
        path=body.path,
        rolled_back=bool(report.get("rolled_back")),
        errors=report.get("errors", []),
        warnings=report.get("warnings", []),
        count=count,
        duration_ms=envelope.get("duration_ms"),
        total_cost_usd=envelope.get("total_cost_usd"),
    )


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


@router.get("/courses/{slug}/export")
def export_course(slug: str) -> Response:
    """M5: download the whole course dir as a zip — read-only (works for bundled examples too)
    and the safety valve before a risky edit. Hidden files (``.DS_Store`` and friends) are
    skipped; course dirs are small text, so the zip is built in memory."""
    cdir = course_dir(slug)
    if cdir is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(cdir.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(cdir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            zf.write(f, arcname=f"{slug}/{rel.as_posix()}")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}-course.zip"'},
    )


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


@router.get("/courses/{slug}/flashcards", response_model=CourseFlashcardsResponse)
def get_course_flashcards(slug: str) -> CourseFlashcardsResponse:
    """The course's flashcard decks + the learner's review state (tracked/due card counts).

    Powers the Review buttons + due chips on the course detail — the deck-shaped mirror of the
    ``/quizzes`` surface. Read-only."""
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    deck_stats = _flashcard_deck_stats(course, course_quiz_progress(slug))
    decks: List[CourseFlashcardDeck] = []
    for module_id, lesson_id, mat in _flashcard_materials(course):
        path = mat["path"]
        count = mat.get("count")
        if not isinstance(count, int):
            try:  # fall back to the file's actual length if the manifest omits/!=int count
                data = read_material(slug, path).get("data")
                count = len(data) if isinstance(data, list) else 0
            except CourseError:
                count = 0
        s = deck_stats.get(path, {})
        decks.append(
            CourseFlashcardDeck(
                path=path,
                lesson_id=lesson_id,
                module_id=module_id,
                title=mat.get("title") or _lesson_title(course, lesson_id) or path,
                card_count=count or 0,
                tracked_cards=s.get("tracked_cards", 0),
                due_cards=s.get("due_cards", 0),
            )
        )
    return CourseFlashcardsResponse(
        slug=slug,
        generated_at=datetime.now(timezone.utc).isoformat(),
        decks=decks,
    )


@router.get("/courses/{slug}/flashcards/state", response_model=CourseFlashcardStateResponse)
def get_course_flashcard_state(
    slug: str, path: str = Query(..., description="deck path relative to the course dir")
) -> CourseFlashcardStateResponse:
    """Per-card review state for one deck, aligned by index to the deck file's order — the
    review page orders its session (due → new → later) from this. Card keys are derived
    server-side; the client only ever sees indices."""
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    cards = _deck_cards(slug, course, path)
    states = course_flashcard_states(slug, path)
    out: List[FlashcardCardState] = []
    for i, key in enumerate(_card_keys(cards)):
        st = states.get(key)
        out.append(
            FlashcardCardState(
                index=i,
                tracked=st is not None,
                due=bool(st["due"]) if st else False,
                reps=st["reps"] if st else 0,
                lapses=st["lapses"] if st else 0,
                due_at=st["due_at"] if st else None,
                last_review_at=st["last_review_at"] if st else None,
            )
        )
    return CourseFlashcardStateResponse(
        slug=slug,
        path=path,
        generated_at=datetime.now(timezone.utc).isoformat(),
        cards=out,
    )


@router.post("/courses/{slug}/flashcards/review", response_model=FlashcardCardState)
def review_flashcard(
    slug: str,
    body: FlashcardReviewRequest,
    path: str = Query(..., description="deck path relative to the course dir"),
) -> FlashcardCardState:
    """Record one self-graded card (``again`` | ``hard`` | ``good``) and advance its SM-2 state —
    the same quality trio a graded quiz answer produces, persisted to the same per-item scheduler
    under ``course:<slug>``. The card's key is derived from the deck file server-side, so a made-up
    key can never mint a mastery row. Returns the freshly saved state."""
    if body.rating not in scheduler.FLASHCARD_QUALITY:
        raise HTTPException(
            status_code=422,
            detail=f"rating must be one of {sorted(scheduler.FLASHCARD_QUALITY)}",
        )
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    cards = _deck_cards(slug, course, path)
    if not (0 <= body.index < len(cards)):
        raise HTTPException(
            status_code=422, detail=f"index {body.index} out of range (deck has {len(cards)} cards)"
        )
    key = _card_keys(cards)[body.index]
    saved = record_flashcard_review(slug, path, key, body.rating)
    return FlashcardCardState(
        index=body.index,
        tracked=True,
        due=False,  # just reviewed — the next due_at is always ≥1 day out
        reps=saved["reps"],
        lapses=saved["lapses"],
        due_at=saved["due_at"],
        last_review_at=saved["last_review_at"],
    )


@router.get("/courses/{slug}/next", response_model=CourseNextResponse)
def get_course_next(slug: str) -> CourseNextResponse:
    """A course-scoped "what to do next": due quiz reviews → due flashcards → continue the next
    lesson → practice a finished lesson's quiz → self-assess a ready project/capstone. Built on the
    same SM-2 + progress
    signals as the rest of the hub, but course-scoped (the global ``/review`` + study plan exclude
    course rows on purpose). Read-only; never a 500 — an empty/blank course yields no items."""
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")

    stats = course_quiz_progress(slug)
    items = next_actions(
        course,
        get_course_progress(slug),
        stats,
        _flashcard_deck_stats(course, stats),
        get_course_assessments(slug),
    )
    lesson_count = len(_lesson_ids(course))
    return CourseNextResponse(
        slug=slug,
        generated_at=datetime.now(timezone.utc).isoformat(),
        all_done=lesson_count > 0 and not items,
        items=[CourseNextItem(**it) for it in items],
    )


@router.post("/courses/{slug}/assess", response_model=CourseAssessment)
def assess_project(
    slug: str,
    body: CourseAssessmentRequest,
    path: str = Query(..., description="project/capstone material path relative to the course dir"),
) -> CourseAssessment:
    """Save a rubric self-assessment for a project/capstone. The ``path`` must be a material the
    course actually declares AND carry a ``rubric`` — you can't assess an arbitrary path. Persists
    to ``course_rubric_assessment`` (the project + rubric stay on disk; only the self-rating lands
    in SQLite, mirroring the lesson-complete checkbox)."""
    if body.self_rating is not None and not (1 <= body.self_rating <= 5):
        raise HTTPException(status_code=422, detail="self_rating must be between 1 and 5")
    try:
        course = get_course(slug)
    except CourseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if course is None:
        raise HTTPException(status_code=404, detail=f"No course '{slug}'.")
    material = _material_by_path(course, path)
    if material is None or not material.get("rubric"):
        # No such material, or it declares no rubric to assess against.
        raise HTTPException(
            status_code=404, detail=f"No rubric-assessable material '{path}' in '{slug}'."
        )
    saved = set_course_assessment(slug, path, body.self_rating, body.ratings, body.note)
    return CourseAssessment(**saved)


def _lesson_title(course: Dict[str, Any], lesson_id: str) -> str:
    for m in course["modules"]:
        for lsn in m["lessons"]:
            if lsn["id"] == lesson_id:
                return lsn["title"]
    return ""
