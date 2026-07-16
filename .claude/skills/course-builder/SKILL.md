---
name: course-builder
description: >-
  Build a full, multi-format **course** for any topic and drop it into the Learning Hub.
  Plan-then-autonomous: interview briefly, propose a syllabus (modules → lessons → objectives),
  get one approval, then autonomously author every material — written lessons (markdown),
  worked examples + exercises, visualizations (mermaid), flashcard decks, hub-shaped quizzes,
  curated reading — as a course *sidecar* on disk that the hub reads. Optionally enrich with
  NotebookLM artifacts where `nlm` is available. Use when the user wants to "build a course",
  "make a course on X", "create a curriculum / learning path", or runs `/build-course`. The
  authoring is cloud-safe (Claude writes the files); only NotebookLM enrichment + saving to
  disk need the local machine.
---

# course-builder — autonomous course creation for the Learning Hub

Turn a topic into a complete course the hub surfaces and tracks. A course is a **hub-native
sidecar directory** (content on disk, progress in SQLite) — the same split the hub uses for
NotebookLM notebooks. You author the files; the backend reads them read-only.

- **Exact formats** (manifest schema, quiz/flashcard shapes, the markdown subset, CLI commands):
  see [`references/contract.md`](references/contract.md). Read it before authoring — get the
  shapes right and the course just works.
- **Design + roadmap:** `docs/COURSE_PIPELINE_SPEC.md`. The bundled
  `backend/app/courses/examples/learning-how-to-learn/` is the gold-standard template — imitate
  its quiz discipline (one correct option, a rationale on every option) and its clarity.

## Workflow — plan-then-autonomous

### 1. Interview (light — just you + me; propose defaults, don't over-ask)
- **Topic** + **level** (beginner / intermediate / advanced — see the level contract below).
- **Size** — default **3 modules × ~2–3 lessons**; adjust to the topic.
- **Material mix** — default per lesson: a lesson + a worked example, flashcards, a diagram
  where a picture genuinely helps, an exercise for skill topics, and **one quiz per module**
  (end-of-module, summative). Ask only to trim/add.
- **NotebookLM enrichment?** Local-only (`nlm`); default **off**.

### 2. Propose the syllabus → ONE approval gate
Present the full structure: modules → lessons → **objectives** → which materials per lesson →
est. time, plus course-level **prerequisites**. For each objective, name the assessment that
covers it (a quiz question, flashcard, or exercise) — objective↔assessment alignment.
**This is the single human checkpoint. Do not author any material until I approve/edit it.**
Use `AskUserQuestion` (≤4 options) for forks. The approved syllabus is the contract for *which
materials exist* — during authoring you may refine content but **don't silently add/drop a
material** the user approved (note any change in the final report).

### 3. Generate autonomously (fan out per MODULE)
**Fan-out contract — the main thread owns identity + assembly; subagents only author files:**
1. From the approved syllabus, the main thread finalizes the **full id map** (every `mXlY` id and
   every material path) and scaffolds the dir (`… cli scaffold …`).
2. Dispatch **one subagent per module** (not per lesson — so the single module quiz has one clear
   owner). Hand each subagent a **copy-paste-complete payload** so it never has to infer authoring
   rules — verbatim: (a) `topic` + `level`; (b) the **full syllabus** (for cross-references);
   (c) **its module spec only** — every lesson id, its objectives, and the **exact id + path of
   every file-backed material to write**; (d) the entire **Pedagogy** section of this skill; and
   (e) the entire `references/contract.md` **including the Markdown SUBSET**. Each subagent **writes
   only its module's file-backed materials** (lessons/exercises/projects/capstones/diagrams/
   flashcards/quizzes **and any rubric JSON** those carry) to the given paths and returns a JSON list
   of `{path, type, lesson_id}`. Subagents **must use only the assigned ids/paths — never mint new
   ones**, and must **not** touch `course.json`.
3. The main thread assembles `course.json` from the approved id map (never from subagent-invented
   ids), backfilling `created_at` (today) and `estimated_hours` (≈ Σ lesson minutes / 60, rounded
   to a whole hour, min 1). **File-less materials (`reading`, `notebooklm`) have no subagent and no
   file — the main thread owns them**: place them in the manifest itself and do any `reading`-URL
   verification here (subagents return only file paths, so a `reading` is invisible to them).
4. **Validate, then self-check** (see §4). For a small course (1–2 modules) authoring inline on
   the main thread is fine — fan-out is for speed at scale.

