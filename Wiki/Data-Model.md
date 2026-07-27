# Data Model

## Purpose
A complete picture of the SQLite store — every table, why it exists, and the design
principles that determine what goes in SQLite versus on disk. No single existing doc
covers the full schema; it is distributed across `backend/app/store/schema.py`,
`backend/app/models.py`, and the per-phase plan docs.

## Key understanding

### Disk-vs-SQLite principle (the founding invariant)
**Fact** (`SPEC.md`, `docs/PHASE1_PLAN.md`): All *content* lives on disk; all *progress*
lives in SQLite. This means:
- NotebookLM sidecar files (`~/Projects/NotebookLMs/<alias>/`) are never written by the hub.
- Course material files (`course.json`, lesson markdown, diagrams, quizzes) are on disk.
- Path definitions (`<notebook_id>.json` path sidecars) are on disk.
- Every learner action — attempt, listen ✓, note, mastery score, streak day, calendar block — goes
  in SQLite at `backend/data/learning-hub.sqlite`.

**Inference**: This split lets the hub be completely reinstalled (or the store wiped) without
losing the source material, and it keeps the sidecars clean for other tools.

### Schema version and migration strategy
**Fact** (`backend/app/store/schema.py`): The store is at `SCHEMA_VERSION = 12`. Every table
uses `CREATE TABLE IF NOT EXISTS` (idempotent). Additive `ALTER TABLE ADD COLUMN` migrations
live in the `MIGRATIONS` dict, keyed by version. `init_db` re-runs them on every call, tolerating
"duplicate column" errors — so a store whose table was dropped and recreated outside the app heals
rather than 500ing. **Consequence: every migration entry must be idempotent under re-run (ADD
COLUMN only); a one-shot data backfill cannot go here.**

### Table inventory (v12)

| Table | Schema version | What it tracks |
|---|---|---|
| `schema_migrations` | v1 | Version ledger — when each version was first seen. |
| `episode_progress` | v1 | Manual "I listened" checkbox per NotebookLM episode. PK = `(notebook_id, artifact_id)`. |
| `attempts` | v1 | Each graded quiz attempt: `notebook_id`, `quiz_artifact_id`, `started_at`, `finished_at`, `score`, `total`. |
| `attempt_answers` | v1 | Per-question answer within an attempt: chosen index, correct flag, hint flag. Cascades on attempt delete. |
| `reflections` | v1 | Post-episode reflections (from the `episode-review` skill): body + `grasp_rating` 1–5. |
| `notes` | v1 | One free-form note per notebook (keyed on `notebook_id`). |
| `custom_topics` | v1 | Non-NotebookLM interests: title, notes, `progress_pct` 0–100. |
| `topic_mastery` | v1 | Phase-4 topic-level mastery: PK = `notebook_id`, `score` (latest attempt fraction), `last_review_at`. The decay engine reads this. |
| `question_mastery` | v1+v3 | Per-question mastery + SM-2 state: PK = `(notebook_id, quiz_artifact_id, question_key)`. v1 has `score`/`miss_count`/`last_review_at`; v3 migration adds `ease`/`interval_days`/`reps`/`lapses`/`due_at`. |
| `activity` | v1 | Daily learning activity rollup for streaks. `day` is LOCAL calendar day (not UTC). |
| `brief_visits` | v4 | One row per Today page load — the habit metric (`distinct days ≥ 5/week`). `day` is local. |
| `course_lesson_progress` | v5 | "I finished this lesson" per course lesson. PK = `(course_slug, lesson_id)`. |
| `brief_notes` | v5 | Inline notes on brief items. Snapshots `topic_slug`/`brief_date`/`item_headline` because `data/sweeps/` is gitignored and regenerable — a note must stay meaningful after its file is re-swept or gone. |
| `course_rubric_assessment` | v6 | Learner self-assessment of a course project/capstone. PK = `(course_slug, material_path)`. `ratings` is a JSON map criterion→level. |
| `news_feed_cache` | v7 | 15-min TTL cache of parsed Google News RSS payloads. Safely deletable — next request refetches. |
| `news_events` | v8 | For-You signal log: `click`/`visit`/`more_like`/`not_interested`. Snapshots headline/source/url because the cache rolls over in minutes. Feeds the decaying interest profile; never `activity` rows. |
| `news_topic_dismissals` | v9 | "Don't suggest this term again" for the news mode topic scout. Terms stored lowercased. |
| `path_step_progress` | v10 | M8 learning path step coverage: PK = `(notebook_id, step_id)`, `completed` flag. |
| `path_confidence` | v10 | M8 per-step confidence self-rating 1–5. PK = `(notebook_id, step_id)`. Latest-value-only (upsert, no history). |
| `study_opt_in` | v11+v12 | Study Scheduler per-track opt-in flag + session length. v12 adds persisted window prefs: `day_start_hour`/`day_end_hour`/`days_of_week` (CSV of Python weekday ints)/`max_blocks`. PK = `(track_kind, track_id)`. |
| `study_blocks` | v11 | Removable block ledger — one row per calendar event written by the Study Scheduler. Carries Google `event_id` + `calendar_id` for clean removal; `status` flips `written` → `removed` on deletion (soft-delete, never hard-deleted). |

