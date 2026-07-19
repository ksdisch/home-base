# Phase 7 — Courses M5: the authoring loop in the hub

_The fifth and FINAL course-pipeline milestone (see `docs/COURSE_PIPELINE_SPEC.md`). M1 made
courses readable + trackable; M2 made practice playable; M3 added depth (projects/rubrics +
the course next-up); M4 joined NotebookLM enrichment. M5 closes the spec's last line —
"regenerate this lesson, edit objectives, reorder modules from the UI; export/share a course" —
which required revising the epic's founding rule that the hub never writes a course file.
Kyle gated that revision with an explicit three-question decision before any design
(2026-07-18), then picked approach A from the explore-plan._

## The insight — the validator was always the gate; the writer just becomes a library

The epic's safety never actually lived in "the backend has no write path" — it lived in
`validate_dir` plus the CLI's write→validate→rollback transaction. M5 extracts that
transaction into `app/courses/writer.py` (the CLI delegates to it, so there is STILL exactly
one writer) and points the new endpoints at it. Every edit — human or model-generated — lands
only if the whole course still validates; otherwise the files come back byte-identical and the
errors surface. A bad LLM output cannot corrupt a course by construction.

## Design decisions (don't relitigate)

- **Kyle's three gates (2026-07-18):** (1) write path = the API imports the CLI's transactional
  machinery in-process (no subprocess bridge, no queue-for-a-skill); (2) scope = all four spec
  features; (3) migration-ledger hardening stays out of M5 (it then shipped independently as
  PR #52).
- **Per-op endpoints, not a generic manifest PUT** (approach A over B): each edit is small and
  tightly validated server-side. A whole-manifest endpoint would hang identity preservation on
  a server-side diff — the exact place a bug silently orphans progress.
- **Editing requires an existing user copy** (`writer.user_course_dir`, escape-proof): bundled
  examples are a 409 and `editable:false` on the API, so the UI never offers a doomed edit.
  NotebookLM sidecars are a different tree and were never reachable.
- **Raw-manifest round-trip:** edits mutate the raw `course.json`, not the normalized load, so
  authored fields the loader doesn't model survive. `pin_ids` materializes the loader's
  positional fallback ids — exactly (an oracle test compares against `load_manifest`) — before
  any reorder, so `course_lesson_progress` rows and the `course:<slug>` material-path stats
  can never re-key.
- **Reorder is a complete bijection:** every module id exactly once, and per module every one
  of its current lesson ids exactly once; any mismatch is a 422 with nothing written.
  Cross-module moves are out of scope.
- **Two failure idioms:** bad addressing / rejected permutations → 4xx; validation failures →
  200 `ok:false` + errors with byte-identical rollback (the caller needs the structured
  errors, and the course is safe either way).
- **Regeneration rides the chat.py lane exactly** (subscription billing, `ANTHROPIC_API_KEY`
  scrubbed from the child env, no tools, injectable `runner` test seam) with per-type output
  contracts (bare markdown / mermaid / strict JSON; fence-strip + JSON re-dump), a 300s
  timeout, `COURSE_REGEN_MODEL` (default sonnet), and a `course-regen.jsonl` row for every
  run — success, rollback, or failure (the cost was paid either way). One material per call;
  the UI sequences multiple. Regenerating a deck/quiz RESETS the replaced items' SM-2/attempt
  stats by design (identity is content/path-keyed) — the UI warns before confirming.
- **Regenerable types** = lesson · exercise · diagram · flashcards · quiz. Project/capstone
  (rubric-coupled) and the no-file types (reading/notebooklm) are excluded in v1.
- **Export is read-only** (in-memory zip, hidden files skipped) and works for bundled examples
  too — it doubles as the safety valve before a risky edit.

## What shipped

1. **courses/writer.py** — `user_course_dir` (the editable guard), `write_manifest` (the
   transactional core, extracted from `cli.cmd_write`), `edit_manifest` (raw round-trip),
   `write_material` (replace-only; file + manifest snapshot; count sync), `pin_ids`.
2. **courses/cli.py** — `cmd_write` delegates to the writer: one write path, two callers.
3. **courses/regen.py** — `CourseRegenClient` (the chat.py mirror), the per-type prompt
   builder + `extract_content`, `append_regen_ledger`.
4. **api/courses.py** — `PUT …/lessons/{id}/objectives`, `PUT …/order`,
   `POST …/lessons/{id}/regenerate`, `GET …/export`; the `_editable_course` front door
   (404/422/409); `editable` merged onto summary + detail; the header docstring now states the
   narrow writer exception instead of the retired "hub never writes" absolute.
5. **models.py / config.py / deps.py** — the M5 request/response models;
   `course_regen_model` + `course_regen_ledger`; `get_course_regen_client`.
6. **frontend** — `types.ts`/`client.ts` mirror (incl. the client's first `put` helper and
   `courseExportUrl`); CourseDetail edit mode: objectives editor (one per line), module/lesson
   ↑/↓ reorder (optimistic apply + revert on failure), per-material Regenerate panel (optional
   guidance, stats-reset warning, honest minute-plus busy state), always-on Export button.
7. **tests** — `test_courses_writer.py` (14: byte-identical rollback, escape/bundled
   refusals, the pin_ids↔loader oracle), `test_courses_edit.py` (8: progress preserved across
   moves — including on a fallback-id course — plus bijection rejections),
   `test_courses_regen.py` (10: prompt contract, fence-strip, count sync, invalid-output
   rollback, ledger rows, lane guard), `test_courses_export.py` (5: zip round-trip, bundled
   export, editable flags). Backend **493** (was 456), frontend **66** (was 62), ruff clean.

## Honest limitations / out of scope

- Cross-module lesson moves; copy-on-write editing of bundled examples; zip **import**;
  title/summary editing; regenerating project/capstone/rubrics; concurrent-edit locking
  (single-user app — last write wins).
- An edit to a course with pre-existing validation errors bounces (`ok:false`) until the
  underlying problem is fixed on disk — deliberate: the writer never blesses a broken course.
- Regeneration quality rides the model; validation catches structure, not pedagogy. The
  guidance field and the rollback loop are the levers.
