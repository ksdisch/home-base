# Architecture

## Purpose
The durable, cross-cutting picture of how Home Base is put together — the parts that stay true across milestones, so a fresh session doesn't have to reconstruct it from a dozen phase docs.

## Key understanding
- **Two arcs, one app** (Fact — `docs/MASTER_PLAN.md`): Arc 1 is the Learning Hub (catalog → quiz player → progress → SM-2 review → custom topics → Courses → Learning Paths); Arc 2 is Home Base proper (morning brief → notes → hands-off scheduling → audio brief → brief chat → mobile → news mode). Both live in one Vite+React+TS frontend and one FastAPI backend.
- **Four data layers** (Fact — `README.md` architecture table):
  1. Topic catalog — parsed from NotebookLM sidecars at `~/Projects/NotebookLMs/<alias>/` plus `nlm studio status`; strictly read-only.
  2. Quiz/study-guide content — `nlm download` on demand, cached locally.
  3. Course content — course sidecars on disk (`course.json` + material files); bundled example in `backend/app/courses/examples/`, generated ones under `COURSES_DIR`; read-only.
  4. Progress — the hub's own SQLite store (`backend/data/learning-hub.sqlite`): attempts, per-question SM-2, mastery decay, streaks, notes, custom topics. Never written into sidecars.
- **Sweeps pipeline** (Fact — `CLAUDE.md`, `docs/M3_PLAN.md`): `sweep.sh` + `sweeps/` render the morning brief from a config roster (`sweeps/topics.json`); a launchd 06:00 CT scheduler with on-wake catch-up runs it unattended; a cost/usage ledger tracks LLM spend; `sweeps/audio_brief.py` renders a ~5-min Kokoro MP3 after every sweep (best-effort).
- **LLM lane containment** (Fact — Wave 2 batch 2, PR #89): headless `claude -p` calls run on the subscription lane with the API key scrubbed, tools off, scratch cwd, untrusted framing; brief chat has no web tools.
- **Serving model** (Fact — `docs/M6_PLAN.md`): FastAPI serves the built frontend on one port; `com.homebase.server` KeepAlive LaunchAgent keeps it up; phone reach via Tailscale tailnet; `sw.js` caches the last brief for offline honesty (writes never queue).
- **News mode** (Fact — `docs/M7_PLAN.md`): pure-RSS ($0, zero LLM) Google News category shell with a 15-min cache, a `news_events` signal log, a For-You decaying-profile ranker, and a topic scout that feeds the Mode-A roster.
- **Key invariant**: sidecars are read-only — enforced in three layers: the `guard-sidecars` PreToolUse hook, `backend/tests/test_no_sidecar_writes.py`, and code convention.

## Sources
- `README.md` — stack, data layers, honest limitations
- `docs/MASTER_PLAN.md` — status of every architectural piece
- `docs/KICKOFF-home-base.md` — the Arc 2 contract
- `SPEC.md` — the Arc 1 contract
- Per-milestone plans under `docs/` — how each piece was built

## Uncertainties & contradictions
- Unresolved: whether sweep accuracy holds long-term (the project's stated riskiest assumption; ~2026-08-19 re-grade scheduled).
- Unresolved: Learning Paths Designer currently proven on one bundled fixture only; scaling to the full library is future work.

## Related pages
- (none yet — first topic page)

## Relevance to current work
Any new feature must respect the read-only-sidecar invariant and the SQLite-only progress rule; anything touching plan items must update `docs/MASTER_PLAN.md` in the same commit/PR.

_Last reviewed: 2026-07-26_