**At depth (large courses).** Fan-out is what makes a big course tractable — but dispatch in
**waves of ~3–4 module-subagents at a time**, not all at once: reconcile each wave's returned
`{path,…}` lists against the id map before launching the next, so a partial failure re-dispatches
only the missing module (§ "Partial fan-out") instead of forcing a full restart. The main thread
stays the single owner of `course.json`, identity, and the file-less `reading`/`notebooklm`
materials across every wave. Keep each subagent's job **one module** no matter how large the
course — never widen a subagent to multiple modules to "save" agents.

### 4. Validate → self-check → save
- Commit the manifest with `… cli write --slug <slug> --from-file <manifest.json>` — it writes
  `course.json` **and** validates atomically, **rolls back** on failure (a broken write never
  clobbers a good manifest), and **exits non-zero** when `ok:false`, so you can branch on the exit
  code. This is the preferred path (validated-by-construction). *Fallback:* write `course.json`
  with your file tools, then validate the **dir the `scaffold` step reported** —
  `… cli validate --path "<the `path` from scaffold's JSON output>"`. Don't hardcode
  `data/courses/<slug>`: courses live under `COURSES_DIR` (default `backend/data/courses`, but the
  user may override it), and `scaffold`/`write` return the real path — use that.
- Get `ok: true`. `validate` checks structure, that files exist + stay inside the course dir, and
  that **quizzes have exactly one correct option + a rationale on every option**, flashcards are
  `{front, back}`, and **each `rubric` file has ≥1 criterion, each with a name + ≥2 labelled,
  described levels**; it also *warns* on unknown material types, empty modules, count mismatches, bad
  levels, **vague (non-Bloom's) objective verbs, empty lesson/diagram files, non-http(s) `reading`
  URLs, and a rubric on a non-exercise/project/capstone material** — clear those too. Loop **at most
  3 times**; map errors to fixes (`missing material file`/`missing rubric file` → the owning subagent
  didn't write it / wrong path → re-dispatch just that module, **unless** the file exists at the
  convention path and the manifest just points elsewhere → fix the manifest path; `duplicate lesson
  id` → a subagent minted its own id → use the assigned map). If still failing after 3 passes,
  **stop and report the residual errors** — don't ship broken.
- **Reviewer pass (recommended at depth).** `validate` checks *shape*, not *teaching quality*. For a
  large or high-stakes course, after `ok:true` dispatch **one read-only reviewer subagent** over the
  authored files to catch what the validator can't: objectives not actually covered by a material,
  quiz distractors that aren't plausible misconceptions, a capstone that doesn't combine ≥2 modules,
  rubric levels that aren't observable, lessons that lead with the answer instead of a predict-then-
  read beat. It **reports**; the main thread applies fixes and re-`write`s. Keep it read-only — it
  never edits course files itself.
- Once `ok`, the course appears at `/courses/<slug>` immediately (the hub reads disk per request).

### 5. (Optional, gated, ⚠️ local) NotebookLM enrichment
Preflight first (`which nlm` + an auth check), like `notebook-init`/`audio-series`. If
available and the user wants it, hand off to those skills, then record `"notebook_id": "<id>"`
(+ `artifact`) on a `notebooklm` material. **Confirm before any `nlm` write**; if auth lapsed,
tell the user to run `nlm login` — don't retry. The course is complete without this.

## Pedagogy — what makes a generated course actually teach

- **Objectives** must start with an **observable Bloom's verb** (define, describe, distinguish,
  compare, apply, analyze, evaluate, design, build…). **Banned:** understand, know, learn about,
  be familiar with, appreciate, grasp. Every objective must be assessable by ≥1 material in its
  lesson.
- **Lesson skeleton** (default shape for each `lessons/<id>.md`): *Hook / why it matters →
  Core explanation (plain language, define jargon on first use) → **Worked example** (a concrete
  instance reasoned through step by step) → **⚠️ Common mistakes** (1–3 misconceptions + the
  correction) → Check-for-understanding (1–2 self-quiz prompts; a "predict, then read on" line
  before any diagram/result) → What to take away.* Don't start the file with `# Title` (the hub
  shows it already).
- **Sequencing:** build prerequisites first; each lesson after the first opens with a one-sentence
  callback to the prior idea. **Every course ends with a `capstone` material** (a rubric-assessed
  synthesis project) that combines objectives from ≥2 modules — this is now a first-class material
  type, not just a note in a lesson.
