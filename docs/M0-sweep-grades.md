# M0 — Sweep quality week: grades

The go/no-go log for [Milestone 0](KICKOFF-home-base.md). Each morning after `make sweep`,
spend ~2 minutes grading each topic's brief **A–F against reality**. This log — not the raw
briefs (which are gitignored) — is the durable evidence for the go/no-go decision. See
[`../sweeps/README.md`](../sweeps/README.md) for the routine.

**Grade key:** **A** = caught everything that mattered, zero slop · **B** = solid, minor
gap · **C** = usable but missed something real or padded · **D** = mostly noise/misses ·
**F** = hallucinated, stale, or useless. A **quiet day honestly reported** is an **A**, not a
low grade.

**Kill criteria:** persistent misses or slop on a pilot topic → stop and rethink that topic's
source strategy before building any UI.

## Log

Copy the three-row block each morning and fill it in. `Miss?` = what it failed to catch ·
`Slop?` = hallucinated / broken / stale · `Notes` = anything to tune in the prompt.

> **2026-07-13 = Claude Day-0 audit** (source-verified first pass, _not_ a human grade): each
> item's cited URLs were fetched or independently cross-searched. Across ~12 items / ~24 sources —
> **zero hallucinated events, zero dead/fabricated links** (CNBC/IG/Bloomberg returned 403 to direct
> fetch, but every story was confirmed via independent search). Verification was thorough but not
> exhaustive; a few secondary stats and the oldest fantasy item weren't independently re-confirmed.
> Your own morning grades are the real signal — this is a sanity-check baseline.

| Date | Topic | Grade | Miss? | Slop? | Notes / prompt tweaks |
|------|-------|:-----:|-------|-------|-----------------------|
| 2026-07-13 | AI / LLMs | A− | None fresh — GPT-5.6 Sol & Meta Muse Spark 1.1 both launched Jul 9, outside the 24h window (correctly excluded) | None — 3/3 items verified real; Gemini specs correctly labeled "leak-grade until Google posts it" | Zero hallucination + exemplary epistemic honesty. Backdrop slot went to the 3-day-old Apple suit; could've flagged Meta Muse Spark 1.1 (Jul 9 coding API) for a builder. Tune: on quiet days, prefer recent builder-relevant releases as backdrop. |
| 2026-07-13 | Fantasy football | A | None — verified genuinely quiet (no hard transactions/injuries broke in 24h) | None — JT quotes + stats exact (323 carries · 46% of touches · 80%+ snaps); Skattebo & Helm confirmed | Honest quiet-day handling, no padding. Items skew 1–6 days old but transparently dated; item 4 (Cook, Jul 7) sourced but not re-verified. Watch: prioritize fresh breaks on busy days. |
| 2026-07-13 | Market / tech news | A | None — independent search surfaced the same lead stories | 2 soft numeric slips (SK Hynix ADR premium ~37% vs ~25.6% found; Micron/Sandisk %s unconfirmed) | Index closes + oil %s exact; SK Hynix crash, Apple-OpenAI suit, June-CPI/bank previews all confirmed. Watch secondary-stat precision. |
| | AI / LLMs | | | | |
| | Fantasy football | | | | |
| | Market / tech news | | | | |
| | AI / LLMs | | | | |
| | Fantasy football | | | | |
| | Market / tech news | | | | |

## Running verdict

_Update as the week goes — the go/no-go call per topic plus the main prompt changes made._

- **AI / LLMs:** Day-0 **A−**. Trustworthy, zero slop, exemplary epistemic honesty (unconfirmed specs labeled as such). Only tuning note: backdrop selection could favor builder-relevant recent releases over legal/drama on quiet days.
- **Fantasy football:** Day-0 **A**. Passed the hardest case (dead-offseason quiet Monday) — honest, no padding, exact quotes/stats. Watch freshness prioritization once camps open.
- **Market / tech news:** Day-0 **A**. Exact hard numbers (index closes, oil), no misses. Watch precision on secondary stats.
