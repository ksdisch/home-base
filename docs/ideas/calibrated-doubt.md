# Calibrated Doubt — the brief that bets, then grades itself

**Status:** Idea — not committed. Added by `/brainstorm` (Moonshot mode) on 2026-07-19.

_Every sweep item ships an optional falsifiable prediction plus a confidence number, and the next morning opens by scoring yesterday's calls against today's items and updating a running, public calibration ledger — a Brier score and a track record ('I was 4-for-5; my 70% calls land 70% of the time')._

> **Wildcard:** kept deliberately borderline-bold per the mode rules — the most on-target survivor of its lane.

## Premise

The entire design earns trust by abstention — never assert what you can't source, leave it out. Invert it: earn trust by accountability. The brief stops saying 'this is true' and starts saying 'I'm 70% this trade closes by Friday — here's my record.' A calibrated forecaster who is honestly 70% and lands 70% is more trustworthy than an oracle who only ever recites the safe past, and the next-day scoring pass is exactly the guard that makes the judgment falsifiable instead of merely cautious. Sibling MO6 (The Book — Kyle stakes his own convictions and the brief grades HIM) is the runner-up in the same predict-and-score family and a natural variant of this move.

**Why now:** The M0 grading week closed TODAY (2026-07-19) with a PASS and zero fabrications — trust-by-abstention is freshly, rigorously proven and about to freeze onto the same eight prompts for a year. The decision of whether trust should scale by abstention (never assert what you can't source) or by accountability (assert, then grade) is live exactly now, at the one moment the M0 rubric and the grading muscle are still warm enough to re-run as a gate.

## The bet

Targets assumption 1 (sweeps stay accurate/trustworthy — the project's own named riskiest assumption) by inverting its strategy. The one thing that must be true: a brief that visibly wagers and honestly grades itself earns more durable trust than one that only ever states the safe, unfalsifiable past — because a brief that can never be caught wrong can never be caught right. A veteran flinches hard: this deliberately manufactures visible, repeated wrongness inside a product whose entire M0 thesis was zero fabrications.

## Decisions / open questions

(1) Auto-resolving arbitrary calls ('did the trade close?') is genuinely hard — stay deterministic over cleanly-checkable predictions, or add an LLM judge against next-day items (which reopens the assumption-4 gate)? (2) Which topics get predictions — markets and model releases resolve cleanly, sports and opinion far less so; opt-in per topic? (3) How to display wrongness without training Kyle to distrust the whole brief — is the Brier/track-record framing enough to make a missed call read as calibration rather than failure?

## Credible first step

Add optional prediction + confidence fields to the item schema in sweeps/prompts/*.md (verified: no such field today), and make them survive by adding them to validate() and normalize() in sweeps/render_brief.py — which today keeps only REQUIRED_ITEM_FIELDS and would silently strip any new key from <topic>.json. Then a scoring pass in backend/app/sweeps.py (the same prior-day-JSON join _history_first_seen already performs) resolves yesterday's cleanly-checkable calls, appends to a new backend/data/calibration.jsonl, surfaced as a 'Yesterday's calls' strip via backend/app/api/brief.py + BriefResponse on frontend/src/pages/Brief.tsx. CORRECTION: the input placed the 'Yesterday's calls' rendering in sweeps/render_brief.py, but that file only emits per-topic gradeable Markdown, not the served Today page — the render surface is api/brief.py, and render_brief.py's only role here is passing the two new fields through validate()/normalize(). Gate with an M0-style graded week before it's trusted.

## Dependencies

sweeps/prompts/*.md (schema), sweeps/render_brief.py validate()/normalize() field pass-through, backend/app/sweeps.py prior-day join (mirrors _history_first_seen), a new backend/data/calibration.jsonl, backend/app/api/brief.py + BriefResponse, frontend/src/pages/Brief.tsx. Process dependency: an M0-style graded week of predictions before the ledger is trusted (assumption 4).

## Explicitly out of scope (revisit later)

Predictions stay optional per item — never forced onto every item, so a quiet, sourced-only day still reads honestly. No LLM judge in v0: resolve only cleanly-checkable calls. Not shipped ungated — a graded week precedes trust, exactly like M0. Does not touch the abstention rule for non-predicted items; it adds a wager lane, it does not weaken the sourcing bar.

## Identity/positioning note

stretch — file-anchored and additive (prompt fields + a scoring join + a jsonl + a strip), yet it inverts the load-bearing accuracy-by-abstention strategy the whole design earns trust through. It does not change what the project IS (still a morning brief), so not identity-shift; it flips the trust principle underneath it, which is why it reads as the wildcard.
