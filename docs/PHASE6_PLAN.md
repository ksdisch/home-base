# Phase 6 Plan — Smarter SR Core (per-item scheduling + daily study plan)

_Status: in progress on `claude/autonomous-milestone-6qQZG`. Picked via `/autonomous-milestone`
brainstorm (Intelligence/automation, ambitious). This is the first milestone past the SPEC
build order (Phases 1–5)._

## Why

Phase 4 shipped a **topic-level** "Review next" queue: each topic carries one mastery score
faded by a single uniform 14-day half-life (`store/mastery.py`). That's honest but blunt — a
concept you've nailed five times decays at the same rate as one you scraped once with a hint,
and the review unit is the whole topic, not the individual question.

This milestone makes the **question the unit of scheduling**: every question gets its own
SM-2 spaced-repetition state (ease / interval / reps / lapses / `due_at`) updated from how you
actually answered it, and a new **daily study plan** packs the due questions into a bounded,
interleaved session ("18 minutes: 3 from A, 2 from B, 1 from C"). It also revives the
**captured-but-never-read `reflections`** table as a browsable journal with a grasp-rating
trend.

The Phase-4 topic queue + home badge stay exactly as they are (well-tested, power the home
cards). The per-item scheduler is layered *alongside* it and feeds the new surfaces — no
rip-and-replace of a tested subsystem.

## Invariants preserved

- **Read-only toward NotebookLM** — everything operates on the local SQLite store.
- **Pure, clock-injected scoring** — the SM-2 step function and the planner take `now`
  explicitly, so every behavior is deterministic to unit-test (mirrors `mastery.py`/`grading.py`).
- **The grader stays the oracle** — scheduling reacts to graded results; it never grades.

## Build order (sequenced commits)

1. **Pure SM-2 scheduler** — `backend/app/store/scheduler.py`: `next_state(...)`,
   `quality_from_signal(correct, used_hint)`, `now_utc()`, `fmt_ts(dt)`, constants. Zero blast
   radius. Full unit tests (`tests/test_scheduler.py`): interval growth on Good, collapse on
   Again, ease floor, multi-week simulation with a frozen clock.
2. **Schema + migration** — bump `SCHEMA_VERSION` to 3; add `ease/interval_days/reps/lapses/
   due_at` to `question_mastery` (in the `CREATE` for fresh DBs) **and** a real
   `ALTER TABLE … ADD COLUMN` migration runner in `init_db` (idempotent: ignores
   "duplicate column" so it's safe on both fresh and existing v2 stores).
   Tests (`tests/test_migrations.py`): a v2 store upgrades cleanly and keeps its rows.
3. **Wire `record_attempt`** — compute each question's next SM-2 state from its prior state
   and persist it alongside the existing score/miss_count signal. Adds an optional injected
   `now`. Existing attempt/mastery tests stay green.
4. **Per-item queue + study planner** — `store/mastery.py: sr_plan_items(now, db_path)` (reads
   the SR columns), and a pure `study/planner.py: build_study_plan(items, *, minutes, now)`
   (greedy due-first fill to a time budget, then interleave so the same topic isn't
   back-to-back). Tests for budget, interleave, due-first.
5. **HTTP surface** — `GET /api/study-plan?minutes=20` and `GET /api/reflections`; new models
   (`StudyPlanSegment/Response`, `ReflectionItem/Response`); a shared `api/labels.py` (extracted
   from `review.py`); `store.list_reflections`. Route tests degrade gracefully on an empty store.
6. **Frontend** — `api/types.ts` + `api/client.ts` additions; a **Study Plan** page (`/plan`,
   minutes selector, interleaved segments linking to each quiz) + nav entry; a **Reflections**
   journal section on Progress. Vitest + Testing Library harness for the new pieces, and a CI
   job that gates `typecheck` + `build` + frontend tests (the repo previously had no FE CI).
7. **Docs** — update README + BACKLOG (retire the deferred "study-planner subagent" idea — it's
   now real, deterministic backend code, the right primitive).

## SM-2 mapping (from the hub's grading signal)

| Answer | SM-2 quality | Effect |
|---|---|---|
| miss (wrong) | 2 (lapse, q<3) | reps→0, lapses+1, interval→1d, ease−0.32 |
| hinted-correct | 3 (hard pass) | reps+1, interval grows, ease−0.14 |
| clean-correct | 5 (good pass) | reps+1, interval grows, ease+0.10 |

Intervals: 1st pass → 1d, 2nd → 6d, thereafter → `round(prev_interval × ease)`. Ease floor 1.3.

## Verifiability (cloud session)

Fully headless: the scheduler and planner are pure; the migration + routes test against a
temp SQLite via the existing `db_path` injection + `TestClient` patterns. Frontend via
vitest + `tsc --noEmit` + `vite build`. No browser, `nlm`, or live data required.
