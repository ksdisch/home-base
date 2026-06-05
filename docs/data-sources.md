# Data sources — where the catalog comes from

The hub's topic catalog is read from the **NotebookLM sidecars** the user already maintains,
cross-checked against live `nlm studio status`. This doc captures the on-disk shape so the
build doesn't have to reverse-engineer it.

## Sidecar root
```
~/Projects/NotebookLMs/
  INDEX.md                       # master index: one entry per notebook + a "Scope" note
  <alias>/
    README.md                    # the sidecar — frontmatter + sources + artifacts tables
    artifacts/
      audio-series-plan.json     # (when present) full series plan + verbatim focus prompts
      audio-series-artifact-map.json   # (when present) Ep N -> artifact IDs map
      *.md                       # generated reports etc.
```

## `INDEX.md`
Markdown list; each notebook is a bullet linking to `<alias>/README.md` with a one-line
description + date, followed by a `**Scope:**` sub-bullet. Parse it for the notebook roster,
or just enumerate the `<alias>/` directories.

## Sidecar `README.md` frontmatter (YAML)
```yaml
---
notebook_id: 594e8167-7d8e-454d-8ea9-3930080c899f   # -> NotebookLM URL + nlm commands
alias: engineering-abstractions
title: Engineering Higher Abstractions — System Design, Architecture & Judgment
template: learning-topic                             # e.g. learning-topic vs interview-prep
created: 2026-05-28
tags: [learning, engineering, system-design, architecture]
profile: default
---
```
- **NotebookLM URL:** `https://notebooklm.google.com/notebook/<notebook_id>`.
- **Grouping signal:** `template` and `tags` distinguish *Learning* vs *Interview prep*
  notebooks (interview-prep sidecars use the interview-prep template; their dirs are named
  `*-interview-prep`). Use these for the home-screen groups.

## Sidecar body (Markdown tables)
The body lists artifacts in tables with **Type · Format · Status · ID · Notes**, plus
(for notebooks with an audio series) sections like:
- **Flagship season — audio:** table of `Ep | Title | Format | Len | Status | Artifact ID`.
- **Study aids:** table mapping `Ep | Topic | Study Guide ID | Quiz ID`.
- **Standalone library:** bulleted list, each `✅ <title> — <format>/<len> — <artifact_id>`.

These tables are human-authored markdown — parse leniently. The **authoritative machine map**
(when it exists) is `artifacts/audio-series-artifact-map.json`:

```jsonc
{
  "notebook_id": "…",
  "audio":        { "1": {"id":"…","title":"Ep 1 — …"}, … },
  "study_guides": { "1": {"id":"…","title":"Ep 1 — Study Guide"}, … },
  "quizzes":      { "1": {"id":"…","title":"Ep 1 — Quiz"}, … }
}
```
Prefer the JSON map where present; fall back to parsing the README tables; reconcile both
against `nlm studio status <notebook_id>` for anything new.

## Current notebooks (snapshot at kickoff — will change; always re-read INDEX.md)
| Alias | Group | Has audio series? |
|---|---|---|
| `engineering-abstractions` | Learning | ✅ 10-ep season + 10 quizzes + 10 study guides + 14 standalones |
| `claude-power-user` | Learning | sidecar present |
| `inner-work` | Learning | sidecar present (merged Stoicism + Waking Up) |
| `stoicism` | Learning | ARCHIVED (merged into inner-work) |
| `medix-…-interview-prep` | Interview prep | single-purpose |
| `segal-interview-prep` | Interview prep | single-purpose |
| `clarity-partners-interview-prep` | Interview prep | single-purpose |
| `steame-interview-prep` | Interview prep | carries its own "Screen Ready" season |

## Suggested ingestion approach
1. Enumerate `~/Projects/NotebookLMs/*/README.md`; read frontmatter for id/alias/title/template/tags.
2. Load `artifacts/audio-series-artifact-map.json` if present; else parse the README tables.
3. (Refresh action) Call `nlm studio status <notebook_id>` to catch artifacts not yet in the sidecar.
4. Group by `template`/dir-name suffix into Learning vs Interview prep; Custom topics are hub-native.
5. Cache parsed catalog + downloaded quiz JSON locally; never write back to the sidecars.
