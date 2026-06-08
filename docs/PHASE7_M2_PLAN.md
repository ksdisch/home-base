# Phase 7 — Courses M2: course quizzes in the player + per-course SM-2

_The second course-pipeline milestone. M1 made courses readable + lesson-trackable; M2 makes
their **quizzes playable in the existing in-hub quiz player**, graded by the same offline oracle,
with attempts + SM-2 state recorded **per course** so a course becomes genuinely trackable._

## Key insight (why this is low-risk)

The quiz session machinery (`app.quiz.session.cmd_prepare`/`cmd_grade`) already supports a
**`from_file`** source — it stashes the keyed quiz server-side and returns an answer-key-free
player view, identical to the NotebookLM path. And `store.record_attempt(notebook_id,
quiz_artifact_id, …)` is fully generic over `notebook_id`. So:

- A course quiz is prepared with `from_file=<course quiz path>` and **namespaced**
  `notebook_id = "course:<slug>"`, `quiz_artifact_id = "<material path>"`.
- The existing `POST /api/quiz/grade` is reused **unchanged** — it grades by `session_id` and
  records the attempt + the per-question SM-2 advance, course-scoped, automatically.
- **No schema change.** Course attempts + SM-2 live in the same `attempts` / `attempt_answers`
  / `question_mastery` / `topic_mastery` tables, under the `course:` namespace.

## Boundary: keep courses out of the notebook surfaces

Because course attempts write the same tables, the notebook-facing aggregates would otherwise
show a broken, unlabelled `course:<slug>` "topic". The clean rule: **every notebook aggregate
excludes `notebook_id LIKE 'course:%'`**, and courses get their own read surface. The activity
**streak/heatmap stays source-agnostic** (course study still counts as activity — it has no
per-notebook label to break).

Filtered (5 queries): `mastery.review_queue` (Review page + home badges), `mastery.sr_plan_items`
(Study plan), `progress.topic_breakdowns`, `progress.shaky_quizzes`, `progress.overall_summary`.

## Backend

1. `courses/manifest.py` — `material_path(slug, rel)` (path-confined resolver returning the
   `Path`, mirroring `read_material`'s confinement) + a `COURSE_NB_PREFIX = "course:"` constant.
2. `store/db.py` — `course_quiz_progress(slug, *, now)`: per-`quiz_artifact_id` attempt stats
   (count, last score/total/pct/at) + per-quiz SM-2 `tracked`/`due` counts (reusing
   `mastery.item_is_due`). Pure read; `now`-injectable.
3. `store/{mastery,progress}.py` — the 5 `NOT LIKE 'course:%'` guards above.
4. `models.py` — `CourseQuizState`, `CourseQuizzesResponse`.
5. `api/courses.py`
   - `POST /api/courses/{slug}/quiz/prepare?path=…` — resolves the quiz material (path-confined),
     `cmd_prepare(notebook_id=f"course:{slug}", quiz_artifact_id=path, from_file=…)`; returns the
     answer-key-free `QuizPrepareResponse`. Calm `ok:false` on a bad/missing/non-quiz path.
   - `GET /api/courses/{slug}/quizzes` — the manifest's quiz materials joined with
     `course_quiz_progress`: `{path, lesson_id, module_id, title, question_count, attempts,
     last_score/total/pct/at, tracked_questions, due_questions}`.

## Frontend

6. `api/types.ts` + `api/client.ts` — `CourseQuizState`/`CourseQuizzesResponse`;
   `prepareCourseQuiz(slug, path)`, `courseQuizzes(slug)`.
7. `App.tsx` — `/courses/:slug/quiz` route (the quiz material `path` rides in `?path=`).
8. `pages/QuizPlayer.tsx` — generalize to a `source: "topic" | "course"`: pick the prepare call
   + the back-link; everything else (play → grade → review → retake) is shared. The grade path is
   already source-agnostic.
9. `pages/CourseDetail.tsx` — a **Quizzes** section: per quiz, a Take/Retake button (→ the
   player), the last score, and an "N due for review" chip from the SM-2 state.

## Tests (definition of done)

`tests/test_courses_quiz.py`: prepare-from-file is answer-key-free (no `isCorrect`/`rationale` in
the player view); grade round-trip persists a `course:<slug>` attempt **and** advances
`question_mastery` SM-2; `/quizzes` reports the attempt + due counts; a path-traversal `path` is
rejected; a non-quiz/garbage path degrades to `ok:false` (never 500); and the **notebook surfaces
(`/review`, `/study-plan`, `/progress`) exclude the course rows** while the activity streak counts
the course attempt. `make test` green; frontend `tsc` + vitest + build clean.

## Out of scope (M3+)

Interleaving course questions into the cross-notebook **Study plan** (needs course-aware segment
links — deferred); flashcard review UI; live Mermaid; exercises/capstone; NotebookLM enrichment.
