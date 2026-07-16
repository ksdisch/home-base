# Phase 7 — Courses M3: multi-agent generation at depth

_The third course-pipeline milestone (see `docs/COURSE_PIPELINE_SPEC.md`). M1 made courses
readable + lesson-trackable; M2 made their quizzes playable + SM-2-tracked per course. M3 closes
the epic's "generation at depth" line: **projects/capstone with structured, tracked rubrics**, a
**course-level "what to do next"** built on the existing SM-2 + progress signals, and the
**course-builder skill upgraded for large courses** (per-module fan-out at depth + a reviewer pass)._

## The three strands (from the spec's M3 line)

> **M3 — Multi-agent generation at depth:** the full subagent fan-out for large courses;
> exercises/projects/capstone with rubrics; a course-level "what to do next" using the
> Review-next engine.

1. **Projects / capstone with structured rubrics (tracked).** `exercise` already exists;
   `project` and `capstone` are new file-backed markdown material types. Any of the three may
   carry a **rubric** (a `rubrics/<id>.json` file: `criteria[] × levels[]`). The learner
   self-assesses against the rubric in the hub; the self-assessment is **tracked** in SQLite
   (delivering the taxonomy's promised "→ reflection log") — content on disk, progress in SQLite,
   the same split as lessons/quizzes.
2. **Course-level "what to do next."** The global `/api/review` + study plan deliberately exclude
   `course:%` (M2 boundary), so courses have had no review surface. M3 adds a course-scoped
   ranked next-up: due quiz reviews (SM-2) → continue the next unread lesson → practice an
   un-taken quiz → do an un-assessed project. Pure, deterministic ranker (mirrors
   `study.planner.build_study_plan`), surfaced as a panel on the course page.
3. **Fan-out at depth (skill).** `course-builder` already fans out one subagent per module; M3
   hardens it for large courses (wave batching + a read-only **reviewer subagent** pass before
   `write`) and teaches it to author `project`/`capstone` + rubrics. Cloud-safe; docs + prompts.

## Design decisions (don't relitigate)

- **Rubric lives on disk as `rubrics/<id>.json`**, referenced by an optional `rubric` path on the
  `exercise`/`project`/`capstone` material — mirrors flashcards/quizzes JSON-on-disk, keeps
  `course.json` lean, and is fetchable through the **existing** `/materials?path=` endpoint (no new
  read route). Shape: `{ "criteria": [ { "name", "levels": [ { "label", "description" } ] } ] }`.
- **A dedicated `course_rubric_assessment` table**, not the `reflections` table — self-contained,
  keeps course self-assessments out of the notebook reflection surfaces with zero new filters, and
  mirrors `course_lesson_progress`. Keyed `(course_slug, material_path)` (a material's `path` is its
  id, exactly as course quizzes key on `quiz_artifact_id = path`).
- **"Assessed" = a row exists.** The next-up engine treats a rubric-bearing project/capstone as
  "to do" until an assessment is saved; there is no pass/fail gate — it's self-reflection.
- **Course next-up is a new course-scoped surface**, NOT a change to the global review/study-plan
  exclusion of `course:%` (that boundary stays; interleaving courses into the cross-notebook plan
  is still out of scope).
- **The bundled example gains one flagship capstone + rubric** (`learning-how-to-learn`); the
  `project` type + rubric edge cases are covered by synthetic test fixtures, not more hand-authored
  example content.

## Backend

1. **schema.py** — `SCHEMA_VERSION` 5→6; add `course_rubric_assessment (course_slug, material_path,
   self_rating, ratings TEXT '{}', note TEXT '', updated_at, PK(course_slug, material_path))`. Plain
   `CREATE IF NOT EXISTS` → no ALTER migration entry (like `brief_notes`/`brief_visits`).
2. **store/db.py** — `get_course_assessments(slug) -> {path: {self_rating, ratings, note,
   updated_at}}`; `set_course_assessment(slug, path, self_rating, ratings, note)` (upsert + an
   `activity` row `project_assessed`, like `set_lesson_completed`). Export both from `store/__init__`.
3. **courses/manifest.py** — add `project`/`capstone` to `_FILE_MATERIALS` + `_PATH_CONVENTION`
   (`projects/*.md`, `capstones/*.md`); `_validate_rubric_file` (non-empty `criteria`; each a `name`
   + ≥2 `levels`; each level a `label` + `description`); in `validate_dir`, when a material carries a
   `rubric` string, confine + existence-check + content-check it.
4. **courses/cli.py** — `scaffold` also makes `projects/ capstones/ rubrics/` subfolders.
5. **courses/next_actions.py** (new, pure) — `next_actions(course, lesson_done, quiz_stats,
   assessments, *, limit=3) -> list[dict]`: deterministic ranked items
   `{kind, title, reason, module_id?, lesson_id?, path?}` with `kind ∈ {quiz_review, lesson,
   quiz_new, project}`. No DB/clock (inputs pre-computed) → unit-testable like `build_study_plan`.
6. **models.py** — `CourseAssessment` + `CourseAssessmentRequest`; `CourseMaterial.rubric`,
   `CourseMaterial.assessment`; `CourseNextItem`, `CourseNextResponse`.
7. **api/courses.py**
   - `GET /api/courses/{slug}/next` — assemble progress + quiz stats + assessments → `next_actions`.
   - `POST /api/courses/{slug}/assess?path=…` — path-confined; the material must exist **and carry a
     `rubric`**; writes the assessment; returns the saved `CourseAssessment`. Calm 404/422 otherwise.
   - `GET /api/courses/{slug}` — merge each material's saved `assessment` in (like lesson `completed`).

## Frontend

8. **api/types.ts** — `rubric?`/`assessment?` on `CourseMaterial`; `CourseAssessment`,
   `RubricLevel`/`RubricCriterion`/`CourseRubric`, `CourseNextItem`, `CourseNextResponse`.
9. **api/client.ts** — `courseNext(slug)`, `assessProject(slug, path, body)` (rubric content reuses
   `courseMaterial`).
10. **pages/CourseDetail.tsx** — a **"What to do next"** panel below the header (top ≤3 items; quiz
    items link to the player, lesson/project items link/scroll to their card); render `project` +
    `capstone` markdown (like `exercise`); a **rubric self-assessment** widget (fetch the rubric
    JSON, pick a level per criterion + optional note, Save → `assessProject`, shows the saved
    state from `material.assessment`); project 🛠 / capstone 🎓 / rubric 📋 icons.

## Skill + contract (cloud-safe)

11. **`.claude/skills/course-builder/references/contract.md`** — `project`/`capstone` rows; the
    optional `rubric` field; the `rubrics/<id>.json` shape; the new folders.
12. **`.claude/skills/course-builder/SKILL.md`** — §3 fan-out **at depth** (wave batching for large
    courses) + a §4 read-only **reviewer subagent** pass before `write`; project/capstone + rubric
    **pedagogy** (capstone at course end combining ≥2 modules; 3–4 observable rubric levels); update
    the honesty note (course quizzes now feed a course-level next-up; projects self-assessed against
    tracked rubrics — the **global** review still excludes courses).

## Example content

13. **`backend/app/courses/examples/learning-how-to-learn/`** — a `capstone` on the final lesson
    (`capstones/m2l2.md`, combining modules 1+2) + its `rubrics/m2l2.json`; manifest updated.

## Tests (definition of done)

14. **tests/test_courses.py** — rubric validation (valid ok; missing/malformed rubric file errors;
    `project`/`capstone` recognized as file materials; path-convention warnings); bundled example
    still validates `ok:true` with the new capstone+rubric.
15. **tests/test_courses_next.py** (new) — pure `next_actions` ranking (due-first; continue lesson;
    quiz_new only when its module is read; project only when un-assessed; `limit`); the `/next`
    endpoint.
16. **tests/test_courses_api.py** — assessment round-trip (POST assess → GET detail shows it);
    assess rejects a traversal path / a material with no rubric; schema at v6.
17. `make test` green (baseline 340 + new); `make lint`; frontend `tsc` + vitest + `npm run build` clean.

## Out of scope (M4+)

Live Mermaid rendering; interleaving course questions into the **cross-notebook** study plan;
NotebookLM enrichment in-flow (**M4**); in-hub authoring/regeneration (**M5**). Rubric assessment is
self-reflection only — no automated grading of free-text project submissions.
