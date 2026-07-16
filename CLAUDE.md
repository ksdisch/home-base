# CLAUDE.md — Home Base

> **Home Base** (renamed from `learning-hub` on 2026-07-13): evolving into Kyle's daily home
> base — self-updating morning brief + inline notes, with the Learning Hub as the learning
> section. Source of truth: `docs/KICKOFF-home-base.md`. Current milestone: **M2 — full
> roster + notes** shipped (`docs/M2_PLAN.md`): config-file roster `sweeps/topics.json`
> (8 topics, manual pause flags), read-time item ids + inline notes (`brief_notes` v5,
> browsable at `/notes`), "Your learning" strip on Today. M1 record: `docs/M1_PLAN.md`.
> **M0's grading week continues in parallel** — grade daily in `docs/M0-sweep-grades.md`
> (Kyle overrode the "no UI until M0 passes" gate for M1 on Day 0, M2 on Day 1, and **M3 on
> 2026-07-15** — deliberate, in writing; the go/no-go still rides on the 3 pilot topics).
> **M3 — hands-off** is now in progress (`docs/M3_PLAN.md`): launchd scheduler + on-wake
> catch-up, read-time `developing` dedup labels, and a cost/usage ledger — built on
> `feat/m3-hands-off`; Kyle installs the schedule when ready. Next: finish the grading week +
> the M0 verdict (~2026-07-19).
> Riskiest assumption: sweeps stay accurate/trustworthy enough to sustain the morning habit.

## Master plan upkeep (required)

