# Learning Paths — an AI study-designer over your NotebookLM library

**Status:** Approved design — brainstorm 2026-07-21 (interactive, with the visual companion). Routing to `/explore-plan` for the Jacobian Lens vertical slice. Not yet built. Proposed as **M8**.

_Learning stops being a flat grid of NotebookLM topics with a dead "mastery —" chip and becomes an AI study-designer: for a topic, Claude reads the real artifacts and composes an ordered **path** — arranging what exists (listen → read → drill → quiz) plus light labeled glue — scored on three honest axes (coverage · SR recall · self-rated confidence). Because the loop's signal gets richer, Plan and Progress are rebuilt around it: Plan splits into Continue + Review lanes; Progress charts three trends. Courses barely changes — it already is this shape._

## Premise

The Learning tab (`/learning` → `Home.tsx`, fed by `GET /api/catalog`, `backend/app/api/catalog.py:40`) is not really a quiz tab — it's a **multi-format library with a quiz-only scorer**. Every topic card already advertises rich formats ("12 audio · 1 quiz · 1 flashcards"), but of all of them only a **graded quiz** writes into the learning loop: `record_attempt()` (`backend/app/store/db.py:375`) is the sole writer of `attempts` + `topic_mastery` + `question_mastery` (SM-2) + `activity`. Listening is a boolean ping; reading a study guide is untracked; flashcards feed mastery only inside Courses (namespaced `course:%`). So the content is multi-modal; the **scoring is single-modal**.

Everything downstream is a *reader* of that one write event. `mastery = decayed quiz score` (`backend/app/store/mastery.py:79`); the Learning card shows "mastery —" whenever a topic has no `topic_mastery` row (`catalog.py:24` `_stamp_mastery` silently skips it); Plan is empty until an SR question is due (`backend/app/api/study_plan.py:50` `has_data`); Progress charts only quiz scores. The store confirms the loop has **never run** — `attempts`, `topic_mastery`, `question_mastery` are all empty — and the only way to seed it is buried three clicks deep at `TopicDetail.tsx:168`, past a dead "mastery —" chip whose tooltip says "Take a quiz" but offers no button (`NotebookCard.tsx:35`).

**Why now:** the artifacts already exist, the SM-2 core + quiz/flashcard players + the grounded `claude -p` lane (M5) are all built and proven. The missing piece isn't plumbing — it's a richer *front* that makes more than the quiz count as learning, and a mastery model honest enough to carry it.

## The bet

That the unit of the Learning tab should be a **guided path**, not an artifact inventory — and that the path's order should be **LLM-composed per topic** (a "learning designer"), because a NotebookLM topic has no inherent sequence (34 audio + 1 quiz, or 26 audio + 11 quizzes — someone must impose "do this, then this"). The designer **arranges** real artifacts and adds light **connective glue** (intro, per-step focus, bridge-checks where a topic has a gap, recap), every step grounded in an artifact that actually exists — the M0 no-fabrication bar applied to pedagogy. A path scored on three axes turns "I listened to 12 audios but never tested" from a lie (mastery inflated) into an honest picture (coverage high, mastery still "—"). And a generated path has steps to do **on day one**, which is what finally lights the cold loop: Plan's Continue lane is non-empty before any quiz exists.

## Design decisions (all locked in the 2026-07-21 brainstorm)

