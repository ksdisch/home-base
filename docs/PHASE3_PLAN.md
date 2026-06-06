# Phase 3 Plan — Progress dashboard (score trends + streaks)

_The "rich tracking" payoff. Phase 2 logs every attempt; this phase **reads that signal back**
and surfaces it: per-topic score trends, an activity streak, and the shakiest material — a calm
Progress screen. Builds entirely on data the hub already writes (`attempts`, `attempt_answers`,
`question_mastery`, `topic_mastery`, `activity`). No new data is captured; this is read + visualize._

See `SPEC.md` §Screens 4 (Progress) and §"rich tracking engine". Mastery **decay** and the
spaced-repetition **"Review next"** queue are explicitly Phase 4 — out of scope here.

## What already exists (reused, not rebuilt)
- **`record_attempt`** (`app/store/db.py`) already writes, per graded attempt: an `attempts`
  row (score/total/finished_at), `attempt_answers`, a raw `question_mastery` signal
  (`score`, `miss_count`, `last_review_at`), a `topic_mastery` row, and an `activity` row
  (`kind="quiz_attempt"`, plus `episode_listened` when marked). The data is **already there**.
- **`load_sidecars` + `to_groups`** (`app/catalog/*`) give an offline, no-auth
  `notebook_id → title/group` map to label progress rows (same source the home feed uses).

## The gap
Nothing **reads** the progress signal. There is no progress API and no Progress screen; the
`NotebookCard` progress fields are placeholders rendered as "—".

## Design — a read-only HTTP layer + a dependency-free React page

### Why no chart library
The frontend is deliberately tiny (React + router only). Rather than pull in Recharts (and a
cloud `npm install` of a new dep), Phase 3 ships **small inline-SVG charts** (`Sparkline`) — it
fits the minimalist grain, keeps `make build` clean, and the datasets are small. SPEC named
Recharts "or similar"; this is the "similar".

### Backend
1. **`app/store/progress.py`** (new, pure read layer over the store):
   - `compute_streaks(days, today) -> (current, longest)` — pure, unit-tested. `current` only
     counts if the latest activity day is today or yesterday (a streak that lapsed isn't "current").
   - `overall_summary(db_path)` — attempts total, distinct topics practiced, avg pct, last activity.
   - `activity_days(db_path)` / `activity_counts(db_path, days_back, today)` — distinct days +
     a per-day count series for the activity strip.
   - `topic_breakdowns(db_path)` — per notebook with attempts: count, last/best/avg pct,
     last_practiced, and the attempt `points[]` (finished_at + pct) for the trend line.
   - `shaky_quizzes(db_path, limit)` — `question_mastery` aggregated by (notebook, quiz):
     total misses + distinct shaky questions + last_review_at. Honest: the question **text**
     isn't stored (read-only hub), so we surface "N misses across M questions in this quiz" and
     link back to retake — not invented question prose.
2. **`models.py`** — `AttemptPoint`, `TopicProgress`, `ShakyQuiz`, `ActivityDay`,
   `ProgressSummary`, `ProgressResponse`. Mirror into `frontend/src/api/types.ts`.
3. **`app/api/progress.py`** (new router, included in `main.py`): `GET /api/progress` →
   assembles the above, maps `notebook_id → title/group` from the catalog, computes streaks
   from `activity_days`. Offline + no-auth like `/catalog` (never a 500; empty store →
   `has_data=false` with zeroed summary).

### Frontend
4. **`components/Sparkline.tsx`** — tiny inline-SVG line/area for a `number[]` (the trend).
5. **`api/client.ts`** — `progress()` → `GET /api/progress`.
6. **`pages/Progress.tsx`** + route `/progress` in `App.tsx`, and a **"Progress"** nav link in
   the header. Layout: a summary band (attempts · avg score · topics · 🔥 current streak ·
   longest), a calm activity strip (last ~5 weeks), per-topic cards (sparkline trend + last/best/
   avg + link to the topic), and a "Shaky spots" list. Empty state: a friendly "take a quiz to
   start your history" pointing home. Reuses `Banner`/`Badge` and the existing Tailwind tokens.

## Tests (`backend/tests/test_progress_api.py`)
- `compute_streaks`: empty → (0,0); a today-anchored run; a run that ended → current 0 but
  longest preserved; gaps; yesterday-anchored counts as current.
- `GET /api/progress` on an **empty** store → 200, `has_data=false`, zeroed summary, empty lists.
- After driving real attempts through the quiz API (reusing the `test_quiz_api` harness /
  sample fixture): summary counts + a topic breakdown with the right last/avg pct and a
  populated trend; a forced miss shows up in `shaky_quizzes`; titles resolve via a crafted
  sidecar root (fallback to `notebook_id` when unknown).
- Integrity/robustness: route never 500s; pct values rounded; ordering deterministic.

## Done =
`make test` green (incl. new progress tests), `make typecheck` + `make build` clean, and
`GET /api/progress` drives the full summary → per-topic trend → shaky-spots payload end-to-end
against attempts created through the quiz API. Live click-through (the rendered page) needs a
browser (local-only); in this cloud session it's verified via the API + an offline fixture and a
clean production build of the page.