- **Retrieval & spacing:** lean on retrieval (quizzes/flashcards/self-explanation) over re-reading.
  Put a short **cumulative/interleaved** review at each module boundary and make the final
  assessment cumulative. *(Course quizzes DO feed the hub now: they play in the in-hub quiz player,
  advance per-course SM-2, and surface in the course's own "what to do next" — you may write copy
  that says "re-take this quiz when it's due." Two honesty caveats: the **global** Review-next queue
  + daily study plan still exclude courses, so don't claim course quizzes show up on the cross-hub
  review page; and a project/capstone rubric is **self-assessment**, not auto-graded — don't imply
  the hub scores the learner's work.)*
- **Quizzes:** include a difficulty spread — at least one **application/scenario** question, not
  only recall. Each distractor encodes a plausible misconception, and its rationale names why a
  learner would believe it. Tag `purpose` formative (per-lesson practice) vs summative
  (end-of-module).
- **Flashcards:** atomic (one idea per card); prefer retrieval prompts ("Why does X fail?") over
  recognition; the front must not leak the answer; cover the objectives, not just vocabulary.
- **Projects, capstones & rubrics (M3):** a `project`/`capstone` is an open-ended *build* — a
  deliverable the learner produces, not a quiz. Shape it as **The task → What a strong result looks
  like (read after attempting) → Self-assess** (see contract.md). Give it a **rubric** (`rubrics/
  <id>.json`): **3–4 criteria** tied to the objectives it exercises, each with **3 observable
  levels** (worst→best) describing what you'd *see* in the work, never "understands X." A `capstone`
  must combine objectives from **≥2 modules**; a mid-course `project` can be single-module. Because
  the rubric is **self-assessment**, write the levels so a learner can honestly place their own
  work — concrete, checkable, non-flattering.
- **Level contract** — make `level` actually change the output:
  - **Beginner** — assume no prior knowledge; define all jargon; more worked examples; recall-
    heavy quizzes; shorter lessons.
  - **Intermediate** — assume fundamentals; fewer definitions; application-heavy quizzes; include
    exercises.
  - **Advanced** — assume working knowledge; terse; emphasize edge cases, trade-offs, a
    substantial capstone; analysis/evaluation-level objectives + questions. State assumed
    `prerequisites` explicitly.

## Environment & failure handling

- **Preflight = the `scaffold` call in §3 step 1** (run it before dispatching subagents). If it
  errors with a **permission/filesystem error** (a cloud session can't write `COURSES_DIR`),
  don't fan out to disk — author every file **inline in chat**, clearly labeled by path, and tell
  the user to set a writable `COURSES_DIR` and re-run to persist. If `.venv` is missing →
  `make setup`; if that fails, report it.
- **Slug already exists** (`scaffold` → `FileExistsError`): stop and ask via `AskUserQuestion` —
  *new slug* (suffix `-2`) / *update the existing course in place* / *cancel*. To **update in
  place**, skip `scaffold` (the dir exists): re-author the changed material files, then
  `… cli write --slug <existing> --from-file <manifest.json>` — it overwrites `course.json` and
  re-validates. ⚠️ Stale material files from the prior version are **not** auto-removed; delete any
  file the new manifest no longer references so the dir matches the manifest. **Never** hand-create
  the dir to route around the bridge.
- **Partial fan-out:** reconcile returned `{path,…}` lists against the id map; re-dispatch only the
  modules whose files are missing — never re-run completed ones.

## Guardrails

- **Never invent facts, quotes, or citations.** `reading` URLs render as live links (`validate`
  only checks the scheme is http(s), not that the page exists) — only include a URL you can
  attribute to a real, stable source (prefer canonical pages / DOIs; the renderer now keeps
  balanced parens like `…_(disambiguation)`); if unsure, **verify with `WebFetch`/`WebSearch` or
  omit the `url`** and put the citation in `note`.
- **One approval gate** (the syllabus); after it, generate without per-file prompts (propose
  defaults, proceed) but surface what you built.
- **Validate AND self-check before done.** A course that fails `validate` (or has a quiz with ≠1
  correct option) must not be declared finished.
- **Stay out of the NotebookLM sidecars**; the bundled `backend/app/courses/examples/` are
  read-only references — write only under `COURSES_DIR`. A user slug that matches a bundled
  example **shadows** it; use unique slugs (`… cli list` shows what exists).
- **Set rendering expectations** when reporting: diagrams still display as mermaid **source** (a
  rendered graph is a later enhancement) — always convey the same idea in the lesson prose too.
  Quizzes **are** playable in-hub now (M2) and projects/capstones get a **self-assessment rubric**
  (M3); a course's "what to do next" panel surfaces due reviews + the next lesson + un-assessed
  projects — so you *can* tell the user learners take quizzes and self-assess projects today.
- **Cloud vs local:** authoring files + the manifest is ✅ cloud-safe; saving to disk needs a
  filesystem; NotebookLM enrichment needs `nlm` (⚠️ local). Say so if a step can't run here, and
  still deliver everything that can.
