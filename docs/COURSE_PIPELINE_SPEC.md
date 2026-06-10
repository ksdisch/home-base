# Course Pipeline — Vision & Architecture Spec

_The "autonomous course creation" epic. Agreed via the `/autonomous-milestone` brainstorm
(2026-06-07). This is the multi-milestone vision; `docs/PHASE7_PLAN.md` is the concrete first
slice. Source of truth for **what** a course is and **how** the pipeline builds one._

## One-line vision

Give the hub a **topic** and get back a **full course** — a structured curriculum
(syllabus → modules → lessons → objectives) with materials in many formats (written lessons,
visualizations, flashcards, exercises, assessments, curated reading) and, where the machine is
local, NotebookLM artifacts (audio series, study guides, quizzes) — all surfaced and tracked in
the hub alongside everything else you're learning.

## Confirmed product decisions (brainstorm interview)

| Decision | Choice |
|---|---|
| **Where it lives** | **Both** — a generation *pipeline* (Claude skills/commands/agents) produces materials, AND the hub gets a first-class **Course** feature that sequences, surfaces, and tracks them. |
| **Autonomy** | **Plan-then-autonomous** — propose a syllabus, get one approval at the design seam, then generate all materials autonomously. |
| **First milestone appetite** | **Spec + vertical slice** — this doc (full vision) + a working end-to-end slice that produces & surfaces one real course. |
| **Material types** | Syllabus/learning-path, written lessons + visualizations, practice + assessment, **and** NotebookLM artifacts. |

## The core insight — a course is a hub-native *sidecar*

The hub already has a proven pattern: **content on disk, progress in SQLite.** NotebookLM
notebooks live as sidecar directories under `~/Projects/NotebookLMs/`; the backend reads them
read-only; the user's listened/quiz/mastery state lives in the hub's own SQLite store, kept
*out* of the sidecars.

A **course** reuses that exact split:

- **Content → disk.** Each course is a directory (a "course sidecar") with a `course.json`
  manifest (metadata + syllabus structure + a typed material index) plus the material files
  themselves (`lessons/*.md`, `diagrams/*.mmd`, `flashcards/*.json`, `quizzes/*.json`).
  **Claude authors these files** — which is exactly what an LLM does well, and it works in any
  session (cloud or local). The hub reads them read-only, just like notebook sidecars.
- **Progress → SQLite.** Per-lesson completion lives in a `course_lesson_progress` table
  (mirroring `episode_progress`); course progress % is *derived* from it. No duplicate state.

This means: the generator (a Claude skill/command) and the consumer (the hub) are cleanly
decoupled through a file format. The pipeline is **cloud-safe by construction** — the only
local-only step is the optional NotebookLM enrichment.

### Where course content lives

| Location | Purpose | In git? |
|---|---|---|
| `backend/app/courses/examples/<slug>/` | Bundled **example** course(s) — always present, so the feature works on a fresh clone / cloud session / in tests. | ✅ committed |
| `<data_dir>/courses/<slug>/` (default `backend/data/courses/`, env `COURSES_DIR`) | The user's **generated** courses. | ❌ gitignored (personal, like `youtube-notes/`) |

The catalog loader reads the **union** of both (user dir overlays bundled examples by slug), so
generated courses and the shipped example coexist.

## The manifest — `course.json`

```jsonc
{
  "slug": "learning-how-to-learn",      // dir name; the course id
  "title": "Learning How to Learn",
  "topic": "evidence-based study techniques",
  "level": "beginner",                  // beginner | intermediate | advanced
  "summary": "…one-paragraph overview…",
  "estimated_hours": 3,
  "created_at": "2026-06-07",
  "generator": "course-builder v1",
  "modules": [
    {
      "id": "m1",
      "title": "…",
      "summary": "…",
      "lessons": [
        {
          "id": "m1l1",
          "title": "…",
          "objectives": ["…", "…"],
          "estimated_minutes": 20,
          "materials": [
            { "type": "lesson",     "title": "…", "path": "lessons/m1l1.md" },
            { "type": "diagram",    "title": "…", "path": "diagrams/m1l1.mmd", "format": "mermaid" },
            { "type": "flashcards", "title": "…", "path": "flashcards/m1l1.json", "count": 8 },
            { "type": "quiz",       "title": "…", "path": "quizzes/m1l1.json", "count": 5 },
            { "type": "reading",    "title": "…", "url": "https://…", "note": "…" },
            { "type": "notebooklm", "title": "…", "notebook_id": "…", "artifact": "audio", "note": "local enrichment" }
          ]
        }
      ]
    }
  ]
}
```

