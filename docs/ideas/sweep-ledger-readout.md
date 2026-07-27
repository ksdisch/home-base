# Total up the sweep ledger — the cost/health readout the code already promised

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-07-26.

_A zero-LLM GET /api/brief/runs/summary over data/sweeps/.runs.jsonl (69 live rows carrying per-topic total_cost_usd, duration_ms, model, is_error since M3) plus one ops line on Today: 'This morning: 9 topics · 21 min · $8.12 · 0 errors', with a 7-day roll-up. Read-only, deterministic, one sitting._

## Premise

The morning brief gains a self-report: cost + health + error count at a glance, so a silently-degraded or expensive sweep announces itself instead of hiding in a dotfile.

**Why now:** It watches both halves of assumption 2 (LLM spend happens at sweep time) and assumption 1 (a missing day or a $1 day is the mechanical shadow of a thin/failed sweep — the #1 stated risk). The anomaly is present in the data today; every day without the readout is a day the signal is grepped-only on the Mac.

## The bet

The bet: a single always-on cost/health line earns a second daily glance and catches sweep pathology Kyle currently can't see. What makes a project veteran nod: the ledger already exists (envelope.py's own docstring calls it 'the durable answer to what do the sweeps cost'), the rows are verified real, and the live data has an unseen tell RIGHT NOW — 07-24 is missing from the ledger entirely and 07-23/07-25 totaled $1-2 vs the ~$10/day norm. Ten days in, nobody wrote the totaler. That's the definition of a QuickWin sitting in plain sight.

## Decisions / open questions

(1) Footer line on Today vs a chip beside the trust gauge? (2) Should an anomalous day (missing / <25% of trailing-median cost) get a warning tint, or is v0 purely informational?

## Credible first step

Add runs_summary() beside _read_ledger() in /Users/kyledisch/Projects/home-base/backend/app/sweeps.py (the tolerant JSONL parser is already there at line 433), expose it from /Users/kyledisch/Projects/home-base/backend/app/api/brief.py, render one footer line in /Users/kyledisch/Projects/home-base/frontend/src/pages/Brief.tsx near the existing habit/trust strip.

## Dependencies

data/sweeps/.runs.jsonl (69 live rows), the tolerant _read_ledger parser in backend/app/sweeps.py, backend/app/api/brief.py, frontend/src/pages/Brief.tsx.

## Explicitly out of scope (revisit later)

No cost alerting/notifications, no per-topic drill-down page, no budget caps — one endpoint, one line, one roll-up.

## Identity/positioning note

none — tethered.
