---
name: catalog-doctor
description: >-
  Health-check the Learning Hub's topic catalog: run the ingestion pipeline against the
  NotebookLM sidecars, reconcile what the hub parsed against live `nlm studio status`, and
  report drift — sidecars that failed to parse, artifacts NotebookLM has that the hub doesn't
  (stale sidecar), and notebooks the hub lists but whose dir is gone. Read-only; never writes to
  the sidecars. Use when the catalog looks wrong/stale, a notebook/episode is missing from the
  hub, after generating new NotebookLM artifacts, or when the user runs /catalog-doctor.
---

# Catalog doctor — sidecar ↔ catalog ↔ nlm reconcile (read-only)

Diagnose why the hub's catalog and reality disagree. The hub builds its catalog from the
NotebookLM **sidecars** at `~/Projects/NotebookLMs/` (override: `NOTEBOOKLM_ROOT`), cross-checked
against `nlm studio status`. This skill surfaces the three drift classes and recommends a fix —
**it does not write to the sidecars or to NotebookLM.** The hub is read-only toward both.

## What "correct" looks like (see `docs/data-sources.md`)

- Each notebook is a dir `~/Projects/NotebookLMs/<alias>/` with a `README.md` (frontmatter:
  `notebook_id`, `alias`, `title`, `template`, `tags`) and an optional
  `artifacts/audio-series-artifact-map.json` (the authoritative machine map of audio /
  study-guide / quiz artifact IDs).
- The hub parses those into the catalog; `nlm studio status <notebook_id>` is the live truth for
  artifacts that may not be in the sidecar yet.

## Procedure

1. **Make sure the backend is reachable.** `curl -s localhost:8000/api/health`. If it's down,
   offer to start it (`make dev` from the repo root) or ask the user to. Most steps need it.

2. **What the hub sees.** `curl -s localhost:8000/api/catalog` → the parsed notebook roster
   (ids, aliases, titles, groups). For detail per notebook: `curl -s localhost:8000/api/topics/<id>`
   → `episodes[]`, `quizzes[]`, study guides as the hub resolved them.

3. **What's on disk.** Enumerate `~/Projects/NotebookLMs/*/` (read-only — list + read only). For
   each dir, read `README.md` frontmatter and load `artifacts/audio-series-artifact-map.json`
   if present.

4. **What NotebookLM reports (live).** For each `notebook_id`, run
   `nlm studio status <notebook_id>` and capture the artifact list. If any call returns an auth
   error, stop and tell the user to run `nlm login` — don't retry blindly.

5. **Diff into the three drift classes:**
   - **Parse failures** — a `<alias>/` dir (with a `README.md`) that is **missing from the
     catalog**, or present but missing title/episodes the README clearly lists. Likely a
     frontmatter or markdown-table parsing issue. Point at the specific file + what didn't parse.
   - **Stale sidecar** — artifacts `nlm studio status` reports that the catalog/sidecar map
     doesn't include (e.g., a newly generated quiz or episode). The hub's "Refresh (live)"
     reconcile is meant to catch these.
   - **Orphans** — a notebook in the catalog whose `<alias>/` dir or `notebook_id` no longer
     resolves (deleted/renamed/archived — e.g., a `stoicism`-style merge).

## Output

A concise health report grouped by the three classes. For each finding: the notebook, the
specific file or artifact, and **what's likely wrong**. Then recommend the fix — without doing
it:

- Parse failure → show the offending frontmatter/table snippet; suggest the sidecar edit the
  **user** (or their sidecar-authoring tooling) should make. The hub never edits sidecars.
- Stale sidecar → suggest the hub's "Refresh (live)" action, or regenerating the sidecar's
  `artifacts/audio-series-artifact-map.json` via the user's NotebookLM tooling.
- Orphan → suggest removing/merging the stale catalog reference.

If everything reconciles, say so plainly — a clean bill of health is a valid result.

## Guardrails

- **Read-only toward NotebookLM.** List/read sidecars and call `nlm studio status` (read-only);
  **never** write under `~/Projects/NotebookLMs/` and never run mutating `nlm` subcommands.
- Handle `{"kind": "NlmAuthError", …}` by telling the user to `nlm login` — don't loop.
- Parse the README tables **leniently** (they're human-authored); prefer the JSON artifact map
  where present, then fall back to the tables, then reconcile against `nlm`.
- **Local-only:** needs the sidecars, the `nlm` CLI, and the running backend — won't work in a
  cloud session.
