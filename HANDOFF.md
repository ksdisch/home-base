# HANDOFF.md

_Last updated: 2026-07-26_

## What was just done
- `/replenish` 2026-07-26 (branch `docs/replenish-2026-07-26`): the dry backlog refilled — 24 verified bugs (report: `docs/bug-hunt/2026-07-26-post-studycal-m8.md`; 3 high, incl. a live phantom topic card on every audio morning and the studycal token-expiry facade due ~07-29) + 17 idea survivors captured as `docs/ideas/` vision docs + `BACKLOG.md ## Open` stubs. Awaiting wave sequencing via `/backlog-hygiene`.
- Project wiki initialized (this file, `PROJECT.md`, `Sources.md`, `Decisions.md`, `Wiki/`) via the project-wiki skill, landed on `docs/wiki-init`.
- In-flight: `feat/brief-archive-nav` carries 2 commits not yet on main — brief archive entry point + index page (`c0d8455`) and audio on archived days (`fe53288`).
- Last merged work: PR #144 (2026-07-22) — topic↔course cross-links on both card types + course quizzes folded into the daily `/study-plan`. Backend 748 / frontend 193 tests green.

## Where things stand
Both arcs are fully built and gated (see `docs/MASTER_PLAN.md` for the authoritative status view). Learning Hub: Phases 1–7, Courses M1–M5, and the Learning Paths vertical slice are live on the prod hub. Home Base: M0–M7 shipped; M0's grading week closed 2026-07-19 with a PASS verdict. The moonshot queue is empty; current work is incremental polish (brief archive navigation).

## Immediate next move
Finish and land `feat/brief-archive-nav` — it's 2 commits ahead of main with no PR yet; landing it clears the only in-flight code work.

## Open questions / blockers
- ~~CI red for every PR (news-scout date time-bomb)~~ **Resolved** (Fact): fixed on main by `700cc3e` — `_seed_quantum_events` now seeds click events relative to the real clock; `tests/test_news_scout.py` verified green locally 2026-07-26 (16/16).
- M6 phone-side proof needs Kyle's eyes-on trio: standalone install, airplane banner, iOS scrub (Mac-side and tailnet-reach verification are done).
- ~2026-08-03 v1 success-criteria check (≥5 mornings/week · events reach Kyle first · ≥3 notes/week) — calendar-gated, not blocked.
- Riskiest assumption (per `CLAUDE.md`): sweeps stay accurate/trustworthy enough to sustain the morning habit; ~2026-08-19 re-grade scheduled.

## Files touched recently
- `PROJECT.md`, `HANDOFF.md`, `Sources.md`, `Decisions.md`, `Wiki/_index.md`, `Wiki/Architecture.md` — wiki init (this change).
- `CLAUDE.md` — Project Wiki section appended.
- Brief archive work on `feat/brief-archive-nav` (frontend brief routes + backend archive endpoints) — the in-flight feature.
