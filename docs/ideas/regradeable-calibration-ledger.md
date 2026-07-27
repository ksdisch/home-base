# Re-gradeable calibration ledger: a resweep can't freeze a wrong self-grade forever

**Status:** Idea — not committed. Added by `/replenish` (Harden lane) on 2026-07-26.

_Harden lane; bug-hunt independently verified a second defect in the same ledger (report #9, concurrent-append duplicates) — treat as one calibration-integrity theme._

_build_calibration in backend/app/sweeps.py grades yesterday's wagers against today's 06:00 items and appends immutable rows keyed by (day, slug, headline); once a key is in the `graded` set, `if ... in graded: continue` skips it permanently. When Kyle resweeps from the phone at 08:00 (a shipped feature), today's <slug>.json comparator files are rewritten — and if the resweep now carries the wagered story, the ledger has already recorded a wrong MISS that never re-checks, silently corrupting Brier, hit rate, and the 'Yesterday's calls' strip. Guard: make _read_ledger keep the LAST row per key; in build_calibration recompute any key whose comparator files are still readable inside _DEDUP_LOOKBACK_DAYS, appending a superseding row (with a revises_resolved_at field) ONLY when the outcome flips — append-only file stays append-only. One pytest that grades a fixture day, rewrites the comparator day's JSON, re-serves, and asserts the corrected outcome._

## Premise

The 'Yesterday's calls' numbers stay true after Kyle resweeps, so the one honesty gauge on the brief measures reality instead of a stale snapshot — the self-grader earns the trust the habit is staked on.

**Why now:** Resweep-from-the-phone is shipped and used; every phone resweep that lands the wagered story is a permanent mis-grade accumulating in calibration.jsonl right now. The Calibrated graded week rides the ~08-19 re-grade, so a corrupted ledger poisons the very verdict that decides whether the strip drops its trial label.

## The bet

That Calibrated Doubt is the trust instrument Assumption 1 leans on — a self-grader that is silently wrong is worse than no self-grader, because it launders a fabricated verdict as a measured one. The row already stores its `comparator` day; nothing ever re-reads it against the file that may have changed underneath it. A veteran sees the collision instantly: an immutability assumption baked in before resweep existed, now shipping alongside a feature that rewrites exactly the files the grade depends on.

## Decisions / open questions

(1) Recompute window = _DEDUP_LOOKBACK_DAYS, or a tighter same-day-only window since resweeps are same-day? (2) Should the "Yesterday's calls" strip visibly mark a revised grade? (3) Fix report-bug #9 (concurrent duplicate appends) in the same PR since both touch _read_ledger semantics?

## Credible first step

backend/app/sweeps.py: _read_ledger (line 433) keeps last-per-(day,slug,headline); build_calibration (lines 480-560) recomputes keys whose comparator files still resolve inside _DEDUP_LOOKBACK_DAYS and appends a revises_resolved_at row on flip; one test in backend/tests grading a fixture, rewriting the comparator JSON, and asserting the correction.

## Dependencies

backend/app/sweeps.py _read_ledger + build_calibration, calibration.jsonl (append-only stays append-only), the ~08-19 re-grade rides on this being true.

## Explicitly out of scope (revisit later)

No retroactive rewriting of historical rows (supersede-by-append only), no changes to the wager prompts or the frozen render path.

## Identity/positioning note

none — tethered.
