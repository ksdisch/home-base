# PROJECT.md

## Purpose
Kyle's daily home base: a self-updating morning brief across his topics (AI/LLMs, his teams, fantasy football, market/tech news) plus a news mode, with the original Learning Hub (NotebookLM-backed quizzes, SM-2 spaced repetition, courses, learning paths) riding along as the learning section. (Fact — `README.md`, `docs/KICKOFF-home-base.md`.)

## Scope
**In scope (current phase):**
- Arc 1 — Learning Hub: catalog, in-hub quiz player, progress/mastery, SM-2 study plan, custom topics, the full Courses pipeline (M1–M5), and Learning Paths (M8 vertical slice live).
- Arc 2 — Home Base: morning brief (M0–M3 kickoff plan) plus encores M4 (audio brief), M5 (chat with the brief), M6 (mobile/one-port serve), M7 (news mode) — all shipped.
- Ongoing: brief archive navigation (in flight on `feat/brief-archive-nav`), study scheduler refinements, bug-hunt waves.

**Out / deferred / never:**
- The hub never writes to NotebookLM sidecars (read-only invariant, enforced by the `guard-sidecars` hook and `backend/tests/test_no_sidecar_writes.py`). Generating new NotebookLM series stays in the `audio-series` skill.
- Hosting beyond the local Mac + tailnet (phone access requires the Mac running; Tailscale for reach).
- Scaling the Learning Paths Designer beyond the bundled fixture to the rest of the library — future M8 work, not started.

## Current status
Active. Both arcs' planned milestones are fully built and gated: Learning Hub Phases 1–7 + Courses M1–M5 + Learning Paths slice shipped; Home Base M0–M7 shipped with M0's sweep-quality week closed 2026-07-19 (verdict PASS, zero fabrications). Open: Kyle's phone-side M6 eyes-on trio, the ~2026-08-03 v1 success-criteria check, the ~2026-08-19 re-grade, and the in-flight brief-archive-nav branch. (Fact — `docs/MASTER_PLAN.md`, `CLAUDE.md`.)

## Next actions
1. Finish and land `feat/brief-archive-nav` (archive entry point + index page + audio on archived days — 2 commits ahead of main, not yet PR'd).
2. M6 phone eyes-on trio (Kyle): standalone install, airplane banner, iOS scrub.
3. ~2026-08-03 v1 success-criteria check: ≥5 mornings/week, events reach Kyle first, ≥3 notes/week.

## Boundaries
- Local-first: Vite + React + TS + Tailwind frontend, FastAPI backend, SQLite store; served on one port by the `com.homebase.server` LaunchAgent; phone reach via Tailscale.
- Depends on the `nlm` CLI + NotebookLM auth for live reconcile/downloads (catalog works offline; auth lapses surface as a calm banner, never a crash).
- Topic catalog source of truth = NotebookLM sidecars at `~/Projects/NotebookLMs/` (read-only); progress lives only in the hub's own SQLite store.
- LLM lanes (sweeps, brief chat, course generation) run on the Claude subscription lane with API key scrubbed, no web tools; costs tracked in a usage ledger.
- `docs/MASTER_PLAN.md` upkeep is contractually required in the same commit/PR as any plan-item change (see `CLAUDE.md`).
