# Learning Hub — Backlog

_Ideas captured for later. Not committed work; a parking lot so good ideas don't get lost.
See `SPEC.md` for the agreed product and `docs/PHASE1_PLAN.md` for what's already built._

---

## Episode review + quiz workflow (`/episode-review` skill)

The conversational "finish an episode → reflect → quiz → log" flow. **In progress** on
branch `claude/episode-review-quiz-workflow`. The skill (the interactive tutor) lives in the
main Claude Code session; durable memory lives in the SQLite store (`attempts`,
`question_mastery`, `topic_mastery`, `reflections`) — not in any agent's internal state.

### ✅ Shipped (Phase 6): the study planner — as deterministic backend code, not a subagent

The "what do I do right now" planner is built (`backend/app/study/planner.py` +
`GET /api/study-plan` + the **Today's plan** page). As predicted below, a subagent was the wrong
primitive: the planner is a pure, deterministic function over the store (ranked SR items → a
bounded, interleaved session), not a one-shot LLM call. It now sits on top of a real per-question
**SM-2 scheduler** (`backend/app/store/scheduler.py`) that supersedes the old uniform half-life
for per-item scheduling. The captured-but-hidden **reflections** are also now surfaced
(`GET /api/reflections` + a journal on the Progress page). See `docs/PHASE6_PLAN.md`.

The two ideas below are kept for the historical reasoning; the planner half is now done.

### Idea: a "study planner" subagent (deferred — superseded by Phase 6 backend code)

A subagent is the **wrong** primitive for the tutoring conversation itself — a Claude Code
subagent runs in an isolated context, does one task, and returns a single message; it can't
hold the turn-by-turn dialogue with the user (reflection, one-question-at-a-time quizzing,
mid-question hints). That interactive role belongs to the **skill**, loaded into the main
session where the user is actually talking. "Persistent memory" is also not a subagent feature
(subagents are stateless across runs) — the persistence is the **DB + a learner-profile doc**.

Where a subagent *does* earn its place is as a discrete, **non-interactive analysis worker**
the skill delegates to at a specific moment — context-heavy, one-shot, returns an artifact:

- **Study planner** — "read my entire `attempts` + `reflections` + `question_mastery` history
  and produce a prioritized 'what to review next' plan." Natural fit for an isolated context
  that returns a single ranked list. This is also the seed of the Phase-4 spaced-repetition
  "Review next" queue.
- **Targeted practice generator** — "generate a fresh practice question aimed at the concept
  I keep missing" (derived from `question_mastery.miss_count`).
- **Episode pre-brief** — "summarize this episode's study guide into ~5 review points" before
  the reflection step.

**Why deferred:** only worth building once there are enough logged attempts/reflections to
analyze, and after the Phase-4 mastery-decay scoring function exists (the planner should call
it rather than reinvent ranking). Until then, the skill does lightweight "review next"
suggestions inline from the latest attempt.

### Companion idea: a learner-profile doc

A small markdown profile (qualitative memory the structured DB can't hold — learning style,
recurring confusions, preferred explanation depth) that the skill reads at the start of each
session and updates at the end. Makes the tutor feel like it *remembers you*. Pairs with the
study-planner subagent (which would read it as context). Stub now, populate as the skill runs.

---

## Other parked ideas

- **"Generate from hub" button** — kick off a new NotebookLM audio series from the hub UI
  (today that lives in the `audio-series` skill; SPEC marks it explicitly out of v1).
- **Hosted phone access** — remove the "Mac must be running on the same LAN" constraint.

### ✅ Shipped: `custom_topics` CLI writer + Phase-5 UI

Built `app.topics.custom` (`add` / `list` / `update`, JSON out) + `app.store.db` helpers
(`add_custom_topic` / `list_custom_topics` / `get_custom_topic` / `update_custom_topic`) +
`tests/test_custom_topics.py`. The `youtube-breakdown` skill registers topics through it.

**✅ Phase 5 done:** custom topics are now surfaced on the hub **home screen** — a
`GET /api/custom-topics` route (+ `POST` / `PATCH` to add/track from the UI) and a dedicated
"Custom" section with add + inline-edit. See `docs/PHASE5_PLAN.md`. This completes the SPEC
build order (Phases 1–5).
