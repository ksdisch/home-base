---
description: Build a full multi-format course for a topic and drop it into the Learning Hub — plan-then-autonomous (propose a syllabus, get one approval, then autonomously author lessons, worked examples, exercises, diagrams, flashcards, quizzes + curated reading). Thin entry point to the course-builder skill.
argument-hint: <topic> (e.g. "Postgres indexing for backend devs"); omit to be asked
---

Topic: $ARGUMENTS

Run the **course-builder** skill to create a course for the topic above (if none was given, ask
me for the topic and level first). Follow the skill's **plan-then-autonomous** workflow and its
pedagogy + guardrails exactly. In short:

1. **Interview lightly** — level, rough size, material mix, optional NotebookLM enrichment.
   Propose sensible defaults; don't over-ask.
2. **Propose the syllabus and STOP for one approval** — modules → lessons → objectives (observable
   Bloom's verbs) → materials → est. time → course prerequisites. Author nothing until I approve.
3. **After approval, generate autonomously** — scaffold via
   `cd backend && .venv/bin/python -m app.courses.cli scaffold …`, then author every material
   (fan out **one subagent per module**; the main thread owns ids + writes `course.json`),
   assemble the manifest, and **validate** (`… cli validate --path data/courses/<slug>`), looping
   at most 3 times; if it still fails, report the residual errors rather than shipping broken.
4. **Report** — slug + where it landed, the structure, the validation result, and the hub URL
   (`/courses/<slug>`). Note that diagrams show as mermaid source and quizzes show a question
   count (interactive player + Review-next wiring are M2) — don't say learners can take the quiz yet.

Honor the skill's guardrails: never invent facts/citations (verify or omit `reading` URLs),
exactly one correct option per quiz question, handle a pre-existing slug by asking, and stay out
of the NotebookLM sidecars + the bundled `backend/app/courses/examples/` references.
