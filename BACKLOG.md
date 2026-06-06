# Learning Hub — Backlog

_Ideas captured for later. Not committed work; a parking lot so good ideas don't get lost.
See `SPEC.md` for the agreed product and `docs/PHASE1_PLAN.md` for what's already built._

---

## Episode review + quiz workflow (`/episode-review` skill)

The conversational "finish an episode → reflect → quiz → log" flow. **In progress** on
branch `claude/episode-review-quiz-workflow`. The skill (the interactive tutor) lives in the
main Claude Code session; durable memory lives in the SQLite store (`attempts`,
`question_mastery`, `topic_mastery`, `reflections`) — not in any agent's internal state.

### Idea: a "study planner" subagent (deferred)

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
