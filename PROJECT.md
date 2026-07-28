# PROJECT.md

## Purpose
Kyle's daily home base: a self-updating morning brief across his topics (AI/LLMs, his teams, fantasy football, market/tech news) plus a news mode, with the original Learning Hub (NotebookLM-backed quizzes, SM-2 spaced repetition, courses, learning paths) riding along as the learning section. (Fact — `README.md`, `docs/KICKOFF-home-base.md`.)

## Scope
**In scope (current phase):**
- Arc 1 — Learning Hub: catalog, in-hub quiz player, progress/mastery, SM-2 study plan, custom topics, the full Courses pipeline (M1–M5), and Learning Paths (M8 vertical slice live).
- Arc 2 — Home Base: morning brief (M0–M3 kickoff plan) plus encores M4 (audio brief), M5 (chat with the brief), M6 (mobile/one-port serve), M7 (news mode) — all shipped.
- Ongoing: study scheduler refinements, bug-hunt waves. (Brief archive navigation landed as PR #153; archive search as PR #167.)

**Out / deferred / never:**
- The hub never writes to NotebookLM sidecars (read-only invariant, enforced by the `guard-sidecars` hook and `backend/tests/test_no_sidecar_writes.py`). Generating new NotebookLM series stays in the `audio-series` skill.
- Hosting beyond the local Mac + tailnet (phone access requires the Mac running; Tailscale for reach).
- Scaling the Learning Paths Designer beyond the bundled fixture to the rest of the library — future M8 work, not started.

## Current status
Active. Both arcs' planned milestones are fully built and gated: Learning Hub Phases 1–7 + Courses M1–M5 + Learning Paths slice shipped; Home Base M0–M7 shipped with M0's sweep-quality week closed 2026-07-19 (verdict PASS, zero fabrications). Open: Kyle's phone-side M6 eyes-on trio, the ~2026-08-03 v1 success-criteria check, and the ~2026-08-19 re-grade (brief-archive-nav landed as PR #153). **All four 07-26 moonshots are now dispositioned at their gate conversations (2026-07-27):** Agent Gate PARKED (D7, revisit after the ~08-03 verdict), The Session Note PARKED (D9, revisit at ~6 months of `brief_notes`, ~2027-01), The Correspondence PARKED (D10, no peer will run a node), and **Free-Inference Rebuild GO (D8)** on its graded bake-off only — plan written to `docs/LOCAL_READER_BAKEOFF_PLAN.md` and awaiting Kyle's approval, no code written. (Fact — `docs/MASTER_PLAN.md`, `CLAUDE.md`, `Decisions.md`.)

## Next actions
1. **Kyle, on the Mac (D8): author the bake-off gold sets, then run the 7-day graded week.** The plan is approved (approach A) and `sweeps/local_reader_bench.py` is built and tested; only the Mac can produce a verdict, since the corpus is gitignored. Assumption 2 stays uncrossed until the week passes and a second decision ships a lens.
2. Sequence the remaining replenish backlog into waves via `/backlog-hygiene` — and have it **re-derive the bug count**, which is stale everywhere in these docs (the former top two, #1 and #3, landed 2026-07-27 as PRs #154 and #156).
3. M6 phone eyes-on trio (Kyle): standalone install, airplane banner, iOS scrub.
4. ~2026-08-03 v1 success-criteria check: ≥5 mornings/week, events reach Kyle first, ≥3 notes/week — its verdict also gates the Agent Gate revisit (D7).

## Boundaries
- Local-first: Vite + React + TS + Tailwind frontend, FastAPI backend, SQLite store; served on one port by the `com.homebase.server` LaunchAgent; phone reach via Tailscale.
- Depends on the `nlm` CLI + NotebookLM auth for live reconcile/downloads (catalog works offline; auth lapses surface as a calm banner, never a crash).
- Topic catalog source of truth = NotebookLM sidecars at `~/Projects/NotebookLMs/` (read-only); progress lives only in the hub's own SQLite store.
- LLM lanes (sweeps, brief chat, course generation) run on the Claude subscription lane with API key scrubbed, no web tools; costs tracked in a usage ledger.
- `docs/MASTER_PLAN.md` upkeep is contractually required in the same commit/PR as any plan-item change (see `CLAUDE.md`).
