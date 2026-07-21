# Milestones the habit strip finally notices

**Status:** Idea — not committed. Added by `/brainstorm` (Delight mode) on 2026-07-20.

_The Today habit strip already holds Kyle's full multi-week history but renders it as flat text ("3 of 5 mornings · 1 of 3 notes this week"); this makes it mark the real, earned milestones sitting in that data — a run of on-target weeks ("· 3 weeks running"), a personal-best week ("· best week yet"), the moment a count reaches its target (the fraction goes teal + `✓`), and round mornings-with-Home-Base totals ("☀ 100 mornings") — each bound to a verified threshold so it can never fire on a partial or stale number._

## Premise

`frontend/src/components/HabitStrip.tsx` fetches `brief_habit` — a zero-filled per-week history of `{week_start, mornings, notes}` — and already derives `current` and `previous` client-side, then prints them as plain text. The milestones the ritual actually produces (streaks, personal bests, the target-hit moment, lifetime mornings) all sit in that array, unmarked. This adds small client-side derivations and marks each milestone in the existing line using the app's own `✓` ack idiom — no new row, no confetti — so the daily ledger becomes a companion that notices Kyle kept showing up.

**Why now:** the habit strip is the read surface for the kickoff's v1 success check (≥5 mornings/week, ≥3 notes/week), judged ~08-03 — so a milestone that finally lands rewards exactly the behavior the project is measured on, and it's pure presentation over data already in hand.

## The bet

That a celebration is only delightful if it's *trustworthy* (A2): every marker is bound to a verified, re-derivable threshold — `mornings >= target` for the hit, a strict `>` over `>=2` prior weeks for a best, consecutive on-target weeks for a streak — so it can never fire on a partial, stale, or premature number. Earned, not generous. A veteran who's opened Today every morning for a month gets the single nod that log was quietly owed. The risk the bet accepts: too many markers turn a calm strip into a scoreboard, so at most one or two fire at once and the default line stays byte-for-byte today's when nothing is earned.

## Decisions / open questions

1) Which milestones ship in v0 — all four (streak, best week, target-hit, lifetime mornings) or just the streak + target-hit? 2) Do multiple earned markers stack on one line, or does one take precedence? 3) Round mornings-thresholds: which numbers (25/50/100), and is a once-only localStorage ack enough or does it need to survive a cache clear? 4) Does hitting the notes target deserve the same `✓` as mornings, or is mornings the primary ritual? 5) Should a broken streak ever be acknowledged, or only positive milestones (honesty vs. nagging)?

## Credible first step

In `HabitStrip.tsx` (L56-68), add `consecutiveOnTarget(weeks)`, `isBestWeek(weeks)`, and `totalMornings(weeks)` helpers over the already-fetched array, and render conditional `text-accent` spans / a trailing `✓` on the current-week line when a threshold is genuinely crossed; persist a once-only flag for the lifetime-mornings milestone in localStorage. One sitting, zero backend — the data is already served.

## Dependencies

`frontend/src/components/HabitStrip.tsx` (the `weeks`/`current`/`previous` derivation + the current-week `<p>`); the existing `brief_habit` payload (no shape change). Reuses the `✓` ack vocabulary already used at `Noted ✓` / `✓ Saved`. No backend, no API, no new store field.

## Explicitly out of scope (revisit later)

No new backend milestone table or server-computed streaks (v0 derives from the payload in hand). No animation/confetti — markers are static text in the existing line. No cross-metric badges or gamification beyond the four named milestones. No change to the sweep-trust re-grade line the strip already carries.

## Identity/positioning note

none — tethered. Reuses the existing strip, the existing `✓` idiom, and the existing data; only the acknowledgement is new.
