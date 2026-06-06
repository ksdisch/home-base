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

> Vendored via `/claudify-repo`. To refresh a tool to its latest global version, re-run that
> command and re-port it.
