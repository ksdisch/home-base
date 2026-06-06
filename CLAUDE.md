# CLAUDE.md — Learning Hub

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

### MCP servers (`.mcp.json`)

| Server | What it does |
|---|---|
| 💻 `learning-hub-db` | SQLite MCP (`uvx mcp-server-sqlite`) over the hub's store at `backend/data/learning-hub.sqlite`, so Claude can inspect attempts/mastery/custom_topics. Requires `uv`/`uvx`; the DB file is created on first `make dev`. The store is local, so it won't connect in cloud sessions. |

> Vendored / scaffolded via `/claudify-repo`. To refresh a vendored tool to its latest global
> version, re-run that command and re-port it. Pending follow-up: the `custom_topics` CLI writer
> that `youtube-breakdown` registers topics through (see `BACKLOG.md`).
