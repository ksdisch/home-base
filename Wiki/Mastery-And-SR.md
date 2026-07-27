# Mastery and Spaced Repetition

## Purpose
The hub has two distinct review-scheduling layers that operate at different granularities and
feed different surfaces. This page explains both, their interaction, the namespace conventions
that keep them from colliding, and which surface each feeds. No single doc covers the full
picture — it spans `store/mastery.py`, `store/scheduler.py`, `PHASE4_PLAN.md`,
`PHASE6_PLAN.md`, and the schema.

## Key understanding

### Two layers, two units of scheduling

| Layer | Unit | Module | When added |
|---|---|---|---|
| **Topic-level decay** | One score per topic (`topic_mastery` row) | `backend/app/store/mastery.py` | Phase 4 |
| **Per-question SM-2** | One SM-2 row per question (`question_mastery`) | `backend/app/store/scheduler.py` | Phase 6 |

**Fact** (`docs/PHASE6_PLAN.md`): Phase 6's rationale for adding per-question SM-2 was that the
Phase-4 topic queue was "honest but blunt — a concept nailed five times decays like one scraped
once with a hint." The per-question layer makes the question the unit of scheduling. The two
layers were **layered, not replaced**.

### Layer 1 — Topic-level half-life decay (`mastery.py`)

The model is honest and simple: **estimated current retention = the last stored score, faded by
time since last review**.

**Fact** (`backend/app/store/mastery.py` tunables):
```python
HALF_LIFE_DAYS = 14.0   # mastery halves every two weeks without a review
DUE_THRESHOLD  = 0.5    # estimated retention below this → "due for review"
MISS_WEIGHT    = 5.0    # each unresolved miss nudges a topic up the queue
PRIORITY_CAP   = 200.0
```

Decay formula: `decayed = score * 0.5 ** (days_since_review / 14)`.
- A freshly-aced topic is not due; it becomes due as it fades.
- `last_review_at is None` → `decayed = 0.0` (never practiced = no retention to credit).
- `score` is the latest attempt fraction (Phase 2 `record_attempt` writes it).

Queue ordering: due-first, then by `priority = (1 - decayed) * 100 + miss_count * MISS_WEIGHT`.
Unresolved misses break ties and push shaky topics up.

**Surfaces fed by the topic-level queue**:
- Home catalog badge: `mastery` chip + `🔁 due for review` badge on each `NotebookCard`.
- `/review` page ("Review next" queue): full ranked list with `reason` lines.
- `/progress` trends: `last_practiced`, `best_pct`, `avg_pct` per topic.

### Layer 2 — Per-question SM-2 (`scheduler.py`)

Classic SM-2: each question carries `ease`/`interval_days`/`reps`/`lapses`/`due_at`.

**Fact** (`backend/app/store/scheduler.py` tunables):
```python
INITIAL_EASE        = 2.5   # SM-2 default
MIN_EASE            = 1.3   # ease floor
FIRST_INTERVAL_DAYS = 1.0   # first successful recall → review tomorrow
SECOND_INTERVAL_DAYS = 6.0  # second successful recall → review in ~a week
LAPSE_INTERVAL_DAYS  = 1.0  # a miss resets to relearn tomorrow
PASS_QUALITY        = 3     # quality ≥ 3 is a successful recall
```

Quality mapping from hub signals:
- Miss → quality 2 (lapse)
- Hinted-correct → quality 3 (hard pass)
- Clean-correct → quality 5 (good pass)
- Flashcard self-grades: `again=2`, `hard=3`, `good=5` — identical to quiz signals.

**Fact**: `next_state()` is pure; the DB layer calls it and persists the result. Nothing in
`scheduler.py` touches SQLite.

**Surfaces fed by the per-question layer**:
- Daily "Today's plan" (Study Plan): `sr_plan_items()` builds the ranked queue; `app/study/planner.py`
  packs it into a time-boxed, interleaved session (same topic not back-to-back).
- Per-question `due_at` drives the "Review" lane in the Plan.
- Course quizzes and flashcards share this same layer under the `course:` namespace.

### Namespace split: `course:` prefix
**Fact** (`backend/app/store/mastery.py`, comments in `schema.py` and `mastery.py`):
Course quizzes use the shared `topic_mastery` and `question_mastery` tables with
`notebook_id = 'course:<slug>'`. This prefix determines what each surface includes:

| Surface | Course rows? |
|---|---|
| `review_queue()` (home badge, `/review`) | **Excluded** (`WHERE notebook_id NOT LIKE 'course:%'`) — courses have their own review surface |
| `sr_plan_items()` (daily Study Plan) | **Included** — course quizzes get a seat in the interleaved plan |
| `/progress` trends, activity heatmap | **Excluded** — topic-only |
| Course quiz SM-2 state, due chips | Read from the same tables via `course:<slug>` |