- **Quizzes** use the hub's existing quiz JSON shape (`{title, questions:[{question,
  answerOptions:[{text,isCorrect,rationale}], hint}]}`) so the in-hub quiz player/grader can
  eventually consume a course quiz with no new grading code.
- **Flashcards**: `[{ "front": "…", "back": "…" }]`.
- **Diagrams**: Mermaid source (`.mmd`). Rendered as labeled source in the slice; live Mermaid
  rendering is a progressive enhancement (keeps the zero-dep frontend lean for now).

## Material taxonomy (the "many formats")

| Type | Format | Cloud-safe? | Wires into |
|---|---|---|---|
| `lesson` | Markdown explainer | ✅ | rendered inline in the hub |
| `diagram` | Mermaid | ✅ | rendered/【shown as source】in the hub |
| `flashcards` | JSON deck | ✅ | (future) spaced-rep review |
| `quiz` | Hub quiz JSON | ✅ | the existing quiz player + mastery engine |
| `exercise` / `project` / `capstone` | Markdown w/ prompts + a rubric | ✅ | (future) reflection log |
| `reading` | URL + note | ✅ | external link |
| `notebooklm` | reference to an `nlm` artifact | ⚠️ local-only | the existing topic/episode/quiz surfaces |

## Pipeline topology (the "skills/commands/agents")

- **`course-builder` skill** (the brain) — holds the manifest schema, the **pedagogy** (how to
  sequence a curriculum, write objectives, pick teaching methods per material), the
  per-material generation prompts, the cloud/local gating rules, and the backend-bridge
  invocation. Auto-triggers on "build a course on X". Runs the **plan-then-autonomous**
  workflow and fans material generation out to **subagents** (one per module/lesson) for speed.
- **`/build-course` command** (the ergonomic entry point) — a thin slash command that takes the
  topic as `$ARGUMENTS` and runs the skill's workflow.
- **`app.courses.cli` bridge** — a JSON-speaking CLI (`scaffold` / `validate` / `list`) the
  skill calls via `cd backend && .venv/bin/python -m app.courses.cli …` to scaffold a course
  dir and validate that generated output is well-formed before the hub reads it.
- **NotebookLM enrichment** (optional, ⚠️ local, gated) — for a `notebooklm` material, the
  skill hands off to the existing `notebook-init` / `audio-series` skills via `nlm`, then
  records the resulting `notebook_id` in the manifest. Never runs without explicit confirmation;
  degrades gracefully (the rest of the course is complete without it).

## Plan-then-autonomous flow

1. **Interview (light)** — topic, level, appetite (how many modules/lessons), which material
   types, cloud-vs-local (is `nlm` available?).
2. **Propose the syllabus** — modules → lessons → objectives → which materials per lesson →
   estimated time. **One approval gate here** (edit/approve).
3. **Generate autonomously** — fan out: per lesson, author the markdown lesson, diagram,
   flashcards, quiz; assemble `course.json`; validate via the bridge.
4. **Surface** — drop the course dir under `COURSES_DIR`; it appears in the hub immediately.
5. **(Optional, gated) enrich** — add NotebookLM artifacts if local + confirmed.

## Roadmap (milestones)

- **M1 — Slice (this milestone, `docs/PHASE7_PLAN.md`):** the manifest format + disk/SQLite
  split, backend read+track API, a Courses list + Course-detail UI, the `course-builder` skill +
  `/build-course` command + `app.courses.cli` bridge, and one bundled example course end-to-end.
- **M2 — Practice fully interactive:** take a course quiz in the existing quiz player (route it
  at a course material); flashcard review UI; feed attempts into the mastery engine keyed by
  course.
- **M3 — Multi-agent generation at depth:** the full subagent fan-out for large courses;
  exercises/projects/capstone with rubrics; a course-level "what to do next" using the
  Review-next engine.
- **M4 — NotebookLM enrichment in-flow:** generate an audio series + study guides for a course
  from the pipeline (local), cross-linked from the course detail.
- **M5 — Authoring loop in the hub:** "regenerate this lesson", edit objectives, reorder
  modules from the UI; export/share a course.

## Honest limitations

- The slice renders Mermaid as **source**, not a rendered graph (no new frontend deps yet).
- Course quizzes are **shaped** for the player in the slice but routed into it in M2.
- NotebookLM enrichment is **local-only** and out of the slice's automated path.
- Generation quality depends on the model; the approval gate on the syllabus is the safeguard.
