---
name: course-builder
description: >-
  Build a full, multi-format **course** for any topic and drop it into the Learning Hub.
  Plan-then-autonomous: interview briefly, propose a syllabus (modules → lessons → objectives),
  get one approval, then autonomously author every material — written lessons (markdown),
  visualizations (mermaid diagrams), flashcard decks, hub-shaped quizzes, curated reading — as a
  course *sidecar* on disk that the hub reads. Optionally enrich with NotebookLM artifacts
  (audio series / study guides) where `nlm` is available. Use when the user wants to "build a
  course", "make a course on X", "create a curriculum / learning path", or runs `/build-course`.
  The generated files are cloud-safe (Claude authors them); only the NotebookLM enrichment and
  the on-disk save need the local machine.
---

# course-builder — autonomous course creation for the Learning Hub

Turn a topic into a complete course the hub can surface and track. A course is a **hub-native
sidecar directory** (content on disk, progress in SQLite) — the same split the hub already uses
for NotebookLM notebooks. You (Claude) author the files; the backend reads them read-only.

Full design + roadmap: `docs/COURSE_PIPELINE_SPEC.md`. This skill is the generator; the hub's
read+track side (the `/api/courses` surface + the Courses UI) already exists.

## The contract — a course directory

```
<slug>/
  course.json            # manifest (schema below)
  lessons/<id>.md        # written lesson, markdown
  diagrams/<id>.mmd      # mermaid source
  flashcards/<id>.json   # [{ "front": "...", "back": "..." }]
  quizzes/<id>.json      # hub quiz shape (see docs/fixtures/sample-quiz.json)
```

`course.json` (see the worked example at
`backend/app/courses/examples/learning-how-to-learn/course.json`):

```jsonc
{
  "slug": "kebab-case-id",
  "title": "…", "topic": "…",
  "level": "beginner|intermediate|advanced",
  "summary": "one paragraph",
  "estimated_hours": 3,
  "created_at": "YYYY-MM-DD",
  "generator": "course-builder v1",
  "modules": [
    { "id": "m1", "title": "…", "summary": "…",
      "lessons": [
        { "id": "m1l1", "title": "…", "objectives": ["…"], "estimated_minutes": 20,
          "materials": [
            { "type": "lesson",     "title": "…", "path": "lessons/m1l1.md" },
            { "type": "diagram",    "title": "…", "path": "diagrams/m1l1.mmd", "format": "mermaid" },
            { "type": "flashcards", "title": "…", "path": "flashcards/m1l1.json", "count": 8 },
            { "type": "quiz",       "title": "…", "path": "quizzes/m1l1.json", "count": 5 },
            { "type": "reading",    "title": "…", "url": "https://…", "note": "…" },
            { "type": "notebooklm", "title": "…", "artifact": "audio", "note": "local enrichment" }
          ] } ] } ]
}
```

Rules that keep the hub happy: **lesson ids are unique across the whole course**; every
`lesson`/`diagram`/`flashcards`/`quiz` material has a real `path` that exists; quizzes use the
hub quiz shape exactly (`{title, questions:[{question, answerOptions:[{text,isCorrect,
rationale}], hint}]}`) with exactly one `isCorrect: true` per question so the existing grader
works. Don't invent facts; flag uncertainty in the lesson text.

## Workflow — plan-then-autonomous

### 1. Interview (light — just you + me)
A few questions, then proceed; don't over-ask:
- **Topic** + desired **level** (beginner/intermediate/advanced).
- **Size/appetite** — roughly how many modules × lessons (default: 3 modules × ~2–3 lessons).
- **Material mix** — default is lesson + a diagram where it clarifies + flashcards + one quiz
  per module. Ask only if they want to trim/add.
- **NotebookLM enrichment?** Only relevant locally with `nlm` — offer it, default off.

### 2. Propose the syllabus → ONE approval gate
Present the full structure: modules → lessons → per-lesson objectives → which materials →
est. time. This is the single human checkpoint. Let me edit/approve. **Do not generate
material until I approve the syllabus.** Use `AskUserQuestion` (≤4 options) for any forks.

### 3. Generate autonomously (fan out)
After approval, scaffold then author every material. **Parallelize with subagents** for any
non-trivial course — one subagent per lesson (or per module), each returning the files for its
lesson. Keep the main thread lean: subagents write their files and report a one-line summary.
- **Scaffold** the dir + skeleton manifest via the bridge (below).
- For each lesson author: the **lesson** markdown (teach it, hierarchical, plain language,
  define jargon, no invented citations); a **diagram** only where a picture genuinely helps
  (mermaid `flowchart`, `mindmap`, `sequenceDiagram`, or `xychart-beta`); a **flashcard** deck
  of the lesson's core vocabulary/ideas; and **one quiz per module** in the hub shape with
  plausible distractors + a rationale on every option.
- Pedagogy: objectives are observable ("explain…", "compare…", "apply…"); sequence builds
  prerequisites first; lean on retrieval (quizzes/flashcards) and elaboration (the "why").
- Assemble the full `course.json` and **validate** before declaring done.

### 4. Save → the hub shows it
Write the dir under the user's `COURSES_DIR` (default `backend/data/courses/<slug>/`,
gitignored). Once `course.json` validates, it appears at `/courses` in the hub immediately —
no code change, no restart of the parser needed (it reads disk per request).

### 5. (Optional, gated, ⚠️ local) NotebookLM enrichment
If the user wants audio/study-guide artifacts and `nlm` is available: hand off to the
`notebook-init` / `audio-series` skills, then record the resulting `notebook_id` (+ `artifact`)
on a `notebooklm` material in the manifest. **Confirm before any `nlm` write**; if auth lapsed,
tell the user to run `nlm login` — don't retry blindly. The course is complete without this; it
degrades gracefully.

## The backend bridge

Scaffold + validate through the JSON CLI (same venv convention as `app.topics.custom` /
`app.quiz.session`):

```bash
cd backend && .venv/bin/python -m app.courses.cli scaffold \
  --slug <slug> --title "<title>" --topic "<topic>" --level <level> --summary "<summary>"
cd backend && .venv/bin/python -m app.courses.cli validate --path data/courses/<slug>
cd backend && .venv/bin/python -m app.courses.cli list
```

`scaffold` creates the dir + subfolders + a skeleton `course.json` under `COURSES_DIR` (never
overwrites). You then author the materials and rewrite `course.json` with the real modules.
`validate` returns `{ok, errors, warnings, module_count, lesson_count, ...}` — **fix every
error before finishing** (the common ones: a material `path` that doesn't exist, a missing
title, duplicate lesson ids). If `.venv` is missing, run `make setup` once from the repo root.

## Guardrails

- **Never invent facts, quotes, or citations.** Reading-list URLs must be real; if unsure, omit.
- **One approval gate** (the syllabus). After that, generate without further per-file prompts —
  propose defaults and proceed (don't fragment the flow), but still surface what you built.
- **Validate before done.** A course with a dangling material path will render broken in the hub.
- **Stay out of the NotebookLM sidecars.** Courses live under `COURSES_DIR`; the bundled
  examples under `backend/app/courses/examples/` are read-only references — never write there.
- **Cloud vs local:** authoring the files + the manifest is ✅ cloud-safe. Saving to disk needs a
  filesystem; the NotebookLM enrichment needs `nlm` auth (⚠️ local). Say so if a step can't run
  in the current session, and still deliver everything that can (e.g. show the files inline).
- **Quiz integrity:** exactly one correct option per question; every option gets a rationale, so
  the in-hub quiz player (M2) and the mastery engine can consume it unchanged.
