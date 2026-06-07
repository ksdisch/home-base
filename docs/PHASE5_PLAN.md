# Phase 5 Plan — Custom (non-NotebookLM) topics on the home screen

_The last SPEC build-order milestone. SPEC §Screen 5: "add a book / YouTube series / loose
interest with no NotebookLM artifacts; track with manual progress + notes." The **writer +
store are already built** (`app.topics.custom` CLI + `app.store.db` helpers + `custom_topics`
table, all tested in `test_custom_topics.py`); BACKLOG confirms only the **read API + UI**
remain. This phase folds in the small write API too so the feature is actually usable from the
hub, not just the CLI._

## What already exists (reused, not rebuilt)
- **`custom_topics` table** (`store/schema.py`) — `id, title, notes, progress_pct, created_at,
  updated_at`.
- **Store helpers** (`store/db.py`) — `add_custom_topic` / `list_custom_topics` /
  `get_custom_topic` / `update_custom_topic`, with input validation (non-empty title, 0–100
  progress) and an `activity` row per write (feeds streaks). Fully unit-tested.
- **Grouping** — `grouping.py` already defines the `custom` group + "Custom" label; the home
  `GroupSection` even has a "coming in a later phase" placeholder for `key === "custom"`.

## The gap
The custom-topics store has **no HTTP surface** and **no UI**. The catalog's `GROUP_ORDER`
emits an always-empty `custom` notebook group (nothing maps to it — custom topics aren't
notebooks and don't fit `NotebookCard`). Phase 5 gives them their own endpoint + section.

## Design — a small CRUD router + a self-contained home section

Custom topics are a *different shape* from notebook cards (no `notebook_id`/sidecar/quizzes), so
they get their own models + endpoint + card, rendered as a dedicated "Custom" section on Home —
**not** shoehorned into `Group.notebooks`.

### Backend
1. **`models.py`** — `CustomTopic` (mirror the store row), `CustomTopicsResponse`
   (`generated_at`, `topics[]`), `CustomTopicCreate` (`title`, `notes=""`, `progress_pct=0`),
   `CustomTopicUpdate` (all optional). Mirror into `types.ts`.
2. **`app/api/custom_topics.py`** (new router, included in `main.py`):
   - `GET /api/custom-topics` → `{generated_at, topics}` (most-recently-updated first; empty
     store → `[]`, never 500).
   - `POST /api/custom-topics` → create; store `ValueError` → `400`.
   - `PATCH /api/custom-topics/{id}` → patch given fields; unknown id → `404`, bad input → `400`.
   Wrap the existing store helpers; the route is thin, the validation already lives in the store.
3. **`grouping.py`** — drop `custom` from `GROUP_ORDER` (keep the `GROUP_LABELS` entry) so the
   notebook catalog stops emitting an empty Custom group; the Home page renders the real one.

### Frontend
4. **`api/types.ts`** — `CustomTopic`, `CustomTopicsResponse`, `CustomTopicCreate`,
   `CustomTopicUpdate`; **`api/client.ts`** — `customTopics()`, `addCustomTopic()`,
   `updateCustomTopic()` (POST/PATCH helpers).
5. **`components/CustomTopicForm.tsx`** — one small inline form reused for add **and** edit
   (title, notes textarea, a 0–100 progress slider); calls back on save.
6. **`components/CustomTopicCard.tsx`** — title, notes preview, a progress bar + `%`, a last-
   updated date, and an "Edit" toggle that swaps in the form (PATCH). Reuses the Tailwind tokens.
7. **`pages/Home.tsx`** — fetch `/api/custom-topics` alongside the catalog; render a "Custom"
   section after the notebook groups with the cards + an "+ Add custom topic" affordance.
   Optimistic-ish: re-fetch the list after a successful add/update. Calm empty state ("Track a
   book, a YouTube series, or a loose interest…").
8. **`GroupSection.tsx`** — remove the now-dead `custom` placeholder branch.

## Tests (`tests/test_custom_topics_api.py`)
- `GET` empty store → 200 / `topics == []`.
- `POST` valid → 200 + echoes the row; it then appears in `GET` (most-recent first).
- `POST` invalid (blank title; progress 101) → `400`.
- `PATCH` progress + notes → reflected, `created_at` stable, `updated_at` bumped.
- `PATCH` unknown id → `404`; `PATCH` bad progress → `400`.
- A POST/PATCH logs an `activity` row (streak signal) — assert via the store.
- Route never 500s; ordering deterministic.

## Done =
`make test` green (incl. the new API tests), `make typecheck` + `make build` clean, and the full
`GET → POST → GET → PATCH` round-trip verified over HTTP against a live backend (add a topic, set
its progress, edit it). Live click-through of the rendered Home section needs a browser (local-
only); in this cloud session it's verified via the API round-trip + a clean production build.
