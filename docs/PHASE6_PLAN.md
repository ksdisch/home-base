# Phase 6 Plan — Courses (the course-pipeline vertical slice)

_The first milestone of the Course Pipeline epic (see `docs/COURSE_PIPELINE_SPEC.md`).
Plan-then-autonomous course creation: a generation pipeline (Claude skill + command + bridge)
produces a course as a hub-native sidecar; the hub reads & tracks it. This slice ships the
format, the read+track backend, the UI, the tooling, and one bundled example course
end-to-end._

## Goal

A user can: see a **Courses** section in the hub, open a course, read its lessons, see its
diagram/flashcards/quiz, and check lessons off (progress %). A future `/build-course <topic>`
run drops a new course dir into `COURSES_DIR` and it shows up — no code change needed.

## Architecture (decided)

- **Content on disk, progress in SQLite** — mirrors the NotebookLM catalog/episode-progress
  split. A course = a directory with `course.json` + material files. Claude authors them
  (cloud-safe). The hub reads them read-only.
- Bundled example at `backend/app/courses/examples/<slug>/` (committed → always works); user
  courses at `COURSES_DIR` (default `backend/data/courses/`, gitignored). Loader reads the union.

## Backend tasks

1. **schema.py** — bump `SCHEMA_VERSION` 2→3; add `course_lesson_progress` (course_slug,
   lesson_id, completed, updated_at; PK(course_slug, lesson_id)). Mirrors `episode_progress`.
2. **config.py** — add `courses_dir` (env `COURSES_DIR`, default `data_dir/courses`); create it
   in `ensure_dirs()`.
3. **`app/courses/` package**
   - `manifest.py` — dataclasses/loader: discover course dirs (union examples + COURSES_DIR),
     parse + validate `course.json`, compute `(total_lessons, total per material type)`, resolve
     a material file's text. Robust to malformed dirs (skip + warn, like the sidecar parser).
   - `cli.py` — JSON-speaking bridge: `list`, `validate --path`, `scaffold --slug --title …`.
     Invoked by the skill via the venv. Mirrors `app.topics.custom` conventions.
   - `examples/learning-how-to-learn/` — the bundled example course (2 modules × 2 lessons;
     lessons, a mermaid diagram, a flashcard deck, a hub-shaped quiz, a reading + a notebooklm
     placeholder material).
4. **store/db.py + __init__.py** — `get_course_progress(slug)`, `set_lesson_completed(slug,
   lesson_id, completed)` (logs an `activity` row like episodes do).
5. **models.py** — `CourseSummary`, `CourseDetail`, `Module`, `Lesson`, `Material`,
   `CoursesResponse`, lesson-complete request/response.
6. **api/courses.py** + register in `main.py`
   - `GET /api/courses` — summaries (title, topic, level, counts, progress %).
   - `GET /api/courses/{slug}` — full structure + per-lesson `completed` + progress %.
   - `GET /api/courses/{slug}/materials?path=…` — a material's raw text (markdown/mermaid) or
     parsed JSON (flashcards/quiz). Path is validated to stay inside the course dir.
   - `POST /api/courses/{slug}/lessons/{lesson_id}/complete` — `{completed}` toggle.

## Frontend tasks

7. **api/types.ts** — Course types mirroring the models.
8. **api/client.ts** — `courses()`, `course(slug)`, `courseMaterial(slug, path)`,
   `setLessonComplete(slug, lessonId, completed)`.
9. **components/Markdown.tsx** — tiny dependency-free markdown renderer (headings, lists, bold,
   inline code, code fences, paragraphs). Keeps the zero-extra-dep posture.
10. **components/CourseCard.tsx**, **pages/Courses.tsx**, **pages/CourseDetail.tsx** — grid +
    detail (syllabus, objectives, lesson markdown inline, diagram source, flashcards, quiz
    preview, lesson-complete toggle). Reuse Badge/Banner/MasteryBar idioms.
11. **App.tsx** — `Courses` nav link + `/courses` and `/courses/:slug` routes.

## Tooling tasks

12. **`.claude/skills/course-builder/SKILL.md`** — the brain: schema, pedagogy, per-material
    prompts, plan-then-autonomous workflow + subagent fan-out, cloud/local gating, bridge calls.
13. **`.claude/commands/build-course.md`** — thin `$ARGUMENTS`-topic entry point.
14. **CLAUDE.md** — register the command + skill in the tables.

## Tests (definition of done)

15. **tests/test_courses.py** — manifest parse/validate, union discovery, totals, malformed-dir
    robustness, progress merge.
16. **tests/test_courses_api.py** — list, detail (with completion), material fetch (+ path
    traversal rejected), lesson-complete round-trip, 404s.
17. `make test` green; `cd frontend && npm run build` (tsc + vite) clean.

## Out of scope (deferred to M2+)

- Taking a course quiz *in the player* (shaped now, routed later); flashcard review UI.
- Live Mermaid rendering; exercises/projects/capstone; NotebookLM enrichment in the automated
  path; in-hub authoring/regeneration.