**Inference**: this was a deliberate design decision made at Course SM-2 introduction (Phase 7 M2)
so courses didn't pollute the topic-facing review queue, but still benefited from the study plan's
interleaving.

### How the two layers relate during an attempt
**Fact** (`backend/app/store/db.py` `record_attempt`): After grading a quiz attempt, `record_attempt`:
1. Writes an `attempts` row + per-question `attempt_answers` rows.
2. Updates `topic_mastery`: `score = attempt_fraction`, `last_review_at = now`.
3. For each answered question, calls `scheduler.next_state()` and upserts a `question_mastery` row
   with the new SM-2 state.

**Inference**: a single quiz attempt simultaneously updates both layers — the topic-level score
(for the home badge) and each question's SM-2 schedule (for the daily plan).

### Study Plan: interleaving and time-boxing
**Fact** (`backend/app/study/planner.py`, `docs/PHASE6_PLAN.md`): `build_study_plan()` is pure;
it takes the output of `sr_plan_items()` (already ranked due-first by priority), packs questions
into a requested time budget, and **interleaves** so the same topic is not back-to-back. It returns
`StudyPlanSegment` items: each is one quiz to retake, sized by how many of its questions are due.

**Fact** (`docs/MASTER_PLAN.md`, 2026-07-22 PR entry): course quizzes were added to the Study Plan
in the same PR that introduced topic↔course cross-links — course SM-2 rows (under `course:<slug>`)
were previously filtered out of `sr_plan_items`, which was relaxed. Course segments are titled from
the course catalog and badged "Course"; they deep-link to `/courses/:slug/quiz?path=...`.

### Path coverage vs. recall: the M8 third axis
**Fact** (`docs/MASTER_PLAN.md`, M8 PR #135, `backend/app/models.py` `PathSummary`): Learning
Paths introduce a third measurement axis alongside topic mastery and daily SR:
- **Coverage** (`path_step_progress`): latest-value-only step completion. No time-series.
- **Confidence** (`path_confidence`): latest-value-only 1–5 self-rating. No time-series.
- **Recall**: the SM-2 `attempts` history via the existing `topic_mastery` / `question_mastery`
  tables — the ONLY axis with a real reconstructable time-series.

**Decision** (Kyle, PR #135): Progress shows Recall as the one real TREND line; Coverage + Confidence
are honest CURRENT readouts — never faked into lines. No new tables, no new writes.

## Sources
- [`backend/app/store/mastery.py`](../backend/app/store/mastery.py) — topic-level decay model + queue (authoritative tunables, pure functions)
- [`backend/app/store/scheduler.py`](../backend/app/store/scheduler.py) — SM-2 `next_state()` (authoritative tunables, pure)
- [`docs/PHASE4_PLAN.md`](../docs/PHASE4_PLAN.md) — why and how the decay model was designed
- [`docs/PHASE6_PLAN.md`](../docs/PHASE6_PLAN.md) — SM-2 rationale, the study plan, interleaving design
- [`docs/MASTER_PLAN.md`](../docs/MASTER_PLAN.md) — M8 three-axis decision, course quizzes joining the plan

## Uncertainties & contradictions
- **Unresolved**: `HALF_LIFE_DAYS = 14`, `DUE_THRESHOLD = 0.5`, and the SM-2 initial params
  (`INITIAL_EASE = 2.5`, etc.) were chosen at design time and are not validated against Kyle's
  actual retention data. They are marked as tunables but have not been tuned.
- **Unresolved**: for a path step that reuses an existing topic artifact (e.g. a quiz already
  practiced outside a path), the SM-2 recall state is shared — completing the step as part of a
  path updates the same `question_mastery` row a standalone retake would. This is intended (shared
  signal) but could cause unexpected cross-surface coupling if the path scheduler is later made
  path-aware.
- **Inference** (no doc explicitly confirms): `topic_mastery.score` is always the fraction of the
  *most recent* attempt, not a running average. Two weak attempts followed by one strong one would
  report the strong fraction as mastery. The decay model then fades this "most recent" signal.

## Related pages
- [Data-Model](Data-Model.md) — the `topic_mastery`, `question_mastery`, `path_step_progress`, and `path_confidence` table definitions
- [Architecture](Architecture.md) — how the SQLite progress layer fits into the four data layers

## Relevance to current work
Any feature that reads or writes review state must decide whether it targets the topic-level queue
(home badge + `/review` — filter `course:%` out) or the per-question plan (Study Plan — include
`course:%`). New namespaces (e.g. a future `path:` prefix) must be explicitly handled in both
`review_queue()` and `sr_plan_items()` filter logic. The two tunables files are the right place to
adjust scheduling aggressiveness; do not add magic numbers inline.

_Last reviewed: 2026-07-26_