1. **Guided paths**, not a flat grid — Learning becomes journeys over your topics.
2. **LLM-composed per topic** (a learning designer) — keeps Learning distinct from Courses (authored curricula); they share the engine underneath.
3. **Arrange + connective glue** — real artifacts are the spine; generated intro/focus/bridge/recap are clearly labeled. Not a full authoring pass (that's `/build-course`).
4. **Three axes:** **Progress** (path coverage, all steps incl. listen/read) · **Mastery** (recall, earned only by testing, SM-2-decayed — unchanged) · **Confidence** (self-rated).
5. **Path player = outline + detail** — left-rail TOC of the whole path, right pane the active step + a live three-axis panel. Closest to the existing Courses look (consistency).
6. **Plan = two lanes:** **Continue** (coverage-driven, next path steps, non-empty day one) + **Review** (recall-driven, SR-due). Reuses today's minutes budget + interleaving.
7. **Learning card** = three live axes + next-step preview + one primary action (Generate / Continue / Review). Replaces the dead "mastery —". "NotebookLM ↗" stays as a quiet secondary link.
8. **Progress** = three trend lines (coverage · recall · confidence) + the heatmap relabeled honest "activity" (fixing the current bug where it implies quizzes you didn't take — the one lit cell today is a `custom_topic_added` event, not a quiz).
9. **On-demand generation** — a path is composed when you press ✨ Generate (or on first open). Zero LLM cost until asked; the Generate press doubles as the loop's seed. (Batch-overnight is a natural later upgrade, reusing the 06:00 scheduler.)
10. **Bridge-checks = formative only** — the generated open-recall prompts are graded by Claude against the topic's real sources (reusing the M5 grounded `claude -p` lane) for feedback + step completion + a confidence prompt, but they do **NOT** move Mastery. Mastery stays earned only by real quiz/flashcard SR items — open recall added without diluting the honest score.
11. **Ship as a vertical slice** (build route: 3 → 2): build the full adaptive experience for **one** topic (the Jacobian Lens notebook) end-to-end, prove path quality + the three-axis model + the tab changes, then scale to the rest.

## Architecture (🟢 new · 🔵 reuse · ⚪ unchanged)

1. **Generate (on-demand).** ⚪ NotebookLM catalog (real artifacts, sidecar parse) → 🟢 **Learning Designer** [🔵 grounded `claude -p`, the M5 lane; validates every step against the catalog — M0 bar] → 🟢 `path.json` sidecar per topic (mirrors `course.json`).
2. **Play.** The 🟢 outline+detail player reads `path.json`; each step's "Start" routes to the right surface and feeds an axis:
   - 🎧 audio → 🔵 audio player → mark listened → **Coverage**
   - 📖 read → 🔵 study-guide view → **Coverage**
   - 🃏 flashcards → 🔵 `FlashcardReview` → SR → **Mastery**
   - ❓ quiz → 🔵 `QuizPlayer` → `record_attempt` → SR → **Mastery**
   - ✨ bridge-check → 🟢 grounded `claude -p` grade → feedback → **Coverage + Confidence** (never Mastery)
   - ✍️ reflect → 🔵 note → **Coverage**
3. **Signals (three axes).** 🟢 Coverage (new path-step store) · ⚪ Mastery (`topic_mastery`/`question_mastery` SM-2 decay — untouched) · 🟢 Confidence (new self-rating store).
4. **Consumers (rebuilt tabs).** 🟢 Learning card (3 axes + next step + Generate/Continue/Review) · 🟢 Plan two lanes (Continue = coverage, Review = mastery SR) · 🟢 Progress three trends + honest heatmap.
5. **Adaptive loop (the slice's ambition).** Signals feed back into the Designer for a *light* re-plan: low recall/confidence inserts a practice step or re-surfaces the relevant episode; high lets you skip ahead. Cheap reorder/insert, not a full regenerate.

**Honest build tally:** the real work is the **Designer + `path.json` + two new signal stores + the three rebuilt tabs**. Grading, SM-2, the quiz/flashcard players, the catalog, and the `claude -p` lane are all reused.

## Credible first step (the vertical slice)

Build it end-to-end for the **Global Workspace in LLMs — the Jacobian Lens Paper** notebook (rich, real, lopsided: 12 audio · 1 quiz · 1 flashcards · **no study guide** — the case that makes the arrange+glue designer earn its keep, since it must insert a generated ✨ bridge-check where a study guide would go). Ship: on-demand Generate → `path.json` → outline+detail player with the three axes → the six step-Start behaviors → the two-lane Plan reading the new coverage store alongside the existing SR review → the three-trend Progress. Then judge path quality and whether the three-axis model feels right *before* scaling to the other topics. Route this via `/explore-plan` (steered — approve the plan before code).

## Dependencies (all verified present; mostly read/extend)

- Designer: the M5 grounded `claude -p` lane (`backend/app/chat.py`, `docs/M5_PLAN.md`) — subscription lane, API key scrubbed, no web tools.
- Catalog + sidecar parse: `backend/app/api/catalog.py`, `backend/app/catalog/`; the `course.json` sidecar pattern to mirror: `backend/app/courses/manifest.py`, `next_actions.py:27`, lesson-completion store `backend/app/store/db.py:541`.
- SR core (unchanged): `backend/app/store/scheduler.py:83`, `backend/app/store/mastery.py:79`; note the deliberate course exclusion `NOT LIKE 'course:%'` at `mastery.py:162` & `:257` — the two-lane Plan must decide how topic paths surface here.
- Surfaces to rebuild: `frontend/src/pages/Home.tsx` (Learning), `StudyPlan.tsx` (Plan), `Progress.tsx` (Progress), `frontend/src/components/NotebookCard.tsx:35`; existing players `QuizPlayer.tsx`, `FlashcardReview.tsx`, `TopicDetail.tsx:168`.
- Contract: `frontend/src/api/types.ts` + `client.ts` (+ the `api-types-sync` skill / `contract-reviewer` agent).

## Explicitly out of scope (revisit later)

Authoring new content to fill gaps (the "arrange + author gaps" option — overlaps `/build-course`). Bridge-checks moving Mastery (decision 10 keeps them formative). Batch/overnight path generation (decision 9 is on-demand; overnight is a later upgrade). Merging Learning into Courses (they stay distinct, shared engine). Scaling beyond the Jacobian Lens slice until its quality is judged.

## Identity/positioning note

identity-shift: Learning stops being a *catalog you browse* and becomes a *tutor that composes your path* — Home Base's learning section gains a verb (study a designed journey) instead of a list. Distinct from Courses (human/`/build-course`-authored curricula): Learning Paths are AI-composed over your own NotebookLM library, on demand. The three-axis model (coverage · recall · confidence) also aligns Learning with how Courses already tracks progress — one honest vocabulary across the app.
