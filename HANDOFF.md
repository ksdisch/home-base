# HANDOFF.md

_Last updated: 2026-07-27_

## What was just done
- **Agent Gate gate conversation → PARKED (decision D7, docs-only PR).** The first of the four 07-26 replenish moonshots got its standing gate conversation (Overnight-gate model). Kyle's call: park Agent Gate until after the ~08-03 v1 check; the other three moonshots stay undecided with their own future gate conversations. Demand-side finding recorded in `docs/ideas/agent-gate.md` for the revisit: Claude Code crons/sessions are a sufficient first tenant — the park is timing, not demand. The vision doc's three open questions stay deliberately unanswered. No code built.
- **PR #153 — the brief archive lands, with one shared audio player.** `feat/brief-archive-nav` (archive entry point + index page `c0d8455`; audio on archived days `fe53288`) rebased onto current main and merged. Its backend suite had been red since `fe53288` (a stale test asserting the removed v1 contract, bug #4) — rewritten, plus the coverage `GET /brief/audio?date=` and `GET /brief/archive` shipped without. The branch also carried a live **dueling-narrator** bug: the archive mounted its own `<audio>` with no coordination with the FR15 shell element. Both surfaces now render one `BriefAudioCard` (folding in #20 drift, #21 pre-metadata seek, #22 latched error, #5 date-flip reload), the shell owns `isPlaying`/`pauseAudio` behind a now-playing pill, and the archive's play pauses Today's (single-track rule). Plus #23: only a real 404 may claim a morning isn't in the archive. Backend 792 / frontend 214.
- Study Scheduler correctness wave (PR #152): 8 verified bugs test-first, incl. the honest token degrade that beat the ~07-29 OAuth leash.
- `/replenish` 2026-07-26 (PR #151): the dry backlog refilled — 24 verified bugs (report: `docs/bug-hunt/2026-07-26-post-studycal-m8.md`) + 17 idea survivors as `docs/ideas/` vision docs + `BACKLOG.md ## Open` stubs.
- Project wiki initialized (this file, `PROJECT.md`, `Sources.md`, `Decisions.md`, `Wiki/`) via the project-wiki skill.

## Where things stand
Both arcs are fully built and gated (see `docs/MASTER_PLAN.md` for the authoritative status view). Learning Hub: Phases 1–7, Courses M1–M5, and the Learning Paths vertical slice are live on the prod hub. Home Base: M0–M7 shipped; M0's grading week closed 2026-07-19 with a PASS verdict. The moonshot queue is empty and there is **no in-flight code work** — every branch is landed. 14 of the 24 replenish bugs are fixed (8 studycal in #152, 6 audio/archive in #153); 10 remain, with 16 idea stubs.

## Immediate next move
Sequence the remaining replenish backlog into waves via `/backlog-hygiene` — 10 bugs + 16 ideas are queued with no ordering (the moonshot lane is now explicitly quiet until the ~08-03 verdict: Agent Gate parked, the other three undecided). The two highest-value bugs are both **HIGH severity and still open**: **#1** (a phantom `brief.chapters` error card served on every audio morning — live in production right now, and a recurring fake "this topic's sweep didn't validate" banner attacks the sweep-trust invariant the whole morning habit rests on) and **#3** (the catalog parser typing video overviews as `audio`, which voids the Designer's M0 cross-check and detonates when the Designer scales past the jlens fixture — the stated next milestone). Note the studycal token deadline (~07-29) is **no longer a forcing function**: #2 was fixed in #152.

## Open questions / blockers
- ~~CI red for every PR (news-scout date time-bomb)~~ **Resolved** (Fact): fixed on main by `700cc3e` — `_seed_quantum_events` now seeds click events relative to the real clock; verified green again post-rebase on the #153 branch 2026-07-27 (16/16).
- Test-environment note (Fact, not a bug): `test_brief_unreadable_json_degrades_to_md_fallback_not_500` and `..._md_in_fallback_...` fail in any container running as **root** — they `chmod(0o000)` a file, which root ignores. They pass in CI and on a normal user account; verified failing identically on `origin/main`.
- M6 phone-side proof needs Kyle's eyes-on trio: standalone install, airplane banner, iOS scrub (Mac-side and tailnet-reach verification are done).
- ~2026-08-03 v1 success-criteria check (≥5 mornings/week · events reach Kyle first · ≥3 notes/week) — calendar-gated, not blocked.
- Riskiest assumption (per `CLAUDE.md`): sweeps stay accurate/trustworthy enough to sustain the morning habit; ~2026-08-19 re-grade scheduled.

## Files touched recently
- `frontend/src/components/BriefAudioCard.tsx` (new, + tests) — the single brief player both surfaces render; `BriefShell.tsx`, `BriefArchive.tsx`, `BriefIndex.test.tsx` (new) alongside it (this change, PR #153).
- `backend/tests/test_brief_api.py` — archived-day audio contract + `/brief/audio?date=` and `/brief/archive` coverage (PR #153).
- `PROJECT.md`, `HANDOFF.md`, `Sources.md`, `Decisions.md`, `Wiki/_index.md`, `Wiki/Architecture.md` — wiki init.
- `CLAUDE.md` — Project Wiki section appended.
