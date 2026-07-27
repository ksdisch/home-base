# Free-Inference Rebuild — the brief becomes a reshapeable corpus behind a graded quote-only gate

**Status:** Idea — not committed. Added by `/replenish` (Moonshot lane) on 2026-07-26.

_Rebuild the read surface knowing what wasn't true at M0: on-device inference on the M-series Mac (Ollama/MLX) is now effectively free, private, and offline. So the brief stops being one fixed linear artifact and becomes a corpus plus a local retrieval-only reader that recomposes it live at read time — 'just the Chicago stuff', 'hide what I saw yesterday', 'brief me in 90 seconds' — under a hard quote-only contract: the model may select, reorder, and quote items from that day's sweep artifact with provenance intact, and is forbidden to generate any new claim. The deterministic sweep artifact stays as the sole source of facts and the audit trail underneath. Distinct from M5 chat (one remote grounded Q&A per question) and from the audio-lane interruption idea: this is the READ surface becoming malleable._

## Premise

The morning read stops being 'everything the sweep found, in one fixed order' and becomes 'the brief, shaped to this moment' — shorter on a busy day, filtered to one city, stripped of what Kyle already saw — all free, offline, private, and provably quote-only. Same facts, same provenance, infinitely reshapeable.

**Why now:** The economic premise that froze read-time at deterministic already shifted: marginal on-device inference cost went to ~0 within the horizon, so the rational feature set for the read surface changed underneath the doctrine. The project's own method — grade first, ship second — is the licensed path to update the doctrine now rather than leave the assumption calcified against reality.

## The bet

THE ONE THING THAT MUST BE TRUE: assumption 2 ('zero/minimal LLM at read time') encoded 2025 economics — LLM meant remote, metered, trust-risky — and the assumption's real content was never 'no LLM' but 'no cost, no cloud, no fabrication at read time'. Local inference deletes the cost and privacy halves; the quote-only contract deletes the fabrication half, keeping load-bearing assumption 1 (sweep accuracy) fully intact because the sweep artifact remains the only source of facts. TARGETS assumption 2 head-on. VETERAN FLINCH: this is the doctrine the whole project's trust rests on — a veteran will reach for the kill switch on 'LLM at read time' instantly, which is exactly why the wedge is a graded go/no-go BEFORE any product surface, in the M0-graded-week house style. That discipline is the argument.

## Decisions / open questions

(1) Which local runtime (Ollama vs MLX) and which model earns the bake-off slot first? (2) What is the mechanical quote-verification — exact substring against the day's sweep JSON, like the Session Note's verifier? (3) Does the reshaped view ever replace the fixed brief, or live beside it permanently?

## Credible first step

A graded bake-off, zero user-facing surface, exactly how this project earns doctrine changes: new sweeps/local_reader_bench.py replays real questions from backend/data/brief-chat.jsonl (falling back to a fixture set built from the ~2 weeks of real data/sweeps/<date>/ dirs already on disk) against a local Ollama/MLX model under the quote-only grounding prompt, grades groundedness side-by-side with the recorded claude -p answers, and writes the verdict table to docs/ the way docs/M0-sweep-grades.md did. The chat.py runner seam (confirmed: Runner = Callable, injected default-off) is the natural place a second local runner slots in behind a flag. Nothing ships to Brief.tsx until a full graded week passes at the sweep's own bar.

## Dependencies

backend/data/brief-chat.jsonl (replay corpus), data/sweeps/<date>/ dirs, the chat.py Runner seam (injectable), a local inference runtime on the Mac, the M0 grading pattern (docs/M0-sweep-grades.md).

## Explicitly out of scope (revisit later)

No cloud inference, no read-time generation of new claims (quote-only contract is the licence), no UI work in v0 — the bake-off is the whole first move. Assumption 2 is only crossed if the graded week passes.

## Identity/positioning note

stretch bordering identity-shift: crosses assumption 2 deliberately; the read surface stops being a fixed document and becomes a corpus rendered per-moment. What changes about what-this-project-IS: the brief becomes generative-but-grounded at read time — the first read surface that is malleable without betraying the trust bar.
