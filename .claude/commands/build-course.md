---
description: Build a full multi-format course for a topic and drop it into the Learning Hub — plan-then-autonomous (propose a syllabus, get one approval, then autonomously author lessons, diagrams, flashcards, quizzes + curated reading). Thin entry point to the course-builder skill.
argument-hint: <topic> (e.g. "Postgres indexing for backend devs"); omit to be asked
---

Topic: $ARGUMENTS

Run the **course-builder** skill to create a course for the topic above (if none was given, ask
me for the topic and desired level first).

Follow the skill's **plan-then-autonomous** workflow exactly:

1. **Interview lightly** — level, rough size (modules × lessons), material mix, and whether to
   add optional NotebookLM enrichment (local-only). Propose sensible defaults; don't over-ask.
2. **Propose the syllabus and STOP for one approval** — modules → lessons → objectives →
   materials → est. time. Do not author any material until I approve/edit it.
3. **After approval, generate autonomously** — scaffold via
   `cd backend && .venv/bin/python -m app.courses.cli scaffold …`, then author every material
   (parallelize across lessons with subagents for anything non-trivial), assemble `course.json`,
   and **validate** with `… app.courses.cli validate --path data/courses/<slug>` until `ok`.
4. **Report** — the slug + where it landed (`COURSES_DIR`), the structure you built, the
   validation result, and the hub URL (`/courses/<slug>`). It shows up in the hub immediately.

Honor the skill's guardrails: never invent facts/citations, exactly one correct option per quiz
question (hub quiz shape), fix every validation error before finishing, and stay out of the
NotebookLM sidecars + the bundled `backend/app/courses/examples/` references.
