# Phase 2 Plan — In-hub Quiz Player

_The headline feature. Take a NotebookLM-generated quiz **inside the hub**, get auto-graded by
the verified offline oracle, see per-question rationales on misses, and have every attempt
saved. Builds on the already-shipped grading oracle (`app/quiz/grading.py`) and the
integrity-preserving session logic (`app/quiz/session.py`)._

See `SPEC.md` §Screens (Quiz player) and `docs/PHASE1_PLAN.md` for what's already built.

## What already exists (reused, not rebuilt)
- **`app/quiz/grading.py`** — `load_quiz` (contract validation) + `grade_quiz` (the oracle).
  Pure, offline, tested (`tests/test_quiz_oracle.py`).
- **`app/quiz/session.py`** — `cmd_prepare` / `cmd_grade`. **Integrity property:** `prepare`
  stashes the *keyed* quiz to a cache session file and returns an **answer-key-free** player
  view (option text + hint only — no `isCorrect`, no rationale); only `grade` reads the keyed
  file. The HTTP API is a thin wrapper around these so the answer key can never reach the client.
- **`app/store/db.py:record_attempt`** — persists `attempts` + `attempt_answers` + the raw
  mastery/activity signal in one transaction. Already wired by `cmd_grade`.
- **`app/nlm/client.py:download_quiz`** — fetches the quiz JSON from `nlm`.

## The gap
There is **no HTTP route** and **no frontend** for taking a quiz. The `Take` button on the
topic page is a disabled "soon" stub and `QuizRef.takeable` is hard-coded `False`.

## Design
A thin HTTP layer over the existing session logic, plus an interactive React player.

### Backend
1. **`cmd_prepare` injectable client** — add an optional `client: NlmClient | None` param so the
   route can pass the DI-overridable client (tests + parity with the rest of the API). The CLI
   path is unchanged (defaults to `NlmClient()`).
2. **`app/api/quiz.py`** (new router, included in `main.py`):
   - `POST /api/topics/{notebook_id}/quizzes/{artifact_id}/prepare` → calls `cmd_prepare`.
     Returns `QuizPrepareResponse` (`ok`, `auth`, `session_id`, `title`, `total`, `questions[]`).
     Graceful, never a 500: `NlmAuthError` → `ok=false`, `auth.ok=false` + "run `nlm login`"
     message; other `NlmError`/`QuizValidationError` → `ok=false` + a calm `error` string.
   - `POST /api/quiz/grade` → calls `cmd_grade`. Body `{ session_id, answers, hints?,
     mark_listened? }`. Returns `QuizGradeResponse` (`score`, `total`, `pct`, `review[]`,
     `attempt_id`, `episode_marked_listened`). Unknown/expired session → `404`.
3. **`models.py`** — add `QuizPlayerQuestion`, `QuizPrepareResponse`, `QuizGradeRequest`,
   `QuizReviewItem`, `QuizGradeResponse`. Mirror into `frontend/src/api/types.ts`.
4. **`catalog/build.py`** — flip `QuizRef(..., takeable=True)` (the "Phase 2 flips this on" note).

### Frontend
5. **API client** (`api/client.ts`) — `prepareQuiz(notebookId, quizId)` + `gradeQuiz(body)`.
6. **`pages/QuizPlayer.tsx`** + route `/topics/:id/quiz/:quizId` in `App.tsx`. One-question-at-
   a-time card flow: progress (Q _x_ of _N_), radio options, optional **Show hint** (tracked as
   `used_hint`), Back/Next, Submit on the last card. Then a **review screen**: big score +
   percent, per-question ✓/✗ with the chosen vs. correct option and the rationale on misses,
   plus **Retake** and **Back to topic**. Calm auth/error banners reuse `Banner`.
7. **`pages/TopicDetail.tsx`** — turn the disabled stub into a real `Link` to the player when
   `q.takeable`.

### Integrity guard (must hold)
The `prepare` response and `QuizPlayerQuestion` carry **no** `isCorrect`/`correct_index`/
`rationale`. Verified by a test asserting those keys never appear in the prepare payload.

## Tests (`tests/test_quiz_api.py`)
- `prepare` (mocked `nlm` runner returning `docs/fixtures/sample-quiz.json`) returns the player
  view; assert **no answer key leaks** (no `isCorrect`/`correct_index`/`rationale`).
- all-correct answers → full score + attempt persisted; a wrong answer → lower score and the
  `review` exposes `correct_index` + rationale.
- auth failure (runner returns "not logged in") → `ok=false`, `auth.ok=false`, "nlm login" msg.
- grade with an unknown `session_id` → `404`.

## Done = 
`make test` green (incl. new quiz-API tests), `make typecheck` + `make build` clean, and the
player drives a full take→grade→review loop against the sample quiz. Live click-through needs a
browser + `nlm` (local-only); in this cloud session it's verified via the API + the offline
fixture end-to-end.