[`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) is the **living unified view** of both arcs'
plans — checklists + a Kanban board. **Any session that starts, completes, or reshapes a
plan item MUST update it in the same commit/PR as the work**: tick/untick the checkbox,
move the Kanban card, and touch its "Last updated" line. New milestone/plan docs get added
to its checklist, board, and doc map. The detailed per-phase docs stay authoritative for
*how* things were built; MASTER_PLAN.md is authoritative for *status*.

## Claude tooling for this repo

These slash commands and skills are vendored into `.claude/` so they work in cloud/web
sessions and for collaborators, not just on the original author's machine.

Legend: ✅ cloud-safe · 💻 local-only (needs a browser/screenshots/dev server — won't run
in cloud/web sessions) · ⚠️ needs the `nlm` CLI + NotebookLM auth (runs locally; in a cloud
session only if `nlm`/MCP is configured there).

### Commands (`.claude/commands/`)

| Command | What it does |
|---|---|
| ✅ `/begin` | Open a session — orient on branch, recent commits, open PRs, last `/wrap` recap. |
| ✅ `/wrap` | End-of-session recap + active-recall quiz, saved to a dated log file. |
| ✅ `/explore-plan` | Explore → plan → confirm before writing any code (2–3 ranked approaches). |
| ✅ `/tdd` | Test-first loop: write failing tests, confirm, then code until green. |
| ✅ `/handoff` | Generate a paste-ready handoff prompt for a fresh Claude Code session. |
| ✅ `/trim-context` | Find/fix CLAUDE.md + memory "token bloat" in the repo. |
| ✅ `/autonomous-milestone` | Autonomously plan/build/test a milestone, or triage the backlog (ultracode multi-agent). |
| ✅ `/build-course` | Plan-then-autonomous course creation — propose a syllabus, then author lessons/diagrams/flashcards/quizzes into a hub course (thin entry to `course-builder`). |

### Skills (`.claude/skills/`)

| Skill | What it does |
|---|---|
| ✅ `episode-review` | Post-episode review-and-quiz workflow for a Learning Hub audio overview; logs score + listened status. |
| ✅ `artifacts-audit` | Audit the repo → plan canonical engineering artifacts (writes `docs/artifacts-plan.md`). |
| ✅ `artifacts-generate` | Generate artifacts (READMEs, ADRs, runbooks, …) from the audit plan. |
| 💻 `match-the-mock` | Implement a UI to match a mock and iterate via screenshots — needs a browser + running dev server. |
| ⚠️ `nlm-skill` | Expert guide to the `nlm` CLI / NotebookLM MCP — the backend shells out to `nlm`. |
| ⚠️ `notebook-init` | Initialize a new NotebookLM notebook end-to-end. |
| ⚠️ `notebook-assist` | Refine / brainstorm / manage sources for an existing NotebookLM notebook. |
| ⚠️ `audio-series` | Generate an episodic NotebookLM audio series for a notebook. |

#### Repo-specific skills (scaffolded via `/claudify-repo` brainstorm)

| Skill | What it does |
|---|---|
| ⚠️ `youtube-breakdown` | Turn a YouTube transcript/URL into a 4-mode breakdown (Study Notes / Quick Reference / Critique / Actionable Insights), then save it as a local note, register it as a hub custom topic, or add it to a notebook as an `nlm` source. The breakdown works anywhere; saving + the `nlm` bridge are local. |
| 💻 `review-next` | Read the hub's SQLite store (attempts, mastery, reflections) and rank "what to review next." Read-only; needs the local store (or the `learning-hub-db` MCP). |
| 💻 `catalog-doctor` | Reconcile the parsed catalog ↔ sidecars ↔ live `nlm studio status` and report drift. Read-only; needs the sidecars, `nlm`, and the running backend. |
| ✅ `api-types-sync` | Reconcile `frontend/src/api/types.ts` (+ `client.ts`) with the backend Pydantic models in `backend/app/models.py` + the routers — fix the hand-synced contract after a model change. Frontend-only edits; ends with `make typecheck`. The read-only `contract-reviewer` agent finds the drift; this skill fixes it. |
| ✅ `course-builder` | Plan-then-autonomous **course** creation: propose a syllabus, then author written lessons + mermaid diagrams + flashcards + hub-shaped quizzes + reading as a course sidecar the hub reads (`app.courses`). Authoring is cloud-safe; saving to disk + optional NotebookLM enrichment are local. See `docs/COURSE_PIPELINE_SPEC.md`. |

### Subagents (`.claude/agents/`)

| Agent | What it does |
|---|---|
| ✅ `test-writer` | Write/extend `backend/tests/` pytest in the house style — `TestClient(app.main)`, per-test isolated SQLite via env, synthetic sidecars via `conftest.write_notebook`, never the real `nlm`/sidecar root. Favours the suite's adversarial + answer-key-free-oracle edge cases. |
| ✅ `contract-reviewer` | Read-only review for backend↔frontend contract drift (`models.py`/routers ↔ `types.ts`/`client.ts`) — field presence, type mapping, optionality, router wiring, and the quiz answer-key-free invariant. Reports findings; `api-types-sync` applies them. |

### Hooks (`.claude/settings.json`)

| Hook | What it does |
|---|---|
| ✅ `guard-sidecars` | PreToolUse on Edit/Write/MultiEdit/NotebookEdit — **blocks** any write under `$NOTEBOOKLM_ROOT` (default `~/Projects/NotebookLMs`), enforcing the read-only-sidecar invariant (`backend/tests/test_no_sidecar_writes.py`) at the agent layer. Script: `.claude/hooks/guard-sidecars.sh`; fails open (allows) on any parse error so it never breaks normal edits. |

### MCP servers (`.mcp.json`)

| Server | What it does |
|---|---|
| 💻 `learning-hub-db` | SQLite MCP (`uvx mcp-server-sqlite`) over the hub's store at `backend/data/learning-hub.sqlite`, so Claude can inspect attempts/mastery/custom_topics. Requires `uv`/`uvx`; the DB file is created on first `make dev`. The store is local, so it won't connect in cloud sessions. |

> Vendored / scaffolded via `/claudify-repo`. To refresh a vendored tool to its latest global
> version, re-run that command and re-port it. The `custom_topics` CLI writer that
> `youtube-breakdown` uses is built (`backend/app/topics/custom.py`); surfacing custom topics on
> the hub home remains Phase-5 UI work (see `BACKLOG.md`).

## Operating Constraints

@.claude/operating-constraints.md
