# CLAUDE.md — Home Base

> **Home Base** (renamed from `learning-hub` on 2026-07-13): evolving into Kyle's daily home
> base — self-updating morning brief + inline notes, with the Learning Hub as the learning
> section. Source of truth: `docs/KICKOFF-home-base.md`. Current milestone: **M2 — full
> roster + notes** shipped (`docs/M2_PLAN.md`): config-file roster `sweeps/topics.json`
> (8 topics, manual pause flags), read-time item ids + inline notes (`brief_notes` v5,
> browsable at `/notes`), "Your learning" strip on Today. M1 record: `docs/M1_PLAN.md`.
> **M0 closed 2026-07-19 — verdict PASS** (`docs/M0-sweep-grades.md`: full week graded +
> source-verified audit, zero fabrications; AI sweep prompt tuned so exclusion carries the
> same sourcing bar as inclusion. The five deliberate gate overrides are vindicated).
> **M3 — hands-off** shipped 2026-07-15 (PR #43, `docs/M3_PLAN.md`): launchd 06:00 CT
> scheduler + on-wake catch-up, read-time `developing` dedup labels, cost/usage ledger —
> first unattended fire verified clean 2026-07-16 (8/8 topics). **M4 — audio brief** shipped
> 2026-07-16 (PR #45, `docs/M4_PLAN.md`): `sweeps/audio_brief.py` renders a ~5-min Kokoro
> MP3 after every sweep (best-effort, never fails it), served at `GET /api/brief/audio`,
> 🎧 player on Today. **M5 — chat with the brief** shipped 2026-07-16 (PR #47,
> `docs/M5_PLAN.md`): "Ask about this" on every brief item — one grounded headless
> `claude -p` answer per question (subscription lane, API key scrubbed, no web tools),
> save-as-note via the existing notes API, usage ledger at `backend/data/brief-chat.jsonl`.
> **M6 — mobile** shipped 2026-07-18 (PRs #55 + #56, `docs/M6_PLAN.md`; fourth deliberate
> gate override, zero new LLM surface): FastAPI serves the built frontend on one port +
> `com.homebase.server` KeepAlive LaunchAgent (+ printed pmset wake) · sw.js v2
> cached-last-brief offline honesty (writes never queue) · bottom tab bar below `sm` +
> Today/Notes phone pass (desktop untouched) · Tailscale tailnet reach. Mac-side live
> verify clean incl. audio Range 206; real-iPhone reach verified from the phone's tailnet
> IP (PR #64) — remaining: Kyle's eyes-on trio (standalone install · airplane banner · iOS
> scrub). **M7 — news mode** shipped 2026-07-18 (PRs #58/#60/#62/#63 + polish #65–#67,
> `docs/M7_PLAN.md`; fifth gate override, zero LLM, $0 pure-RSS): Google-News-style
> second mode at `/news` — config categories (`sweeps/news_categories.json`, Local =
> Chicago/Lake Co.) → Google News RSS w/ 15-min cache · `news_events` signal log +
> card feedback · For You decaying-profile ranker (default tab, per-term search-feed
> reach, honest cold start) · topic scout → one-click adds to the Mode-A roster
> (dismiss-remembered). Next: M6 phone eyes-on proof (Kyle) + the ~08-03 v1
> success-criteria check (≥5 mornings/week · events reach Kyle first · ≥3 notes/week).
> Riskiest assumption: sweeps stay accurate/trustworthy enough to sustain the morning habit.

## Master plan upkeep (required)

[`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) is the **living unified view** of both arcs'
plans — checklists + a Kanban board. **Any session that starts, completes, or reshapes a
plan item MUST update it in the same commit/PR as the work**: tick/untick the checkbox,
move the Kanban card, rewrite its one-line "Last updated" status, and prepend a condensed
entry (dated heading + 2–4 lines) to its Changelog section. New milestone/plan docs get added
to its checklist, board, and doc map. The detailed per-phase docs stay authoritative for
*how* things were built; MASTER_PLAN.md is authoritative for *status*.

## Claude tooling for this repo

These slash commands and skills are vendored into `.claude/` so they work in cloud/web
sessions and for collaborators, not just on the original author's machine.

Legend: ✅ cloud-safe · 💻 local-only (needs a browser/screenshots/dev server or local
TTS/voice — won't run in cloud/web sessions) · ⚠️ needs the `nlm` CLI + NotebookLM auth
(runs locally; in a cloud session only if `nlm`/MCP is configured there).

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
| ✅ `/brainstorm` | Multi-mode structured brainstorm (Moonshot default) → `docs/ideas/` vision docs + backlog stubs. |
| ✅ `/claudify-repo` | Vendor global commands/skills into this repo and/or brainstorm repo-specific automations. |
| ✅ `/prompt-optimize` | One-shot prompt rewrite: workflow archetype + model + effort + ready-to-paste prompt. Advisory only. |
| ✅ `/reframe-orchestrator` | Reframe `.claude/orchestrator.md` into a mode-independent invariants & gates doc. |
| ✅ `/mock-sql-demo` | Text self-play mock SQL interview (interviewer + ideal candidate), then a debrief. |
| 💻 `/boot_server` | Detect how the project is served, start the dev server, open it in Chrome. |
| 💻 `/catchup` | Mid-session audio catch-up as an MP3 (local TTS); keeps working after. |
| 💻 `/envsetup` | Open `.env` in the editor + the credential's generation page in Chrome, key stub pre-added. |
| 💻 `/mock-sql-audio` | Full simulated SQL mock interview as an MP3 (local two-voice TTS). |
| 💻 `/mock-sql-interview` | Live voice mock SQL interview (local voice mode). |
| 💻 `/screenshot-iterate` | Visual loop: implement against a mock, screenshot the running app, compare, iterate. |
| 💻 `/smoke-test` | Manual smoke test setup: opens pages in Chrome, checklist saved under `docs/smoke/`. |

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
| ✅ `bug-hunt` | Proactive bug hunt: fan out finder agents, adversarially verify findings, ranked triage list. |
| ✅ `kickoff` | Deep discovery interview → approved kickoff brief + phased plan → scaffold a new project + GitHub repo. |
| ✅ `mini` | Kick off a new mini project under `~/Projects/mini/` (short interview + scaffold). |
| ✅ `project-guide` | Comprehensive point-in-time guide to the project (architecture, history, interview lens); dated file. |
| ✅ `research-paper` | End-of-project research paper + presenter pack from recorded results; opens a PR, never merges. |
| ✅ `seed-hunt` | End-of-project seed hunt: verify closure, harvest lessons, sweep arXiv, decision brief. |
| ✅ `ship-and-route` | Land outstanding git work behind a review gate, walk findings, route the next move. |
| 💻 `narrate` | Turn a short brief into a single-voice MP3 narration (local Kokoro TTS). |
| ⚠️ `interview-prep` | Init/maintain a NotebookLM interview-prep notebook from the local job-search dossier. |
| ⚠️ `notebook-merge` | Merge 2+ overlapping NotebookLM notebooks into one unified notebook. |
| ⚠️ `video-series` | Generate an episodic NotebookLM video series for a notebook. |

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

## Project Wiki

This project uses the project-wiki skill. When integrating new sources, recording decisions, or pausing work:
- Update `PROJECT.md` status and next actions
- Update `HANDOFF.md` with what changed and what's next
- Add durable understanding to `Wiki/` topic pages
- Record decisions in `Decisions.md`
- Keep `Wiki/_index.md` current

(`Wiki/`, `Decisions.md`, and `Sources.md` are created on first need — templates live in the skill.)

Invoke the `project-wiki` skill when wiki updates are needed.
