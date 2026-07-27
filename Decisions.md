# Decisions

| ID | Decision | Status | Date | Source/Rationale |
|----|----------|--------|------|-----------------|
| D1 | Rename `learning-hub` → `home-base` and evolve into Kyle's daily home base (morning brief + Learning Hub as the learning section) | Approved | 2026-07-13 | Kickoff contract `docs/KICKOFF-home-base.md`; `README.md` |
| D2 | The hub is strictly read-only toward NotebookLM sidecars; generating new series stays in the `audio-series` skill | Approved | 2026-06 (SPEC) | `SPEC.md`, `README.md`; enforced by the `guard-sidecars` hook + `backend/tests/test_no_sidecar_writes.py` |
| D3 | Progress data (attempts, mastery, streaks, notes, custom topics) lives in the hub's own SQLite store, kept out of the sidecars | Approved | 2026-06 (SPEC) | `README.md` architecture table |
| D4 | Deliberate gate overrides: build M3–M7 ahead of the M0 sweep-quality verdict; vindicated when M0 closed PASS with zero fabrications | Approved | 2026-07-15 → 2026-07-19 | `CLAUDE.md` status header; `docs/M0-sweep-grades.md` |
| D5 | Study-scheduler note box: local deterministic parser is the primary engine; `claude -p` only as fallback for unparseable phrasing; honest no-op message if neither reads it | Approved | 2026-07-22 | Kyle's call after the v1 note box silently did nothing (PR #141; `docs/MASTER_PLAN.md`) |
| D6 | Learning Paths build on the audio overview season as the spine; video series is supplementary only ("design decision 12"), guarded by `test_paths_fixture.py` | Approved | 2026-07-22 | PR #143 fix after the Jacobian path was wrongly built on the video season (`docs/MASTER_PLAN.md`) |
| D7 | Park Agent Gate until after the ~08-03 v1 check; the other three 07-26 moonshots stay undecided (each keeps its own future gate conversation). Demand-side finding recorded: Claude Code crons/sessions are a sufficient first tenant — the park is timing, not demand. The vision doc's three open questions stay deliberately unanswered until the revisit | Approved | 2026-07-27 | Gate conversation (Overnight-gate model); `docs/ideas/agent-gate.md` Decisions section |
