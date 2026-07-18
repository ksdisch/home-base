# Home Base — Backlog

_Ideas captured for later. Not committed work; a parking lot so good ideas don't get lost.
See `SPEC.md` for the agreed product and `docs/PHASE1_PLAN.md` for what's already built._

---

## 🏠 Home Base evolution — Morning Brief (kickoff approved 2026-07-13)

The repo's next arc: evolve the hub into Kyle's daily home base — a self-updating morning
brief across his topics with inline notes, learning riding along. Full contract:
[`docs/KICKOFF-home-base.md`](docs/KICKOFF-home-base.md).

- [ ] **M0 — sweep quality week:** per-topic sweep prompts + a `make sweep` runner; ~5–7 daily
      manual runs on pilot topics (AI/LLMs · fantasy football · market/tech news); 2-min A–F
      grade each morning. Go/no-go gate before ANY UI work. _In flight — grading through
      ~2026-07-19 in `docs/M0-sweep-grades.md`._
- [x] **M1 — the brief page:** home route renders stored sweeps (topic sections · digests ·
      sources · as-of stamp) + manual refresh + visit log; current home → "Learning" tab.
      _✅ shipped 2026-07-13 (PR #36, `docs/M1_PLAN.md`; deliberate Day-0 override of the M0 gate)._
- [x] **M2 — full roster + notes:** all topics with seasonal pause flags (config file), inline
      notes on brief items, "Your learning" section on home.
      _✅ shipped 2026-07-14 (roster PR #38 + notes/strip PR, `docs/M2_PLAN.md`; second deliberate override)._
- [x] **M3 — hands-off:** scheduled sweeps (launchd on-wake catch-up), dedup vs history, cost
      guardrails, curation polish.
      _✅ shipped 2026-07-15 (PR #43, `docs/M3_PLAN.md`; third deliberate override) — first
      unattended 06:00 fire verified clean 2026-07-16._
- [x] **M4 — audio brief:** ~5-min narrated MP3 of each sweep via local Kokoro + 🎧 player on
      Today. _✅ shipped 2026-07-16 (PR #45, `docs/M4_PLAN.md`; picked from the post-M3 menu)._
- [x] **M5 — chat with the brief:** ask follow-ups on brief items. _✅ shipped 2026-07-16
      (PR #47, `docs/M5_PLAN.md`; approach A from its explore-plan — per-item Ask, no web
      tools, save-as-note)._
- [ ] **M6 — mobile:** the brief in your pocket — Tailscale tailnet reach, FastAPI serves
      the built frontend on one port + KeepAlive LaunchAgent, installed PWA with
      cached-last-brief offline honesty, mobile-first pass on the morning loop.
      _📋 planned 2026-07-18 (`docs/M6_PLAN.md`; fourth deliberate override of the
      M0-verdict gate, zero new LLM surface; build pending)._

Deferred by the brief: ESPN league integration · auto-courses ·
breaking-news alerts · public writing. _(Mobile was promoted to M6 on 2026-07-18.)_

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
- **Hosted phone access** — remove the "Mac must be running" constraint entirely (true
  hosting; an architecture split — sweeps, Kokoro, `nlm`, and SQLite are Mac-local by
  design). _M6 (planned 2026-07-18) retires the same-LAN half via Tailscale; this parked
  item is now only the remaining half._
- **Migration ledger hardening** — found 2026-07-16: the live store's `question_mastery` was
  missing the five v3 SM-2 columns even though `schema_migrations` recorded v3 as applied
  (the table was empty and in its Phase-1 shape — most plausibly dropped/recreated outside the
  app, e.g. via the sqlite MCP or a manual session; every SM-2 surface 500'd against the real
  store until the columns were re-added by hand, with a file backup at
  `backend/data/learning-hub.sqlite.bak-pre-v3-repair-20260716`). Idea: make `init_db` verify
  reality instead of trusting the ledger — e.g. check `PRAGMA table_info` for each migration's
  columns (or re-run the idempotent ALTERs unconditionally, since `_safe_alter` already
  tolerates duplicates) so a poisoned/orphaned ledger row can't silently skip a migration.

### ✅ Shipped: `custom_topics` CLI writer + Phase-5 UI

Built `app.topics.custom` (`add` / `list` / `update`, JSON out) + `app.store.db` helpers
(`add_custom_topic` / `list_custom_topics` / `get_custom_topic` / `update_custom_topic`) +
`tests/test_custom_topics.py`. The `youtube-breakdown` skill registers topics through it.

**✅ Phase 5 done:** custom topics are now surfaced on the hub **home screen** — a
`GET /api/custom-topics` route (+ `POST` / `PATCH` to add/track from the UI) and a dedicated
"Custom" section with add + inline-edit. See `docs/PHASE5_PLAN.md`. This completes the SPEC
build order (Phases 1–5).

### ✅ Shipped: Phase 7 — Courses (course-pipeline vertical slice, M1)

Plan-then-autonomous **course creation**. A course is a hub-native sidecar (content on disk,
progress in SQLite). Shipped: the manifest format + `app.courses` loader/CLI bridge, the
`/api/courses` read+track surface, the **Courses** UI (list + detail/player with inline lessons,
flashcards, diagrams, lesson-complete progress), the `course-builder` skill + `/build-course`
command, and a bundled example course. See `docs/PHASE7_PLAN.md` + `docs/COURSE_PIPELINE_SPEC.md`.
(Renumbered from "Phase 6" on the course branch — the SR work shipped as Phase 6 first.)

**Next on the course epic (M2+):** take a course quiz *in the existing quiz player* + flashcard
review UI (the quiz JSON is already hub-shaped); live Mermaid rendering; exercises/projects/
capstone with rubrics; NotebookLM enrichment folded into the automated pipeline; in-hub
regenerate/edit. The full roadmap is in `docs/COURSE_PIPELINE_SPEC.md`.
