# The Grading Week Was an Inspection, Not a Warranty

**Status:** Idea — not committed. Added by `/brainstorm` (Premortem mode) on 2026-07-19.

_Sweep trustworthiness rests entirely on a single graded week (M0, which closes today 2026-07-19); nothing after it re-checks accuracy against sources on any cadence, so prompt rot, source-markup changes, or a model update degrade sourcing silently until Kyle personally catches a fabrication on a morning that matters and quietly stops trusting — then opening — the brief._

## Premise

M0 earned trust rigorously — a week of A–F grading plus a source-verified audit — but that rigor was a gate, not a running practice. Twelve months of unattended sweeps on the same prompts will drift, and nothing is watching. This adds a recurring trust-sampling instrument that outlives the one-time grading week: a monthly manual re-grade against the M0 rubric, logged to docs/sweep-trust-log.md, with the last-grade date surfaced right where Kyle already sees his habit stats. It deliberately does NOT automate the judgment (that would be a new LLM surface, assumption 4) — it makes human neglect visible so a silent accuracy decay can't hide behind a healthy-looking visit count.

**Why now:** The M0 grading week ends 2026-07-19 (today) with a PASS and a prompt tuned off its back (docs/M0-sweep-grades.md); every morning from tomorrow runs on prompts nothing re-audits. The ~08-03 v1 success check measures habit adherence — but habit is downstream of the accuracy this instrument watches, and there is currently no scheduled re-grade, sampling audit, or trust signal anywhere in sweeps/ after that date.

## The bet

That making 'days since the sweeps were last accuracy-graded' visible next to the habit strip converts trust from assumed-permanent into a measured, decaying thing — and nudges the re-grade before drift is discovered the hard way. It targets assumption 1, the project's own stated riskiest ('sweeps stay accurate/trustworthy — the habit dies if trust dips'). A veteran flinches at eight topics running twelve months on frozen prompts through unannounced model swaps with zero drift instrumentation, where the habit-check strip counts visits and notes but never once re-tests sourcing.

## Decisions / open questions

The antibody leans on Kyle re-grading monthly — the exact diligence the death predicts will lapse; does a visible 'ungraded 60 days' banner actually prompt action, or just get ignored? Sampling design (how many items/topics per re-grade to be meaningful without being a chore); should a long ungraded stretch soft-warn on the brief itself, not just the habit strip; is a lightweight automated pre-screen worth the assumption-4 gate later.

## Credible first step

Extend the existing GET /brief/habit endpoint (VERIFIED at backend/app/api/brief.py:161, backed by brief_habit_weeks in backend/app/store/db.py:179 — it returns per-week visit counts only, never accuracy) to also surface a `last_graded` date read from a new docs/sweep-trust-log.md that reuses the M0 rubric (docs/M0-sweep-grades.md). Render that date beside the habit-check strip so an ungraded/stale stretch is visible instead of assumed fine. The grade itself stays a monthly manual pass — the instrument's job is to make its own absence loud.

## Dependencies

GET /brief/habit (backend/app/api/brief.py) + brief_habit_weeks (backend/app/store/db.py); the M0 rubric (docs/M0-sweep-grades.md) as the reused grading standard; a new docs/sweep-trust-log.md; the frontend habit-check strip as the render surface.

## Explicitly out of scope (revisit later)

Any automated/LLM-driven accuracy scorer for v0 (that's a gated new surface); changing the sweep prompts themselves; the calibration/self-grading prediction ledger (that's the distinct MO5 wager move); re-litigating the M0 verdict.

## Identity/positioning note

none — tethered.
