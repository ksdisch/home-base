# Free-Inference Rebuild — the brief becomes a reshapeable corpus behind a graded quote-only gate

**Status:** GO at the 2026-07-27 gate conversation (decision D8); plan APPROVED the same day
(approach A) and the bake-off bench is **built** — `sweeps/local_reader_bench.py`, 35 tests,
zero product surface. Remaining and Kyle's alone: author the gold-set fixtures, then run the
7-day graded week. Assumption 2 stays uncrossed until it passes and a second decision ships a
lens. Plan + implementation corrections:
[`../LOCAL_READER_BAKEOFF_PLAN.md`](../LOCAL_READER_BAKEOFF_PLAN.md).
Added by `/replenish` (Moonshot lane) on 2026-07-26.

_Rebuild the read surface knowing what wasn't true at M0: on-device inference on the M-series Mac (Ollama/MLX) is now effectively free, private, and offline. So the brief stops being one fixed linear artifact and becomes a corpus plus a local retrieval-only reader that recomposes it live at read time — 'just the Chicago stuff', 'hide what I saw yesterday', 'brief me in 90 seconds' — under a hard quote-only contract: the model may select, reorder, and quote items from that day's sweep artifact with provenance intact, and is forbidden to generate any new claim. The deterministic sweep artifact stays as the sole source of facts and the audit trail underneath. Distinct from M5 chat (one remote grounded Q&A per question) and from the audio-lane interruption idea: this is the READ surface becoming malleable._

## Premise

The morning read stops being 'everything the sweep found, in one fixed order' and becomes 'the brief, shaped to this moment' — shorter on a busy day, filtered to one city, stripped of what Kyle already saw — all free, offline, private, and provably quote-only. Same facts, same provenance, infinitely reshapeable.

**Why now:** The economic premise that froze read-time at deterministic already shifted: marginal on-device inference cost went to ~0 within the horizon, so the rational feature set for the read surface changed underneath the doctrine. The project's own method — grade first, ship second — is the licensed path to update the doctrine now rather than leave the assumption calcified against reality.

## The bet

THE ONE THING THAT MUST BE TRUE: assumption 2 ('zero/minimal LLM at read time') encoded 2025 economics — LLM meant remote, metered, trust-risky — and the assumption's real content was never 'no LLM' but 'no cost, no cloud, no fabrication at read time'. Local inference deletes the cost and privacy halves; the quote-only contract deletes the fabrication half, keeping load-bearing assumption 1 (sweep accuracy) fully intact because the sweep artifact remains the only source of facts. TARGETS assumption 2 head-on. VETERAN FLINCH: this is the doctrine the whole project's trust rests on — a veteran will reach for the kill switch on 'LLM at read time' instantly, which is exactly why the wedge is a graded go/no-go BEFORE any product surface, in the M0-graded-week house style. That discipline is the argument.

## Decisions / open questions

(1) Which local runtime (Ollama vs MLX) and which model earns the bake-off slot first? (2) What is the mechanical quote-verification — exact substring against the day's sweep JSON, like the Session Note's verifier? (3) Does the reshaped view ever replace the fixed brief, or live beside it permanently?

**ANSWERED at the 2026-07-27 gate conversation (Kyle's picks, recorded scope):**

_Demand side passed the pressure test first: asked what he wants to do to the brief that a
deterministic filter can't already do, Kyle's answer was **open-ended natural language** —
arbitrary reshaping requests that can't be enumerated in advance. The doc's own three
examples ("just the Chicago stuff", "hide what I saw yesterday") are filter-shaped and were
explicitly **not** the want; they remain available as a zero-doctrine QuickWin if ever
desired. The bet rests on the un-enumerable case._

1. **Ollama + a small instruct model** takes the first bake-off slot. MLX is faster on
   M-series and "both runtimes" is more complete, but neither gates the doctrine change:
   the question that gates it is *can a local model do this reliably at all*, not *which
   runtime is quicker*. An 8B-class instruct model is expected to suffice — see answer 2
   for why the bar is lower than it looks. The bench wires in behind the existing
   `chat.py` `Runner` seam, so MLX can take a later slot without a rewrite.
2. **Ids-only, never prose — the model emits no text at all.** Its entire output is a list
   of item ids from that day's sweep plus an ordering; the UI renders the stored
   headline/digest through the existing deterministic path. Exact-substring verification
   (the Session Note's mechanism) and substring-plus-flagged-connectives were both
   considered and **not** chosen: they detect fabrication after the fact, where ids-only
   removes the channel for it. Fabrication stops being a policed contract and becomes a
   type signature. **Consequence recorded:** the task is structured selection, not
   generation — so the bake-off grades schema discipline (valid ids, no invented ids),
   recall of items that should have been kept, and ordering quality, *not* prose
   groundedness. The one thing ids-only cannot do is synthesize across items, which is
   precisely what assumption 2 forbids; that is a feature of the answer, not a gap in it.
3. **Beside the fixed brief; default status must be earned.** v0 is an opt-in lens over an
   unchanged fixed brief. Becoming the front door is possible but only via its own M0-style
   graded record plus a gate conversation — the same escalation shape Overnight chose for
   its send gate. "Beside it permanently" and "replaces it once the week passes" were both
   declined: the first caps the idea at a novelty, the second decides the product shape
   before any verdict exists.

**Recorded invariants (hold under every answer above):**

- **Offline degrade, not failure.** If the local runtime isn't up — Mac asleep, Ollama not
  running — the lens degrades visibly to the fixed brief rather than erroring, per the M6
  `sw.js` offline-honesty pattern. The morning never depends on inference being available.
- **The bake-off is Mac-side by construction.** `backend/data/` and `/data/sweeps/` are
  both gitignored (`.gitignore:40,43`), so the replay corpus — `brief-chat.jsonl` and the
  sweep dirs — exists only on Kyle's machine. A cloud session can author the bench and its
  tests; only the Mac can produce the verdict table. Plan accordingly: the graded week is
  Kyle's to run.
- **Assumption 2 is still uncrossed until the graded week passes.** The go recorded here is
  a go for the *bake-off*, not for shipping a read surface. Nothing reaches `Brief.tsx`
  without a second decision.

## Credible first step

A graded bake-off, zero user-facing surface, exactly how this project earns doctrine changes: new sweeps/local_reader_bench.py replays real questions from backend/data/brief-chat.jsonl (falling back to a fixture set built from the ~2 weeks of real data/sweeps/<date>/ dirs already on disk) against a local Ollama/MLX model under the quote-only grounding prompt, grades groundedness side-by-side with the recorded claude -p answers, and writes the verdict table to docs/ the way docs/M0-sweep-grades.md did. The chat.py runner seam (confirmed: Runner = Callable, injected default-off) is the natural place a second local runner slots in behind a flag. Nothing ships to Brief.tsx until a full graded week passes at the sweep's own bar.

## Dependencies

backend/data/brief-chat.jsonl (replay corpus), data/sweeps/<date>/ dirs, the chat.py Runner seam (injectable), a local inference runtime on the Mac, the M0 grading pattern (docs/M0-sweep-grades.md).

## Explicitly out of scope (revisit later)

No cloud inference, no read-time generation of new claims (quote-only contract is the licence), no UI work in v0 — the bake-off is the whole first move. Assumption 2 is only crossed if the graded week passes.

## Identity/positioning note

stretch bordering identity-shift: crosses assumption 2 deliberately; the read surface stops being a fixed document and becomes a corpus rendered per-moment. What changes about what-this-project-IS: the brief becomes generative-but-grounded at read time — the first read surface that is malleable without betraying the trust bar.
