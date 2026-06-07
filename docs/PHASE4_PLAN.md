# Phase 4 Plan — Mastery decay + the spaced-repetition "Review next" queue

_The "rich tracking engine" payoff. Phases 2–3 **capture** the mastery signal (`topic_mastery`,
`question_mastery`, each with a `last_review_at`) and **read it back** as trends/streaks. Phase 4
turns that raw signal into a **decaying mastery score** and a **ranked "Review next" queue** — the
spaced-repetition nudge SPEC §"rich tracking engine" + §Screen 4 promised. Like Phase 3 this is
read + compute on data the hub already writes; no new capture._

See `SPEC.md` §Screens 4 (Progress / "Review next") and §"The rich tracking engine". The schema
(`backend/app/store/schema.py`) was shaped for exactly this: per-topic/-question scores that fade
against an injected clock.

## What already exists (reused, not rebuilt)
- **`record_attempt`** writes, per graded attempt: `topic_mastery(notebook_id, score, last_review_at)`
  (score = latest attempt fraction) and `question_mastery(…, score, miss_count, last_review_at)`
  (clean-correct 1.0 / hinted 0.5 / miss 0.0, with a running `miss_count`). The signal + the
  `last_review_at` timestamps the decay model needs are **already there**.
- **`store/progress.py`** — the Phase-3 pattern this mirrors: pure functions that take an injected
  clock (`compute_streaks(days, today)`) + read helpers that take an optional `db_path`.
- **`api/progress.py`** — the route pattern: resolve `notebook_id → title/group/topic_url` from the
  offline sidecar catalog, never 500, degrade to `has_data=false` on an empty store.
- **`NotebookCard`** model already carries `mastery` / `due_for_review` / `last_touched`
  placeholders (rendered as "—"); Phase 4 fills them in.

## The gap
Nothing turns the raw signal into *decayed* mastery or a *ranked* queue. `topic_mastery.score` is
the latest fraction with no time-fade; the home `due_for_review` badge is hardcoded `false`; there
is no "Review next" surface. The `review-next` skill ranks from a hand-written heuristic and notes
it should defer to "the Phase-4 mastery-decay scoring function" once it exists — this builds it.

## Design — a pure decay model + a read layer + a route, mirrored to the UI

### The model (pure, unit-tested, injected clock) — `app/store/mastery.py`
Honest and simple, not a fake SuperMemo. Mastery is **estimated current retention** = the last
stored score, faded by time since last review:

- **Half-life decay.** `decayed = score * 0.5 ** (days_since_review / HALF_LIFE_DAYS)`.
  `HALF_LIFE_DAYS = 14` (mastery halves every two weeks unreviewed). `days_since ≤ 0 → score`
  unchanged; `last_review_at is None → 0.0` (never practiced = no retention to credit).
- **Due.** `decayed < DUE_THRESHOLD (0.5)` → "due for review". A freshly-aced topic is not due;
  it becomes due as it fades, or immediately if the last attempt was weak.
- **Priority (queue ordering).** `priority = (1 - decayed) * 100 + miss_count * MISS_WEIGHT(5)`,
  capped. Lower retention dominates; unresolved misses break ties / push shaky topics up.
- All pure helpers take `now: datetime` and parse the stored `datetime('now')` strings
  (naive UTC) so tests are deterministic with no time-travel.

Read layer (takes optional `db_path`, like `progress.py`):
- `review_queue(now, *, half_life, threshold, db_path)` — join `topic_mastery` with per-notebook
  aggregated `question_mastery` misses; emit one row per practiced topic with
  `score / decayed / due / priority / days_since / total_misses / shaky_questions / reason`,
  sorted `due` first then `priority` desc.
- `due_topic_ids(now, *, db_path)` — the set of due `notebook_id`s, for the catalog badge.

### Backend wiring
1. **`models.py`** — `ReviewItem` (notebook_id, title, group/_label, topic_url, mastery, decayed,
   due, priority, days_since_review, total_misses, shaky_questions, last_review_at, reason) +
   `ReviewResponse` (generated_at, has_data, due_count, items). Mirror into `types.ts`.
2. **`api/review.py`** (new router, included in `main.py`): `GET /api/review` → builds the queue,
   resolves labels from the catalog (same offline helper as progress), never 500s, empty store →
   `has_data=false`.
3. **`api/catalog.py`** — after `to_groups`, stamp each card's `mastery` / `due_for_review` /
   `last_touched` from `topic_mastery` (decayed via the model). Keep `to_groups`/`to_card` **pure**
   (they're reused by `progress.py`'s label map) — do the DB stamp in the route, not the builder.

### Frontend
4. **`api/types.ts`** — `ReviewItem` + `ReviewResponse`; **`api/client.ts`** — `review()`.
5. **`components/NotebookCard.tsx`** — replace the "progress —" placeholder with a real mastery
   chip when `mastery != null` (tone by band), keep the existing `🔁 due for review` badge (now
   actually driven).
6. **`components/MasteryBar.tsx`** (tiny) — a calm 0–100 retention bar reused on the card + queue.
7. **`pages/Progress.tsx`** — a **"Review next"** section at the top (the actionable headline):
   each item = title, retention bar, reason ("retention ~40% · last practiced 12d ago" /
   "3 misses to clean up"), a "Review →" link to the topic. Empty/all-fresh → a calm "nothing due,
   you're current" note. Fetch `/api/review` alongside `/api/progress`.

### Skill
8. **`.claude/skills/review-next/SKILL.md`** — prefer the new `GET /api/review` (the Phase-4
   engine) when the backend is running; keep the raw-SQL heuristic as the offline fallback.

## Tests
- **`tests/test_mastery.py`** (pure): decay at 0 / 1× / 2× half-life; `None` last_review → 0;
  due threshold boundaries; priority ordering (lower retention ranks higher; misses break ties);
  timestamp parsing (naive `datetime('now')` form + tz-aware ISO).
- **`tests/test_review_api.py`** (HTTP, reuse the `test_progress_api` quiz-driving harness):
  empty store → 200 / `has_data=false` / `[]`; a just-taken attempt is **not** due (high
  retention); back-date its `last_review_at` in the store → it becomes due, appears in the queue,
  ordered by priority; a missed-question topic shows misses and outranks a clean one at equal age;
  `GET /api/catalog` reflects `due_for_review`/`mastery` for a crafted-sidecar notebook once its
  mastery is back-dated; route never 500s; labels fall back to id.

## Done =
`make test` green (incl. the new mastery + review tests), `make typecheck` + `make build` clean,
and `GET /api/review` drives the full decayed-mastery queue end-to-end against attempts created
through the quiz API — including the due-transition after back-dating a review — with the home
catalog badge + card mastery wired through. Live click-through of the rendered page needs a browser
(local-only); in this cloud session it's verified via the API, the pure-model unit tests, an
offline back-dating test, and a clean production build.
