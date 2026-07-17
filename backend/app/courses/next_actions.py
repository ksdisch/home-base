"""M3 course-level "what to do next" — a pure, deterministic ranker.

The global Review-next queue (``/api/review``) + daily study plan deliberately exclude course rows
(``course:%``), so a course has had no review surface of its own. This turns a course's progress
signals — lesson completion, per-quiz SM-2 due counts, and rubric self-assessments — into a short
ranked list of concrete next actions, the same way :mod:`app.study.planner` turns the ranked SR
queue into a session.

Pure by design: it takes already-computed inputs (the manifest structure + the three progress
maps the API assembles), so every ranking property is deterministic to assert — no DB, no clock.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple


def _lessons_in_order(
    course: Mapping[str, Any]
) -> Iterator[Tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Yield ``(module, lesson)`` in manifest order — the course's intended sequence."""
    for m in course["modules"]:
        for lsn in m["lessons"]:
            yield m, lsn


def next_actions(
    course: Mapping[str, Any],
    lesson_done: Mapping[str, bool],
    quiz_stats: Mapping[str, Mapping[str, Any]],
    flashcard_stats: Mapping[str, Mapping[str, Any]],
    assessments: Mapping[str, Any],
    *,
    limit: Optional[int] = 3,
) -> List[Dict[str, Any]]:
    """Rank what to do next for one course. Returns a list of items
    ``{kind, title, reason, module_id, lesson_id, path}`` with
    ``kind ∈ {quiz_review, flashcards_review, lesson, quiz_new, project}``, priority-ordered:

    1. **quiz_review** — questions the SM-2 scheduler says are due now (time-sensitive: spacing).
    2. **flashcards_review** — deck cards due now (same spacing urgency; quizzes rank first
       because graded retrieval gives feedback a self-graded card can't).
    3. **lesson** — the next lesson not yet completed (continue where you left off).
    4. **quiz_new** — a quiz you haven't taken, on a lesson you've finished (retrieval practice).
    5. **project** — a project/capstone with a rubric, its lesson done, not yet self-assessed.

    Within a rank, course order is preserved (due reviews break ties by most-due first). ``limit``
    caps the list (``None`` = no cap).
    """
    items: List[Dict[str, Any]] = []

    # 1) Due quiz reviews — SM-2 flagged these questions overdue. Independent of lesson completion:
    #    if something is due, do it.
    for m, lsn in _lessons_in_order(course):
        for mat in lsn["materials"]:
            if mat.get("type") != "quiz" or not isinstance(mat.get("path"), str):
                continue
            due = int(quiz_stats.get(mat["path"], {}).get("due_questions", 0) or 0)
            if due > 0:
                items.append(
                    {
                        "kind": "quiz_review",
                        "title": mat.get("title") or lsn["title"],
                        "reason": f"{due} question{'s' if due != 1 else ''} due for review",
                        "module_id": m["id"], "lesson_id": lsn["id"], "path": mat["path"],
                        "_sort": (0, -due),
                    }
                )

    # 2) Due flashcards — the deck's SM-2 rows say cards are overdue. Same urgency tier as quiz
    #    reviews, ranked just after them.
    for m, lsn in _lessons_in_order(course):
        for mat in lsn["materials"]:
            if mat.get("type") != "flashcards" or not isinstance(mat.get("path"), str):
                continue
            due = int(flashcard_stats.get(mat["path"], {}).get("due_cards", 0) or 0)
            if due > 0:
                items.append(
                    {
                        "kind": "flashcards_review",
                        "title": mat.get("title") or lsn["title"],
                        "reason": f"{due} card{'s' if due != 1 else ''} due for review",
                        "module_id": m["id"], "lesson_id": lsn["id"], "path": mat["path"],
                        "_sort": (1, -due),
                    }
                )

    # 3) Continue — the first lesson not yet completed, in course order.
    first_unread: Optional[Tuple[Mapping[str, Any], Mapping[str, Any]]] = None
    any_done = False
    for m, lsn in _lessons_in_order(course):
        done = bool(lesson_done.get(lsn["id"]))
        any_done = any_done or done
        if not done and first_unread is None:
            first_unread = (m, lsn)
    if first_unread is not None:
        m, lsn = first_unread
        items.append(
            {
                "kind": "lesson",
                "title": lsn["title"],
                "reason": "Continue where you left off" if any_done else "Start the course",
                "module_id": m["id"], "lesson_id": lsn["id"], "path": None,
                "_sort": (2, 0),
            }
        )

    # 4) Practice — a quiz never taken, on a lesson you've finished.
    for m, lsn in _lessons_in_order(course):
        if not bool(lesson_done.get(lsn["id"])):
            continue
        for mat in lsn["materials"]:
            if mat.get("type") != "quiz" or not isinstance(mat.get("path"), str):
                continue
            if int(quiz_stats.get(mat["path"], {}).get("attempts", 0) or 0) == 0:
                items.append(
                    {
                        "kind": "quiz_new",
                        "title": mat.get("title") or lsn["title"],
                        "reason": "You finished the lesson — test yourself",
                        "module_id": m["id"], "lesson_id": lsn["id"], "path": mat["path"],
                        "_sort": (3, 0),
                    }
                )

    # 5) Project / capstone — has a rubric, its lesson is done, not yet self-assessed.
    for m, lsn in _lessons_in_order(course):
        if not bool(lesson_done.get(lsn["id"])):
            continue
        for mat in lsn["materials"]:
            if mat.get("type") not in ("project", "capstone"):
                continue
            if not isinstance(mat.get("path"), str) or not mat.get("rubric"):
                continue
            if mat["path"] in assessments:
                continue
            label = "capstone" if mat["type"] == "capstone" else "project"
            items.append(
                {
                    "kind": "project",
                    "title": mat.get("title") or lsn["title"],
                    "reason": f"Apply what you learned — self-assess this {label} against its rubric",
                    "module_id": m["id"], "lesson_id": lsn["id"], "path": mat["path"],
                    "_sort": (4, 0),
                }
            )

    items.sort(key=lambda it: it["_sort"])
    for it in items:
        it.pop("_sort", None)
    return items if limit is None else items[:limit]