### Namespacing: the `course:` prefix
**Fact** (`backend/app/store/mastery.py`, `backend/app/store/schema.py`): Course quizzes share the
`question_mastery` and `topic_mastery` tables with NotebookLM topics. Course rows are namespaced as
`notebook_id = 'course:<slug>'` (constant `COURSE_NB_PREFIX` in `app.courses`). **Design consequence
— surfaces split on this prefix:**
- `review_queue()` / `due_topic_ids()` (home badge + `/review`) **filter out** `course:%` — courses
  have their own review surface.
- `sr_plan_items()` (the daily Study Plan) **includes** `course:%` — course quizzes get a seat in the
  interleaved plan alongside topics.
- `/progress` trends, "Recent activity" heatmap — topic-only (filter `course:%` out).

### Brief item ID (`item_id`)
**Fact** (`backend/app/sweeps.py`, `backend/app/store/schema.py` brief_notes comment):
`item_id = sha1(date|slug|headline)[:12]`. This is **date-scoped by design** — a stale tab's
"Ask about this" naturally 404s after rollover; a note's anchor is stable as long as the date +
topic + headline haven't changed, but is NOT stable if the brief is re-swept with a new headline.
The `brief_notes` table snapshots `brief_date`/`topic_slug`/`item_headline` for exactly this reason.

### Local-day rule
**Fact** (`schema.py` comments on `activity`, `brief_visits`): SQLite's `datetime('now')` is UTC —
a 7pm CDT visit would be filed under tomorrow if naive UTC were used. Code that writes `day` values
uses `date('now','localtime')` in raw SQL or `db._local_day` in injected-clock paths. The `/api/progress`
"today" comparison is also local. **Bug history**: the UTC streak bug was fixed in Wave 2 batch 5,
PR #92.

### Pre-migration snapshot
**Fact** (Wave 2 batch 5, PR #92): `init_db` takes an unconditional pre-migration snapshot (newest
5 kept) before running any ALTER migrations. A failing migration can be healed by restoring the
snapshot. This is the `HA11` hardening item.

## Sources
- [`backend/app/store/schema.py`](../backend/app/store/schema.py) — the authoritative table + migration definitions
- [`backend/app/models.py`](../backend/app/models.py) — Pydantic models mirroring the store; comments explain design rationale
- [`docs/PHASE4_PLAN.md`](../docs/PHASE4_PLAN.md) — mastery/decay design rationale
- [`docs/PHASE6_PLAN.md`](../docs/PHASE6_PLAN.md) — SM-2 per-item scheduler and study plan design
- [`docs/MASTER_PLAN.md`](../docs/MASTER_PLAN.md) — schema version milestones + Wave 2 correctness work

## Uncertainties & contradictions
- **Unresolved**: `track_kind = 'path'` only in v0 of the Study Scheduler — Courses parity (a `track_kind='course'` row) is future work with no schema change required.
- **Unresolved**: `activity` rows feed learning streaks but `brief_visits` and `news_events` are deliberately kept separate from them. The exact streak query behavior if a user only reads news (no quiz attempts) is not documented.
- **Contradiction**: `schema.py`'s doc comment on `question_mastery` says v2 stores get the Phase-6 SM-2 columns via an ALTER migration, but the `MIGRATIONS` dict uses key `3` (SCHEMA_VERSION 3), not `2`. The ALTER is additive and idempotent, so no data is lost, but the comment is imprecise.

## Related pages
- [Architecture](Architecture.md) — the four data layers this table set implements
- [Mastery-And-SR](Mastery-And-SR.md) — how `topic_mastery` and `question_mastery` are read and computed

## Relevance to current work
Any new feature that writes user state must use SQLite (not sidecars); pick up the schema version
and add a `CREATE TABLE IF NOT EXISTS` + an idempotent `ALTER TABLE ADD COLUMN` migration entry.
Course-namespaced progress goes under `course:<slug>`, path-namespaced under `notebook_id` (the
real notebook id). The local-day rule applies to any new table with a `day` column.

_Last reviewed: 2026-07-26_
