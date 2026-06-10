# Phase 7 — Courses M3: flashcard review (SM-2) + live Mermaid

_The third course-pipeline milestone. M2 made course **quizzes** playable with per-question SM-2;
M3 gives course **flashcard decks** the same treatment — a self-graded, SM-2-scheduled review
flow — and upgrades course diagrams from labeled Mermaid source to **live rendered graphs**._

## Key decisions (gated with the user, 2026-06-10)

- **Grading model: Anki-style 4-button.** After flipping a card the learner self-grades
  **Again / Hard / Good / Easy → SM-2 quality 2 / 3 / 4 / 5**. `scheduler.next_state()` is reused
  **unchanged** (it already takes any quality 0–5; q=4's ease delta is exactly 0 — classic SM-2).
  Quizzes keep their objective `quality_from_signal`; flashcards get a parallel
  `quality_from_grade`.
- **Where review state lives: a new `flashcard_mastery` table** (schema v4), mirroring
  `question_mastery`'s SM-2 columns but keyed `(course_slug, deck_path, card_key)`. A separate
  table — not `question_mastery` under the `course:` namespace — because a self-graded card has no
  attempt/score/answer rows, and every quiz-side aggregate (`course_quiz_progress`,
  `sr_plan_items`, the notebook filters) can stay untouched instead of growing flashcard guards.
  Due counts are **derived** on read (`mastery.item_is_due`); no stored progress %.
- **Card identity:** `card_key = sha1(front)[:16]` — the exact `question_key` recipe, so state
  survives deck reordering and an edited front is honestly a new card. Duplicate fronts in one
  deck dedupe to one card (first wins).
- **Mermaid: bundle `mermaid`, lazy-loaded.** The frontend's first runtime dependency beyond
  react/react-dom/react-router — judged worth it because it's dynamic-`import()`ed (a separate
  code-split chunk fetched only when a diagram is actually opened; the main bundle stays lean),
  works offline/in-cloud for every course past and future, and renders with
  `securityLevel: "strict"`. A parse failure falls back to the labeled source block.

## Backend

1. `store/schema.py` — `SCHEMA_VERSION = 4`; new idempotent `flashcard_mastery` table
   (`course_slug, deck_path, card_key` PK; `last_grade`; the SM-2 columns
   `ease/interval_days/reps/lapses/last_review_at/due_at`). Pure CREATE — no ALTER migration
   needed.
2. `store/scheduler.py` — `GRADES = ("again", "hard", "good", "easy")` +
   `quality_from_grade(grade) → 2/3/4/5` (ValueError on junk).
3. `courses/manifest.py` — `card_key(front)`; `load_flashcard_deck(slug, rel_path)` →
   `[{key, front, back}]` (path-confined, validated, deduped; `CourseError` when malformed).
4. `store/db.py` —
   - `record_flashcard_review(slug, deck_path, card_key, grade, *, now)` — advances the card's
     SM-2 state off its previous row + writes an `activity` row
     (`notebook_id='course:<slug>'`, `kind='flashcard_review'` — streaks stay source-agnostic).
   - `course_flashcard_progress(slug, *, now)` — per-deck `{tracked_cards, due_cards,
     last_review_at}` (mirrors `course_quiz_progress`).
   - `flashcard_card_states(slug, deck_path)` — per-card state for the session endpoint.
5. `models.py` — `CourseFlashcardDeckState`, `CourseFlashcardsResponse`, `FlashcardSessionCard`,
   `FlashcardSessionResponse`, `FlashcardGradeRequest` (grade is a `Literal`, so junk grades 422
   for free), `FlashcardGradeResponse`.
6. `api/courses.py` —
   - `GET /api/courses/{slug}/flashcards` — the manifest's flashcard materials joined with
     `course_flashcard_progress`: `{path, lesson_id, module_id, title, card_count, tracked_cards,
     due_cards, last_review_at}`. 404 on an unknown course.
   - `POST /api/courses/{slug}/flashcards/session?path=…` — the full deck with per-card review
     state (`card_key, front, back, new, due, reps, due_at`), ordered most-overdue → new → not
     yet due; the client builds its queue from the `due` flag. Calm `ok:false` (never a 500) on a
     missing/escaping/non-deck path. Fronts+backs are *supposed* to reach the client here — it's
     self-graded; there is no answer-key invariant for flashcards.
   - `POST /api/courses/{slug}/flashcards/grade` — body `{path, card_key, grade}`; the card must
     exist in the deck file (404 otherwise); persists via `record_flashcard_review` and returns
     the new SM-2 state.

## Frontend

7. `api/types.ts` + `api/client.ts` — mirror the new models; `courseFlashcards(slug)`,
   `flashcardSession(slug, path)`, `gradeFlashcard(slug, body)`.
8. `App.tsx` — `/courses/:slug/flashcards` route (deck `path` rides in `?path=`, like quizzes).
9. `pages/FlashcardPlayer.tsx` — the deck player: queue = due+new cards (with a "review anyway"
   path when nothing's due); front → **Show answer** → Again/Hard/Good/Easy → next (each grade
   POSTs immediately, so abandoning a session mid-way loses nothing); end-of-session summary
   (per-grade counts + review-again + back to course). Each card is graded **once** per session —
   "Again" cards return tomorrow via SM-2 rather than re-queueing in-session (honest v1 limit).
10. `pages/CourseDetail.tsx` — flashcard materials get a **Review deck** button + "N due" badge
    (fed by one `courseFlashcards` fetch, mirroring the quizzes fetch); the inline browse grid
    stays. Diagram materials render through the new component:
11. `components/MermaidDiagram.tsx` — lazy `import("mermaid")`, `startOnLoad:false`,
    `securityLevel:"strict"`, render-to-SVG with the source block as the error/loading fallback.

## Tests (definition of done)

`tests/test_courses_flashcards.py` (house style: `TestClient(app.main)`, per-test isolated SQLite
via env, the bundled example course): `/flashcards` lists the example deck with zeroed state +
404s an unknown course; session fetch returns keyed cards (all new+due initially); grade
round-trip persists `flashcard_mastery` and the four grades map to the right SM-2 transitions
(`again` → lapse+1/reps 0/due tomorrow; `good` first rep → due +1d; `easy` raises ease) with due
counts surfacing after the interval elapses (injected clock); junk grade → 422; unknown card →
404; traversal / non-deck paths → calm `ok:false`; flashcard reviews **don't touch** the notebook
surfaces (`/review`, `/study-plan`, `/progress` headline counters) while the activity streak counts
the day; and a duplicate-front deck dedupes. Plus `test_scheduler.py` gains the
`quality_from_grade` mapping and `test_migrations.py` pins the v3→v4 upgrade. Frontend: vitest
covers the player's flip→grade→summary loop (mocked fetch + mocked `mermaid`); `tsc` + build stay
clean. `make test` + `make lint` green.

## Out of scope (M4+)

Interleaving course items (questions *or* cards) into the cross-notebook Study plan;
in-session relearning steps for "Again" cards; exercises/projects/capstone + rubrics; NotebookLM
enrichment; in-hub course regenerate/edit; any change to the NotebookLM topic surfaces.
