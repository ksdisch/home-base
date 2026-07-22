# Home Base — Backlog

_Ideas captured for later. Not committed work; a parking lot so good ideas don't get lost.
See `SPEC.md` for the agreed product and `docs/PHASE1_PLAN.md` for what's already built._

---

## 🏠 Home Base evolution — Morning Brief (kickoff approved 2026-07-13)

The repo's next arc: evolve the hub into Kyle's daily home base — a self-updating morning
brief across his topics with inline notes, learning riding along. Full contract:
[`docs/KICKOFF-home-base.md`](docs/KICKOFF-home-base.md).

- [x] **M0 — sweep quality week:** per-topic sweep prompts + a `make sweep` runner; ~5–7 daily
      manual runs on pilot topics (AI/LLMs · fantasy football · market/tech news); 2-min A–F
      grade each morning. Go/no-go gate before ANY UI work.
      _✅ closed 2026-07-19 — **verdict PASS** (zero fabrications all week; AI sweep prompt
      tuned). Grades + audit in `docs/M0-sweep-grades.md`._
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
- [x] **M6 — mobile:** the brief in your pocket — Tailscale tailnet reach, FastAPI serves
      the built frontend on one port + KeepAlive LaunchAgent, installed PWA with
      cached-last-brief offline honesty, mobile-first pass on the morning loop.
      _✅ shipped 2026-07-18 (PRs #55 + #56, `docs/M6_PLAN.md`; fourth deliberate override
      of the M0-verdict gate, zero new LLM surface; Mac-side live verify clean, phone-side
      proof pending Kyle)._

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
  design). _M6 (shipped 2026-07-18) retires the same-LAN half via Tailscale; this parked
  item is now only the remaining half._
- **Migration ledger hardening** — ✅ shipped (PR #52, drafted 2026-07-17): `init_db` now re-runs every forward
  migration unconditionally instead of gating on `schema_migrations` — the ledger records when
  a version was first seen, but the table's real shape decides what gets altered (`_safe_alter`
  already swallows "duplicate column"), so a poisoned/orphaned ledger row can no longer
  silently skip a migration. Consequence, documented at `MIGRATIONS` in `app/store/schema.py`:
  entries must stay idempotent-under-re-run (additive `ADD COLUMN`); a one-shot data backfill
  would need its own gate. Regression tests in `backend/tests/test_migrations.py` (poisoned-
  ledger heal + unknown-version ledger rows). _Original incident, 2026-07-16: the live store's
  `question_mastery` lost its five v3 SM-2 columns to a drop/recreate outside the app while the
  ledger still said v3 — every SM-2 surface 500'd until the columns were re-added by hand
  (file backup at `backend/data/learning-hub.sqlite.bak-pre-v3-repair-20260716`)._
- **M8 Designer — curate artifacts + rich-topic timeout** — ✅ SHIPPED (PR #134, 2026-07-22):
  bounded per-kind cap (`_MAX_PER_KIND`) + FOCUSED-path prompt + 180→240s timeout; live re-validated
  (engineering-abstractions 180s-timeout → ~90s/17 steps · jlens 17→13). Original finding: the
  on-demand Designer (PR #130)
  arranged *every* artifact into the path, so on the richest topics it (a) timed out at the 180s
  `claude -p` lane ceiling (confirmed 2026-07-22 on `engineering-abstractions`, ~49 artifacts, run
  solo) and (b) would yield an unwieldy ~50-step path; a normal topic (jlens, 14 artifacts) composes
  a genuinely good path in ~80s. Fix: a curation instruction in `build_designer_prompt` (select the
  most essential N artifacts per kind) and/or raise `_TIMEOUT_SECONDS` / bump `PATHS_DESIGNER_MODEL`
  for big topics. Surfaced by the pre-#12 live-Generate quality gate (2026-07-22).

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

---

## Open

_Backlog replenish 2026-07-19 (multi-lane `/brainstorm` + `bug-hunt` session; see
[`docs/bug-hunt/2026-07-19-post-m7.md`](docs/bug-hunt/2026-07-19-post-m7.md) and `docs/ideas/`).
Append-only. Bug stubs tagged **[P1]** are the five medium-severity findings Kyle flagged fix-first;
untagged bugs are the verified lows, in report rank order._

### Ideas (34 — one vision doc each)

#### 🎯 [Design approved 2026-07-21] Learning Paths — an AI study-designer over your library
- **Why:** Learning is a multi-format library with a quiz-only scorer — only a graded quiz feeds mastery/Plan/Progress, so the loop is cold (attempts=0). Learning Paths makes Claude a *learning designer* that composes an ordered, grounded path over a topic's real artifacts (arrange + labeled glue) scored on three axes (coverage · SR recall · self-rated confidence), rebuilding Plan (two lanes) and Progress (three trends) around it. See [`docs/ideas/learning-paths.md`](docs/ideas/learning-paths.md) for the full write-up.
- **Acceptance:** Ship the Jacobian Lens vertical slice end-to-end (on-demand path → outline+detail player → three axes → Continue/Review lanes), then judge path quality + the three-axis model before scaling to other topics.
- **Size:** L (new arc — proposed M8)
- **Added:** 2026-07-21
- **Status:** ✅ Vertical slice SHIPPED + CLOSED 2026-07-22 (#126–#136; live on the prod hub) — loader/stores #127 · Paths API #128 · frontend #129 · Designer #130 · Plan Continue lane #132 · Designer curation #134 · three-trend Progress #135 · frontend green gate #136. Path quality judged good 2026-07-22. Next M8 = scale the Designer beyond the bundled fixture to the rest of the library (future). Granular status in [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md).

#### ✅ [Exploration] Overnight Chief of Staff — the brief you approve, not read
- **Why:** A nightly agent runs after the 06:00 sweep, drafts the morning's real errands (stale follow-up emails, job-tracker reconciliation, a Louis med refill, the finance snapshot) as proposed actions, and the Today page opens as an after-action... See [`docs/ideas/overnight-chief-of-staff.md`](docs/ideas/overnight-chief-of-staff.md) for the full write-up.
- **Acceptance:** Prototype the credible first step (draft-only overnight pass -> overnight.jsonl -> Overnight strip) and judge whether the bet holds.
- **Size:** L (Moonshot)
- **Added:** 2026-07-19
- **Shipped:** v0 2026-07-20, PR #107 (tenth gate override, on the gate conversation's recorded scope: in-repo data only · draft-only with a later per-errand-type graded send gate · undo = discard + the reversibility rule). The credible first step exactly: nightly guarded pass → overnight.jsonl → live-only 🌙 approve/discard queue; approve = a real note via the existing notes path. The vault bridge and any real send/execute remain behind their own future gates.

#### [Exploration] The Mirror — the brief reads Kyle, not the world
- **Why:** A new top strip on Today that renders a candid, sourced read of Kyle himself each morning — 'You asked about agent evals 4 mornings running and wrote zero Celtics notes on the topic you've paused-then-unpaused three times; attention this... See [`docs/ideas/the-mirror.md`](docs/ideas/the-mirror.md) for the full write-up.
- **Acceptance:** Prototype the credible first step (deterministic 'You this week' strip on Today) and judge whether the bet holds.
- **Size:** L (Moonshot)
- **Added:** 2026-07-19
- _✅ v0 shipped 2026-07-20 (PR #104, RED→green — the Wave-4 moonshot pick, seventh deliberate gate override): `app/mirror.py` deterministically aggregates the last 7 LOCAL days of brief_visits + brief_notes + news_events + brief-chat.jsonl + roster pause flags into counts, a capped attention split, and one templated sentence → `BriefResponse.mirror` on the live view only (never ?date= archives) → the 🪞 "You this week" strip atop Today. MIN_SIGNAL=5 honest cold start; each source degrades independently; zero LLM, zero writes, render_brief.py untouched. v0 reports pause STATE, not churn (topics.json has no history). Kyle's pick same day: all four moonshots eventually, one at a time — the bet-judgment half of the acceptance rides the mornings before the ~08-03 check._

#### [Exploration] The Readiness Brief — tomorrow, not yesterday
- **Why:** A forward-tense section pinned above the brief that projects Kyle's next ~72 hours by colliding the swept world against his own calendar and job-search/life state, so its unit is a collision that rehearses him for what's coming, not a ca... See [`docs/ideas/readiness-brief.md`](docs/ideas/readiness-brief.md) for the full write-up.
- **Acceptance:** Prototype the credible first step (read-time 'Coming up' projection from developing-streak history) and judge whether the bet holds.
- **Size:** L (Moonshot)
- **Added:** 2026-07-19
- _✅ v0 shipped 2026-07-20 (PR #105, RED→green — Kyle's next-moonshot pick, eighth deliberate gate override): `build_readiness` in `app.sweeps` beside the M3 walkers projects which of the served morning's stories are still in motion — renderable prior mornings in the 7-day dedup window (`history_days`), badge-identical headline/source-URL identity keys so strip and badge can never disagree, mornings-seen → streak-density → slug/headline ranking, top-5 cap → `BriefResponse.readiness` on the live view only (never ?date= archives) → the 🔭 "Coming up" strip below the Mirror on Today. Honest below two archived mornings; zero LLM, zero writes, renderer untouched. Trajectories-only per Kyle's scope pick — the calendar/vault collision join stays the unscoped flagship; bet-judgment (felt readiness vs thin trending list, idea-doc open question 2) rides the mornings before the ~08-03 check._

#### [Exploration] Calibrated Doubt — the brief that bets, then grades itself
- **Why:** Every sweep item ships an optional falsifiable prediction plus a confidence number, and the next morning opens by scoring yesterday's calls against today's items and updating a running, public calibration ledger — a Brier score and a tra... See [`docs/ideas/calibrated-doubt.md`](docs/ideas/calibrated-doubt.md) for the full write-up.
- **Acceptance:** Prototype the credible first step (prediction+confidence fields surviving render, one scored morning) and judge whether the bet holds. Wildcard.
- **Size:** L (Moonshot)
- **Added:** 2026-07-19
- _✅ v0 shipped 2026-07-20 (PR #106, RED→green — Kyle's third-moonshot pick, ninth deliberate gate override, narrow render_brief.py unfreeze granted): optional wager pair (`prediction` + `confidence` 55–90, 0–2 per brief) in all 8 sweep prompts + the scout template → `normalize()`-only pass-through in the frozen renderer (validate()/gradeable .md/failure semantics byte-identical — a flubbed wager can never fail a sweep) → `build_calibration` in `app.sweeps` grades each wager against the topic's next READABLE sweep via the developing badge's own identity keys (reappeared = kept moving = hit; missing/garbled later file leaves the call open, never a false miss), appends once per (day, slug, headline) to `backend/data/calibration.jsonl`, recomputes the lifetime record (hits/Brier/days) each serve → `BriefResponse.calibration` live-only → 🎯 "Yesterday's calls" strip + open-wager chips on Today. Assumption-4 gate visible as the trial-week label until 7 distinct graded mornings; the ~08-19 monthly re-grade doubles as the vision doc's required M0-style graded week. Open questions deliberately deferred: LLM-judge resolution for arbitrary calls (v0 stays deterministic) and per-topic opt-in (v0's fresh-movement semantics resolve identically everywhere)._

#### [Improvement] Yesterday's brief, one tap back
- **Why:** An optional ?date= on GET /api/brief plus a /brief/:date route, so a note's date/headline snapshot on /notes links straight into that archived morning and prev/next arrows let Kyle walk the never-pruned sweep history. See [`docs/ideas/yesterdays-brief-one-tap-back.md`](docs/ideas/yesterdays-brief-one-tap-back.md) for the full write-up.
- **Acceptance:** GET /api/brief?date= + /brief/:date route + notes deep-link; confirm a /notes entry opens its archived morning with notes joined.
- **Size:** M (QuickWin)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #101, RED→green — Wave 3 item 7/7, WAVE 3 COMPLETE): `sweep_dates()` + `?date=` serves any renderable archived day (notes joined, honest 404s, no-param unchanged) with `prev_date`/`next_date` neighbors; sw.js stands aside for `?date=` (caching one would clobber the offline morning + evict its audio — pinned); new `/brief/:date` BriefArchive page outside the FR15 shell (notes live, Ask hidden — chat resolves the served day only, no stale nag, ← prev/next → Today nav); /notes date snapshots are now Links. Audio hidden on historical days by design. Phone check — a /notes tap opening its morning — rides Kyle's next browse._

#### [Improvement] Pick up the walk where it left off
- **Why:** A localStorage-backed resume on the audio brief: persist the <audio> element's currentTime keyed by brief date and restore it on load, so an interrupted ~5-min Kokoro cut doesn't snap back to 0:00. See [`docs/ideas/audio-resume.md`](docs/ideas/audio-resume.md) for the full write-up.
- **Acceptance:** Audio position persists per brief date in localStorage; confirm an interrupted playback resumes within ~2s of where it stopped.
- **Size:** S (QuickWin)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #95, RED→green — Wave 3 item 1): onTimeUpdate persists currentTime to localStorage keyed `audio-pos-<brief.date>`, onLoadedMetadata seeks back before first play (resume is exact to the last ~250ms tick — inside the ~2s bar), onEnded clears the key (idea-doc open question decided: a finished brief starts fresh). Handlers on the element itself so the FR15 hoist carries them; no backend/API change._

#### [Improvement] Jump straight to the topic you came for
- **Why:** A thin sticky row of topic-name chips atop the Today brief that scrollIntoView() to each TopicSection's anchor, so the fixed sweeps/topics.json order stops being the only way through the page. Converged in QuickWin + Friction lanes. See [`docs/ideas/jump-to-topic-chips.md`](docs/ideas/jump-to-topic-chips.md) for the full write-up.
- **Acceptance:** Sticky topic-chip row on Today anchors to each section; confirm a tap lands on the right topic on the phone.
- **Size:** S (QuickWin)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #96, RED→green — Wave 3 item 2): `id={topic.slug}` + `scroll-mt-24` on every TopicSection, sticky chip row under the app header scrollIntoView-smooths the tapped section. Every served topic gets a chip uniformly (no dimming/omission), row hidden for a single-topic brief, horizontal scroll over wrap. Phone tap-lands check rides Kyle's next morning read._

#### [Improvement] Notes reach the surface Kyle actually grazes
- **Why:** A 'Note' button on every News and For-You card that writes through the exact same POST /brief/notes path the Brief page uses, so a news item becomes a durable note interleaved into /notes alongside brief notes. Converged in QuickWin + Friction lanes. See [`docs/ideas/notes-on-news.md`](docs/ideas/notes-on-news.md) for the full write-up.
- **Acceptance:** Note button on News/For-You cards writes through POST /brief/notes; confirm the note appears interleaved on /notes.
- **Size:** M (QuickWin)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #84, RED→green — Wave 1): Note button + inline composer on every News/For-You card through the existing POST /brief/notes (origin category slug credited, mirroring signal(); local-today brief_date; "✓ Saved" ack; inline error keeps the composer). Zero backend changes; one backend test pins the non-roster-slug round-trip + humanized /notes title._

#### [Improvement] Say when a topic didn't run
- **Why:** A server-side diff of the active (non-paused) roster against the slugs that actually produced a file for the served date, surfaced as one Banner on Today so a silently-failed topic is visible instead of just absent. Complements bug #1 (adjacent, different fix). See [`docs/ideas/topic-didnt-run-banner.md`](docs/ideas/topic-didnt-run-banner.md) for the full write-up.
- **Acceptance:** BriefResponse gains a missing-topics field + one banner on Today; confirm a deliberately-failed topic shows as 'didn't run' instead of vanishing.
- **Size:** S (QuickWin)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #82, RED→green — Wave 1): `BriefResponse.missing_topics` (active roster minus renderable slugs; `.raw.txt`-only counts, paused excluded, empty when no served day) + a warning Banner on Today, suppressed offline, tolerant of pre-QU12 cached payloads._

#### [Exploration] The Silence Nobody Hears
- **Why:** The whole Mac-local stack (both LaunchAgents, Tailscale, Kokoro, launchd, the nvm/venv/Homebrew paths baked into the plists) can stop firing with zero notification, so the first signal of death is an empty morning brief — by which point ... See [`docs/ideas/heartbeat-outside-the-app.md`](docs/ideas/heartbeat-outside-the-app.md) for the full write-up.
- **Acceptance:** Antibody: independent heartbeat LaunchAgent alerting outside the app; confirm a killed sweep agent produces a phone-visible alert the same morning.
- **Size:** M (Premortem)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #85, RED→green — Wave 1 complete): `com.homebase.heartbeat` (09:00 + login) runs dependency-free `heartbeat.sh` — newest ledger ts (mtime fallback), >36h silent → Desktop flag file first, then notification; flag auto-clears on recovery; missing ledger alerts. install-schedule.sh manages both agents. Mac install + forced-stale live verify same session._

#### [Exploration] The Grading Week Was an Inspection, Not a Warranty
- **Why:** Sweep trustworthiness rests entirely on a single graded week (M0, which closes today 2026-07-19); nothing after it re-checks accuracy against sources on any cadence, so prompt rot, source-markup changes, or a model update degrade sourcin... See [`docs/ideas/sweep-trust-warranty.md`](docs/ideas/sweep-trust-warranty.md) for the full write-up.
- **Acceptance:** Antibody: last-graded date surfaced next to the habit strip + a re-grade cadence; confirm the gauge decays visibly after the grading week closes.
- **Size:** M (Premortem)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #83, RED→green — Wave 1): `last_graded` on `GET /brief/habit` from the newest dated heading in the new seeded `docs/sweep-trust-log.md` + a "Sweep trust:" line on the habit strip (amber "re-grade due" past 30 days; loud "no grade on record" state). Grading stays manual by design._

#### [Exploration] The Ritual Already Lives Elsewhere
- **Why:** Kyle's actual daily-check-in habit consolidates in the always-reachable Cowork/vault stack (morning-briefing, daily-plan, habit-check, evening-reflection — all reading Obsidian vault + Todoist + Calendar from any device, already schedule... See [`docs/ideas/feed-the-vault-ritual.md`](docs/ideas/feed-the-vault-ritual.md) for the full write-up.
- **Acceptance:** Antibody: best-effort post-sweep summary appended into the vault daily note; confirm one morning's threads appear in the note Kyle already reads.
- **Size:** M (Premortem)
- **Added:** 2026-07-19

#### [Improvement] The Note That Vanishes When You Distrust the Sweep
- **Why:** A manual same-day re-sweep (TOPIC=<slug> ./sweep.sh) rewrites headlines, which shifts every item's sha1(date|slug|headline) id, so notes Kyle already attached silently detach from the Today view with no error, no log line, nothing. See [`docs/ideas/resweep-note-detach-guard.md`](docs/ideas/resweep-note-detach-guard.md) for the full write-up.
- **Acceptance:** sweep.sh warns (and requires confirm) when a same-day re-sweep would overwrite a topic that has attached notes; regression test the id-detach path.
- **Size:** S (Harden)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #87, RED→green — W2 batch 1): guard in sweep.sh's per-topic loop — dependency-free stdlib-sqlite count of notes attached to (topic, today) before overwrite; warns naming the count, tty confirm [y/N], non-tty refuses without `SWEEP_FORCE=1` (both documented in the header). Scheduled lane unreachable by design (SWEEP_SKIP_DONE skips existing topics first)._

#### [Improvement] The Swept Item Is Not the Boss
- **Why:** build_prompt() splices a swept item's raw headline/digest/why_it_matters/sources directly beside Kyle's question with zero untrusted-data framing, so an injection payload that survives into a swept digest can steer the 'Ask about this' a... Pairs with bug #23. See [`docs/ideas/untrusted-item-framing.md`](docs/ideas/untrusted-item-framing.md) for the full write-up.
- **Acceptance:** build_prompt() wraps item text in untrusted-data framing/delimiters (chat + regen lanes); test that framing survives into the assembled prompt.
- **Size:** S (Harden)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #89, RED→green — W2 batch 2): `<untrusted-item>` (chat) / `<untrusted-current-material>` (regen) delimiters + a data-not-instructions framing sentence in both build_prompts; adversarial payload pinned inside the delimiters, Kyle's question left as the only directive. Pairs with #23's --tools/cwd containment, fixed same PR._

#### [Improvement] The Feed That Went Quiet Without Saying So
- **Why:** A Google-News RSS template change that drops every <item> through parse_rss's title/link filter while the XML still parses cleanly makes get_category_items overwrite a good cache with an empty result at stale=False, so a category (or a w... Pairs with bug #3. See [`docs/ideas/empty-feed-drift-guard.md`](docs/ideas/empty-feed-drift-guard.md) for the full write-up.
- **Acceptance:** get_category_items refuses to overwrite a non-empty cache with a parsed-empty result (serve stale instead); add the zero-items-drift regression test.
- **Size:** S (Harden)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #90, RED→green — W2 batch 3): zero-item parse + non-empty cache → serve last-good marked stale + one warning log; cache never clobbered (second request still serves the good items). No-cache empty parse stays an honest empty page (pinned)._

#### [Improvement] Copy the Bytes Before You Touch Them
- **Why:** init_db runs every forward migration unconditionally against the single learning-hub.sqlite file holding every note, SM-2 mastery record, custom topic, and reflection Kyle has ever saved, with no byte-level snapshot taken first -- so one... See [`docs/ideas/pre-migration-snapshot.md`](docs/ideas/pre-migration-snapshot.md) for the full write-up.
- **Acceptance:** init_db snapshots the sqlite file before running migrations (bounded retention); test that a failing migration leaves a restorable .bak.
- **Size:** S (Harden)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #92, RED→green — W2 batch 5): unconditional `shutil.copy2` to `{db}.bak-<utc-timestamp>` before the migration loop (never gated on the ledger, per the steelman); fresh/empty store skips; newest 5 kept; failing-migration test proves the .bak holds the pre-migration bytes. Restore stays manual (copy the .bak back)._

#### [Improvement] Today doesn't survive you leaving it
- **Why:** Every Today→News→Notes→Today hop tears the whole page down and rebuilds it from a blank slate: pulse-skeleton flash, refetch of identical brief data, scroll reset, and the audio brief silently snapping back to 0:00 mid-walk. See [`docs/ideas/today-survives-navigation.md`](docs/ideas/today-survives-navigation.md) for the full write-up.
- **Acceptance:** Brief payload + audio element lifted above Routes; confirm Today<->News<->back keeps scroll, data, and playing audio intact.
- **Size:** M (Friction)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #97, RED→green — Wave 3 item 3): new `components/BriefShell.tsx` above `<Routes>` owns the brief payload (stale-while-revalidate — returns render the held payload in the same commit, fresh sweeps still surface; a failed revalidate with data in hand stays silent) and the single `<audio>` element (stable-host portal — React never remounts it, Brief re-slots the live node per visit, playback continues detached on News/Notes). Same-node identity + instant-return pinned in App.test. Honest caveat: per-route scroll memory not included — the instant full-height render removes the skeleton-induced top-clamp, true restoration deferred._

#### [Improvement] Stuck on Stale, Phone in Hand
- **Why:** When the served brief is a day old, the only recovery the UI offers is a `make sweep` terminal command (Brief.tsx stale banner, lines 424-432) — unusable on the keyboard-less iPhone that M6 shipped Today to. See [`docs/ideas/sweep-from-the-phone.md`](docs/ideas/sweep-from-the-phone.md) for the full write-up.
- **Acceptance:** Lock-guarded POST triggers ./sweep.sh from the stale banner; confirm a phone tap refreshes the brief and a second tap mid-run is a no-op.
- **Size:** M (Friction)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #100, RED→green sandbox-only — Wave 3 item 6): `POST /api/brief/sweep` spawns the same repo-root ./sweep.sh detached behind an in-process lock (mid-run tap → honest `already_running`; missing runner → 503; taps logged to `phone-trigger.log`); child env scrubbed (bug #10 lane set — sweep.sh refuses a leaked key) + `SWEEP_SKIP_DONE=1`, never `SWEEP_FORCE` (HA2 keeps refusing the non-tty lane); stale banner gains Refresh now → Sweep-started copy + a 30s poll via the FR15 shell until the fresh date lands; `make sweep` path stays. Real-phone tap check rides Kyle's next stale morning._

#### [Improvement] Audio topic chapters
- **Why:** The ~5-min brief is one linear Kokoro MP3 built topic-by-topic in roster order behind a bare <audio controls> with zero seek metadata, so skipping an out-of-season or already-read topic on a walk means blind-scrubbing a featureless bar w... See [`docs/ideas/audio-topic-chapters.md`](docs/ideas/audio-topic-chapters.md) for the full write-up.
- **Acceptance:** audio_brief.py emits per-topic start offsets; chapter chips seek the player; confirm chips land within a few seconds of each topic lead-in.
- **Size:** M (Friction)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #98, RED→green — Wave 3 item 4): `build_script` returns chapters from its own settled word math (`WORDS_PER_MINUTE` estimate, display titles, trim-zeroed topics keep theirs); `brief.chapters.json` written atomically before the render (orphans stay invisible behind the API's mp3 gate); `BriefResponse.audio_chapters` degrades to [] on any file problem; chips seek to start−2s (clamped) so the spoken "Next up:" confirms the jump, then play. Ears-on lands-close check rides Kyle's next walk._

#### [Improvement] Developing since when? The badge that promises change and can't name it
- **Why:** The two affordances that most invite "so what actually changed?" — the prominent "developing · since Jul 14" badge and the adjacent "Ask about this" chat — both structurally cannot tell Kyle what moved, because neither compares the item ... See [`docs/ideas/developing-since-what-changed.md`](docs/ideas/developing-since-what-changed.md) for the full write-up.
- **Acceptance:** Ask-about-this receives the prior-day digest for developing items (and the badge can show it); confirm 'what changed?' answers cite the actual prior digest.
- **Size:** M (Friction)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-20 (PR #99, RED→green — Wave 3 item 5): both halves, fully deterministic — `_annotate_developing` attaches `prior_digest` (the first_seen day's digest, matched by the same identity keys that set the badge; empty/unreadable → no field, the label never overpromises); `build_prompt` threads it as a delimited `<untrusted-prior-item>` PRIOR VERSION block naming the day + a compare instruction (HA4 rule extended, injection pin included); the badge becomes a tap-toggle revealing "As written Jul 14: (verbatim)". Zero new generative surface. Live 'what changed?' answer check rides Kyle's next developing story._

#### [Improvement] One mis-tap, no take-backs: destructive taps need an undo beat
- **Why:** Three one-tap destructive actions on the phone surfaces commit instantly with no confirmation, no undo, and no trace beyond the thing vanishing: News "Not interested" (fires a -8 not_interested signal into For You AND hides the card), an... Converged in Friction + Harden lanes. See [`docs/ideas/destructive-tap-undo.md`](docs/ideas/destructive-tap-undo.md) for the full write-up.
- **Acceptance:** One undo-toast helper wraps not_interested + both note-delete paths; confirm undo within ~5s results in no API mutation.
- **Size:** S (Friction)
- **Added:** 2026-07-19
- _✅ shipped 2026-07-19 (PR #93, RED→green — W2 batch 6, closes the wave): `components/undo.tsx` (`useUndoable` + `UndoToast`, 5s) wraps all three taps — optimistic UI, deferred mutation, Undo = zero API calls (pinned per surface under fake timers), timeout/second-tap/unmount commits. No ranker/weight/layout change._

_Delight pass 2026-07-20 (`/brainstorm` Delight mode — the app's visual language & craft, News + Today as worked examples). Foundation-weighted: 3 systemic pieces (① ② ③) + 3 discrete delights (④ ⑤ ⑥); ⑥ is the deliberate wildcard. Append-only._

#### [Improvement] ① Lead story vs. the field — News gets a front page
- **Why:** Promote News `items[0]` to a real lead (bigger `text-lede` headline, `p-5`, meta on its own line) while the rest stay the compact field, so the eye lands on a front-page story instead of skating a `divide-y` wall of identical headlines — carried by two reusable type tokens. See [`docs/ideas/news-lead-hierarchy.md`](docs/ideas/news-lead-hierarchy.md) for the full write-up.
- **Acceptance:** `<LeadCard>` for index 0 + `text-lede`/`text-meta` tokens in `tailwind.config.js`; confirm on a real News load the top story reads as a lead and the eye lands there first, minor rows unchanged.
- **Size:** M (Delight) — foundation
- **Added:** 2026-07-20
- _✅ shipped 2026-07-21 (PR #117, RED→green): the visible #1 renders as its own lead card (new `text-lede` 1.25rem headline, `p-5`, meta on its own line) above the compact `divide-y` rest; `text-lede`/`text-meta` `fontSize` tokens added to `tailwind.config.js`; one shared `renderArticle` helper drives lead + rows (no duplicated `<article>`). Shipped adjacent to F2 (headline promotion) in one News pass. `News.test.tsx` +1 (lead `text-lede` vs compact); light-mode hierarchy screenshot-verified, dusk tokens carry dark._

#### [Improvement] ② A color system, not a color — semantic + source tint
- **Why:** Grow the single muted-teal into a small family — `success/info/warn/danger` semantic tints + a deterministic per-source tint — so every News source line signals provenance at a glance and the scattered `amber`/`red` one-offs collapse into one honest vocabulary, all inside the teal's calm envelope. See [`docs/ideas/semantic-source-color-system.md`](docs/ideas/semantic-source-color-system.md) for the full write-up.
- **Acceptance:** Semantic + `sourceTint` tokens added; News source line swapped to `sourceTint(item.source)`; confirm each source carries a stable, distinct, low-saturation tint and one warn/danger vocabulary replaces the `amber`/`red` one-offs — none out-shouting the teal.
- **Size:** M (Delight) — foundation
- **Added:** 2026-07-20
- _✅ shipped 2026-07-20 (PR #113, RED→green): palette → `:root` CSS vars (`rgb(var()/<alpha-value>)`, opacity modifiers verified intact via CSS build); semantic `success/info/warn/danger` + 6-hue `source` ramp; `sourceTint()` tints the News source line; note-error → `text-danger` as the proof slice (broader `amber`/`red` migration across Banner/Brief/etc. deferred, token vocab now exists). Lays the CSS-var substrate ③ needs. `sourceTint.test.ts` (4)._

#### [Improvement] ③ Dusk mode — a true low-light morning surface
- **Why:** Re-express the exact identity in low light via CSS variables + `prefers-color-scheme` (warm paper → warm near-black, cards → charcoal, teal legibility-tuned), so a morning app read in a dark pre-dawn room stops flashing a bright field — riding ②'s variable substrate. See [`docs/ideas/dusk-mode.md`](docs/ideas/dusk-mode.md) for the full write-up.
- **Acceptance:** Base tokens moved to CSS variables + a `prefers-color-scheme: dark` block + `color-scheme: light dark`; confirm the shared chrome (header, tab bar, body) and cards read calm and legible in dark with staleness/warning semantics intact.
- **Size:** M (Delight) — foundation
- **Added:** 2026-07-20
- _✅ shipped 2026-07-21 (PR #114, daily-loop v0, screenshot-signed-off): dark mode via CSS-var remap under `@media (prefers-color-scheme: dark)` + a `[data-theme]` override (auto + light/dark/system header toggle, FOUC-safe inline script, forced-light wins under a dark OS); new `card`/`line` surface tokens convert the chrome + Today/News/Notes surfaces (light values byte-identical). `theme.test.ts` (6). **Fast-follow ✅ shipped 2026-07-21 (PR #115):** the dusk token map (`bg-card`/`border-line*`/`bg-line*`, `text-stone`→`text-muted`) now covers the 16 deeper pages/components (Learning/Courses/CourseDetail/Progress/QuizPlayer/TopicDetail/Flashcards/StudyPlan/StudyGuide + Badge/CourseCard/MasteryBar/NotebookCard/CustomTopic*) — screenshot-verified charcoal cards on the near-black ground, no white gaps in dark; `text-stone-{400,500,600}`→`text-muted` the one non-byte-identical-in-light change (required for dark legibility). Mechanical rename, no class-asserting tests._

#### [Improvement] ④ Milestones the habit strip finally notices
- **Why:** Make the Today habit strip mark the real, earned milestones already sitting in its `weeks[]` history — a run of on-target weeks, a personal-best week, the target-hit `✓`, round mornings totals — each bound to a verified threshold so it never fires on a partial or stale number. See [`docs/ideas/habit-strip-milestones.md`](docs/ideas/habit-strip-milestones.md) for the full write-up.
- **Acceptance:** `consecutiveOnTarget`/`isBestWeek`/`totalMornings` derivations + conditional accent/`✓` spans in HabitStrip with once-only localStorage; confirm each marker fires only on a genuinely crossed threshold and the default line is unchanged when nothing is earned.
- **Size:** S (Delight)
- **Added:** 2026-07-20
- _✅ shipped 2026-07-20 (PR #111, RED→green): streak / personal-best / mornings-target-hit `✓` / lifetime-mornings (25/50/100/200/365, once-only per-device localStorage) markers derived client-side from `brief_habit`, each threshold-bound; ≤ `✓` + 1 accent suffix (precedence lifetime>streak>best), current-week line byte-identical when nothing earned. `HabitStrip.test.tsx` (8 tests)._

#### [Improvement] ⑤ The companion voice, not the system dialog
- **Why:** Give the calm `<Banner>` tones (`info`/`muted`, never `warning`) a thin `accent/40` left rule, so honesty-copy ("Still learning you", "Showing saved articles") reads as the app's own margin voice instead of stock alert chrome — one shared-component edit inherited everywhere. See [`docs/ideas/companion-voice-banners.md`](docs/ideas/companion-voice-banners.md) for the full write-up.
- **Acceptance:** `accent/40` left rule added to the Banner `info`/`muted` tones (warning untouched); confirm every calm honesty surface reads as the app's margin voice and a real `warning` still reads as an alarm.
- **Size:** S (Delight)
- **Added:** 2026-07-20
- _✅ shipped 2026-07-20 (PR #110, RED→green): `accent/40` left rule (`border-l-2 border-l-accent/40 pl-3`) on the calm `info`/`muted` Banner tones — left-longhand `border-l-accent/40` so the other three sides keep their tone color; `warning` untouched. Verified in built CSS + `Banner.test.tsx` (3 tests)._

#### [Improvement] ⑥ Content that arrives, not pops
- **Why:** Replace the brief's hard skeleton→content pop with a sub-250ms top-down section cascade (and a settle on the Ask answer), reduced-motion-guarded and hit-testable at frame 0, so the morning open feels like an arrival with zero added latency. The set's deliberate wildcard. See [`docs/ideas/content-arrives-not-pops.md`](docs/ideas/content-arrives-not-pops.md) for the full write-up.
- **Acceptance:** A `motion-safe` `.brief-cascade` (opacity + small `translateY`) on Today's section map + a settle on the Ask answer, gated to a genuine cold load; confirm total settle <~250ms, content readable at frame 0, and reduced-motion users get the instant paint.
- **Size:** S (Delight) — wildcard
- **Added:** 2026-07-20
- _✅ shipped 2026-07-21 (PR #119, Kyle greenlit "build it, subtle & guarded"): `.brief-cascade` (opacity 0→1 + 6px `translateY`, 160ms, staggered 0→90ms per section) on Today's section map + a keyed settle on the Ask answer; gated to a genuine cold load via a `coldLoad` ref (never replays on a warm `BriefShell` return). Animation defined only under `@media (prefers-reduced-motion: no-preference)` → instant paint for reduced-motion. Browser-verified `animationName=briefCascade`, 0.16s, last delay 0.09s → ~250ms settle, 7 sections. `Brief.test.tsx` +1. Honest: impl-before-test on this one; the felt smoothness rides Kyle's eyes-on next morning open._

_Friction pass 2026-07-20 (`/brainstorm` Friction mode — ease-of-use across the daily loop; News + the app shell/nav as the worked examples). 4 S–M friction removals (F1–F4) + 1 flagged interaction-model stretch (F5). C5 category-tab-target hygiene folds into F2's PR; the same-tab article-return idea (killed as a trap-for-a-trap) and a global search across brief+notes+news were considered and cut/deferred. Append-only._

#### [Improvement] F1 · News forgets where you were — News survives navigation
- **Why:** Today survives navigation (`BriefShell`) but News does not — every Today→News→Today hop remounts News and resets the tab, scroll, and dismissed cards, so Kyle pays a re-orient tax on the loop's most natural gesture. See [`docs/ideas/news-survives-navigation.md`](docs/ideas/news-survives-navigation.md) for the full write-up.
- **Acceptance:** News hoists its selected tab + scroll position (+ hidden/liked sets, reconciled against the fresh fetch) above the route mount, mirroring `BriefShell`; confirm a Today→News→Today hop lands back on the same tab and scroll position on the phone.
- **Size:** M (Friction) — first wedge S (sessionStorage-persist the selected tab)
- **Added:** 2026-07-20
- _✅ first wedge shipped 2026-07-21 (PR #118, RED→green): the selected tab is persisted to `sessionStorage` on click and used as the fallback when the URL has no `?cat=`, so a Today→News→Today hop lands back on the tab you left (explicit `?cat=` still wins; a fresh session with nothing saved → For You). `News.test.tsx` +2. **Full hoist shipped 2026-07-21 (PR #124):** new `NewsShell` (mirroring `BriefShell`) holds hidden/liked/noted + scroll above the routes, so a remount reconciles the id-keyed sets against the fresh feed instead of resetting. Scroll took two live-caught fixes (an unmount-time read clamps to 0 → passive scroll listener; the listener gated on "restored" so the return's Loading… collapse can't overwrite it). `News.test.tsx` survival test + live Today→News→Today (saved=800 → restored=800). **F1 complete.**_

#### [Improvement] F2 · The News card has no front door — headline as the primary tap
- **Why:** The headline is the primary action (opens the article) but is styled like body text, while three equal `text-xs` buttons compete for the eye, so on touch it's unclear what to tap or where the tap lands. See [`docs/ideas/news-card-primary-action.md`](docs/ideas/news-card-primary-action.md) for the full write-up.
- **Acceptance:** Headline restyled as the obvious primary tap (weight + trailing `↗` + full-height target) with the two feedback buttons visually subordinated **but not buried** (they stay one-tap so the ranker keeps its signal), and the category pills ≥44px; confirm on the phone the headline reads as the tap target. Folds in C5 (`min-h-[44px]` + `snap-x`).
- **Size:** M (Friction) — first wedge S (pure headline restyle)
- **Added:** 2026-07-20
- _✅ shipped 2026-07-21 (PR #117, RED→green): the headline is now the primary tap on every card (`font-semibold` + trailing `↗` + full-height `block py-0.5`); the two feedback signals subordinated (right-aligned, muted) but stay one-tap so the For You ranker keeps its signal (Kyle's call: quieter, not buried). C5 folded in — category pills `min-h-[44px]` + `snap-x snap-mandatory`. Shipped adjacent to ① (lead card) in one News pass. `News.test.tsx` +2 (headline primary tap, 44px pills)._

#### [Improvement] F3 · For You never says what to do first
- **Why:** The cold-start banner states the learning state but offers no next action, and after the threshold gives no sign it's personalized — so Kyle can't tell what to do first or whether his feedback ever mattered. See [`docs/ideas/foryou-cold-start-first-move.md`](docs/ideas/foryou-cold-start-first-move.md) for the full write-up.
- **Acceptance:** The `feed.learning` For You banner gains a "do this first" directional line (+ optionally a persistent personalization read-out); confirm the nudge shows below the 20-signal threshold and clears above it, adding no new control.
- **Size:** S (Friction)
- **Added:** 2026-07-20
- _✅ shipped 2026-07-21 (PR #116, RED→green): the `feed?.learning` "Still learning you" banner opens with a bolded "**Do this first:** open a story you want more of, or tap 'More like this'…" directive above the kept `N of 20 signals` status line — references the real gesture, adds no new control, gated on the same `feed.learning` flag so it clears the instant For You warms up. Optional persistent personalization read-out deferred. `News.test.tsx` +2 (nudge present below threshold, absent above)._

#### [Improvement] F4 · Stranded at the bottom of the feed — jump-to-top
- **Why:** After thumbing a long News feed one-handed there's no one-tap way back to the top — only a manual re-scroll or a state-wiping remount. See [`docs/ideas/news-jump-to-top.md`](docs/ideas/news-jump-to-top.md) for the full write-up.
- **Acceptance:** A thumb-zone back-to-top button appears after ~400px of News scroll and smooth-scrolls to the top; confirm one tap returns to the top on the phone and it stays hidden near the top.
- **Size:** S (Friction)
- **Added:** 2026-07-20
- _✅ shipped 2026-07-20 (PR #112, RED→green): floating `<BackToTop>` on News — fades in past ~400px window scroll, scrolls to top (smooth; instant under `prefers-reduced-motion`), 44px thumb target `bottom-20 right-4` above the tab bar; `aria-hidden` while hidden. `BackToTop.test.tsx` (4 tests)._

#### [Improvement] F5 · Seven tabs, no signal which one matters this morning — nav priority + freshness (STRETCH)
- **Why:** The nav is seven equal items with no priority or freshness signal, so every open is a "which tab?" micro-decision whose answer is almost always Today — Kyle's explicitly #1-named friction. The run's one flagged interaction-model reframe. See [`docs/ideas/nav-priority-freshness-signal.md`](docs/ideas/nav-priority-freshness-signal.md) for the full write-up.
- **Acceptance:** Nav gains a priority hierarchy (daily-loop cluster vs muted reference shelf) and/or a freshness dot from `brief.date` / item `published_at` vs a `localStorage` last-seen. First wedge = the Today freshness dot (no backend); prototype it and judge the feel before the IA cluster split (an identity shift — get Kyle's okay first).
- **Size:** L (Friction, stretch) — first wedge S–M
- **Added:** 2026-07-20
- _✅ freshness dot shipped 2026-07-21 (PR #120, RED→green): a small `aria-hidden` accent dot on the Today tab (desktop header + mobile bar) when the loaded `brief.date` is newer than a `localStorage` last-seen, cleared the moment Today is opened. `<BriefShell>` hoisted above the navs (new `<AppChrome>`) + fetch-on-mount (inFlight-deduped, so it never double-fetches with Brief's per-visit refresh) so the dot can surface from News/Notes; the dot is `aria-hidden` so the Today link's accessible name stays "Today"; audio portal + offline/`fromCache` + FR15 invariants unchanged; `App.test.tsx` +2 (159→161). **Cluster split shipped 2026-07-21 (PR #122)** — the flagged IA identity shift, approved: the seven flat desktop links become a daily-loop cluster (Today·News·Notes, full-weight `text-ink`) + a divider + a muted reference shelf (Learning·Plan·Courses·Progress, `text-muted`); active page still wins in either tier; desktop only (mobile bar untouched per idea doc); structural grouping test, suite 161→162. **F5 complete.**_

#### [Feature] Study Scheduler — opt-in Calendar time-blocks for a course or path — ✅ v0 SHIPPED (PR #137/#138) · ✅ v1 flexible prefs SHIPPED 2026-07-22
- _✅ **v1 flexible preferences** shipped 2026-07-22 (this PR): v0 ignored *which days* + *what time of day* (no day-of-week concept; evening-only window silently rewrote "before 2pm" → 6–7pm). v1 = a real **`days_of_week`** planner knob (Mon=0…Sun=6) · explicit panel controls (day chips · time range · session length · max blocks) driving the plan deterministically · the `claude -p` lane taught the knob + "before 2pm"/"weekdays" examples, now driving the controls via an `applied` echo the UI snaps to (note-turns accumulate through the persisted base) · per-key hand-vs-LLM precedence · **schema v12** persists the prefs per-track (stick across visits/devices). Backend 709→723, frontend 180→185, ruff/tsc/build green; v12 migration heals a pre-v12 store. **Future:** recurring · completion-reclaim · Courses parity._
- _✅ v0 shipped 2026-07-22 (PR #137), anchored on the M8 **Jacobian path** (Kyle's call), full v0 in one PR: schema-v11 opt-in + removable block ledger · per-kind duration model · a deterministic CT/DST session planner (packs whole steps, never splits, skips busy, one/day) · a `CalendarPort` seam (Fake in tests, a real Google adapter behind lazy imports) · a grounded `claude -p` negotiation lane (sets planner knobs only, never invents times) · a Study-time panel on PathPlayer. New package `app.studycal` (distinct from the SM-2 `app.study`/`store.scheduler`). Backend +39 tests, frontend +5 (→180), ruff/typecheck/build green. A **live** write needs Kyle's one-time OAuth; degrades honestly to a "connect your calendar" state until then. Architecture + runbook: [`docs/STUDY_SCHEDULER.md`](docs/STUDY_SCHEDULER.md). **Future:** recurring · completion-reclaim · Courses parity._
- **Why:** On a specific course (or M8 Learning Path — same ordered-step engine), an opt-in assistant reads Google Calendar free/busy, works out session length with Kyle, and proposes time-blocks for the next steps (study guide · audio overview · quiz · several at once) — Kyle reviews and confirms the proposed set in one pass, then the whole batch is written to Calendar. Per-track opt-in (~1–2 tracks live at once), not global. Home Base's second acting surface after Overnight and its first Google-service write, but kept honest by a *light* batch-confirm — a self-only, non-communicating, trivially-reversible calendar block deliberately doesn't get Overnight's email-send bar (Kyle's call, 2026-07-22). See [`docs/ideas/study-scheduler.md`](docs/ideas/study-scheduler.md) for the full write-up.
- **Acceptance:** Prototype the credible first step (per-course opt-in flag + deterministic session planner + read-only free/busy pull → review-and-confirm view that writes the whole proposed batch on one confirm) end-to-end on one course; judge whether defended calendar time actually improves study adherence. Route via `/explore-plan` (new Google OAuth + external-write surface).
- **Size:** L
- **Added:** 2026-07-22 (direct capture — not a `/brainstorm` idea)

### Bugs (23 verified — full detail in the [report](docs/bug-hunt/2026-07-19-post-m7.md))

#### [Bug] [P1] #1: Empty or all-failed newest sweep dir blanks the entire brief while yesterday's complete brief sits one fold...
- **Where:** `backend/app/sweeps.py:62-67` · severity medium · confidence high
- **Why:** sweep.sh mkdir-p's the day folder minutes before the first topic lands, and latest_sweep_date has no content check, so every morning there is a window — exactly when the on-wake catch-up fires and Kyle opens his phone — where GET /api/brief says has_data=fa...
- **Acceptance:** Make latest_sweep_date (or a wrapper shared by brief/audio/chat) skip date dirs containing no *.json/*.md, returning the newest day with renderable content; optionally expose the newer folder's in-progress/failed stat... Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #73, RED→green): `latest_sweep_date` skips date dirs with no renderable `*.json`/`*.md` — brief, audio, and chat all serve the newest day that can actually render._

#### [Bug] [P1] #2: Scout one-click add creates a roster topic with no sweep prompt
- **Where:** `backend/app/news.py:83-107` · severity medium · confidence high
- **Why:** append_roster_topic writes only the topics.json entry; sweep.sh requires prompts/<slug>.md per topic and counts its absence as a failure, so the run ends rc=1 forever after. The shipped, advertised M7 feature ('tomorrow's 06:00 sweep picks it up') silently ...
- **Acceptance:** Have append_roster_topic also write sweeps/prompts/<slug>.md from a generic template parameterized by the term (matching the M0-tuned sourcing bar), or make sweep.sh fall back to a generic prompt instead of a permanen... QuickWin + Friction lanes converged on this same guard (fold their variants in). Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #74, RED→green): the add stamps `prompts/<slug>.md` from the new checked-in `sweeps/prompts/_template.md` (M0-tuned hard rules verbatim) before the roster append; hand-tuned prompts never overwritten; missing template fails the add closed._

#### [Bug] [P1] #3: One dead feed in a multi-feed category discards all successfully fetched feeds and freezes the category on ...
- **Where:** `backend/app/news.py:183-191` · severity medium · confidence high
- **Why:** The try wraps the whole feed loop, so one flaky host (Uplifting has 4 independent small WordPress sites; Local has 2) throws away the feeds that succeeded and serves the expired cache as stale — and the category can never refresh while that single feed stay...
- **Acceptance:** Catch NewsFeedError per feed and continue; serve/cache the merged result as fresh when at least one feed succeeded; only fall back to stale cache / 502 when every feed failed. Add a partial-failure test. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #75, RED→green): per-feed NewsFeedError catch in `get_category_items`; healthy feeds serve + cache fresh (category unfreezes); stale/502 honesty now scoped to every-feed-failed._

#### [Bug] [P1] #4: Learning-activity days are bucketed on the UTC calendar day
- **Where:** `backend/app/store/db.py:80 (also :108, :356, :443, :510, :645, :756, :978, :1054; reader api/progress.py:64)` · severity medium · confidence high
- **Why:** Any activity after ~7 PM CT lands on tomorrow's UTC day, so consecutive local-day practice reads as a broken streak and an evening dashboard check can show current_streak=0 while it's still 'today' locally. The repo already diagnosed and fixed this exact bu...
- **Acceptance:** Write activity.day as the local day mirroring record_brief_visit: date('now','localtime') in the six raw-SQL writers, local-day derivation in record_attempt/record_flashcard_review, and datetime.now().astimezone().dat... Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #76, RED→green): all six raw-SQL writers on `date('now','localtime')`, `_local_day()` derivation in the injected-now writers, local `today` in `/api/progress`; SM-2/attempt timestamps stay UTC (boundary pinned by a far-TZ test fixture). Bug #13 (foryou gate) stays its own stub._

#### [Bug] [P1] #5: make dev silently runs against the KeepAlive prod server
- **Where:** `dev.sh:64` · severity medium · confidence medium
- **Why:** With com.homebase.server installed, the dev uvicorn dies at bind in a backgrounded subshell, Vite comes up anyway and transparently proxies /api to the prod agent: backend edits never take effect (no --reload process) and dev-frontend writes land in the pro...
- **Acceptance:** Before launching uvicorn, detect the taken port (lsof -ti tcp:8000 or a health-check curl) and fail loudly naming com.homebase.server; or move dev backend + Vite proxy to a distinct port (8001) so dev and the agent ne... Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #77, RED→green): port guard at the top of dev.sh (`lsof -ti`) refuses loudly naming com.homebase.server + the bootout/reinstall commands; `BACKEND_PORT` drives guard + uvicorn so they can't drift. **Closes the P1 set (PRs #73–#77).**_

#### [Bug] #6: Read-time dedup URL identity strips the whole query string
- **Where:** `backend/app/sweeps.py:152-158` · severity low · confidence high
- **Why:** youtube.com/watch?v=AAA and ?v=ZZZ collide to 'youtube.com/watch' (reproduced by execution), violating the docstring's 'conservative … never mislabeled' invariant. Sports-topic sweeps plausibly cite query-keyed URLs across a week, and a false 'developing · ...
- **Acceptance:** Keep the query string in the normalized identity (strip only fragment/trailing slash, or only known tracking params like utm_*/fbclid); add a regression test with two watch?v= URLs. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #87, RED→green — W2 batch 1): `_norm_url` keeps the query string; only fragment, trailing slash, and tracking params (utm_*, fbclid) are noise. watch?v=AAA vs ?v=ZZZ pinned; the shared-URL test fixture moved off the bare `utm=` param the fix un-strips._

#### [Bug] #7: GET /api/brief can 500 on an unreadable sweep file
- **Where:** `backend/app/sweeps.py:253-262 (and _fallback_topic line 127)` · severity low · confidence high
- **Why:** One bad permission or a mid-swap replacement takes down the whole Today page instead of degrading a single topic. Every other read in the module deliberately catches OSError; the two brief-serving reads — including the designated fallback path — are the exc...
- **Acceptance:** Add OSError to the except tuple at line 257 and wrap _fallback_topic's md read in try/except OSError falling through to the 'no readable brief' dict. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #87, RED→green — W2 batch 1): OSError joins the json fallback tuple and `_fallback_topic`'s md read degrades to the honest 'no readable brief' card — both read sites pinned by permission-denied tests; one bad file degrades one topic, never Today._

#### [Bug] #8: Frontend mount decided once at startup, but installer/README promise 'make build' needs no restart
- **Where:** `backend/app/main.py:74-76` · severity low · confidence high
- **Why:** install-server.sh explicitly tolerates a missing dist and tells you to 'run make build', but the KeepAlive process registered no SPA catch-all at startup and never restarts — the phone 404s on / until a launchctl kickstart nobody mentions. Two shipped artif...
- **Acceptance:** Register the catch-all unconditionally and check frontend_dist per request (serve index.html when present, 404 when not), making the README claim true; or amend the installer hint/README to include the kickstart command. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #91, RED→green — W2 batch 4): catch-all registers unconditionally, index.html checked per request (404 until the build lands); hashed assets served by the catch-all's file branch until the /assets mount exists at next start; no-dist behavior byte-identical to before._

#### [Bug] #9: One malformed activity.day row permanently 500s GET /api/progress via compute_streaks
- **Where:** `backend/app/store/progress.py:32` · severity low · confidence high
- **Why:** date.fromisoformat runs unguarded over every distinct activity.day, so a single bad row (reachable via the vendored learning-hub-db MCP write_query — the same outside-the-app surface behind the documented 2026-07-16 incident) takes down the whole progress d...
- **Acceptance:** Parse defensively like brief_habit_weeks: wrap date.fromisoformat per row in try/except (TypeError, ValueError) and skip bad rows. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #92, RED→green — W2 batch 5): exactly the acceptance — per-row try/except in `compute_streaks`, bad rows skipped; pure-function + end-to-end poisoned-row tests (raw insert via the store, `GET /api/progress` 200)._

#### [Bug] #10: Subscription-lane env scrub drops only ANTHROPIC_API_KEY
- **Where:** `backend/app/chat.py:51-55 (also regen.py:86-90, sweeps/schedule/run-scheduled.sh:20)` · severity low · confidence high
- **Why:** The documented guarantee ('a stray exported key can never silently flip a question onto metered API billing') is enforced for one variable out of the set the claude CLI actually reads. An exported ANTHROPIC_AUTH_TOKEN or CLAUDE_CODE_USE_BEDROCK/VERTEX from ...
- **Acceptance:** Extend all three scrub sites to also drop ANTHROPIC_AUTH_TOKEN, CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX (and ANTHROPIC_BASE_URL), and pin the full set in the scrub tests. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #89, RED→green — W2 batch 2): `_LANE_ENV_VARS` (the five-var set incl. ANTHROPIC_BASE_URL) scrubbed in chat.py + regen.py; run-scheduled.sh unsets the same five; full set pinned at all three sites._

#### [Bug] #11: _strip_fence corrupts a regenerated lesson/exercise that legitimately starts and ends with distinct code bl...
- **Where:** `backend/app/courses/regen.py:204-210` · severity low · confidence high
- **Why:** A correct unwrapped answer opening with starter code and closing with a solution block gets its outer fences stripped, leaving unbalanced markdown that passes validate_dir's non-empty-only check and is written with no rollback — a garbled lesson from a norm...
- **Acceptance:** Only strip when the fence is plausibly a wrapper (e.g. interior fence markers remain balanced after stripping); on ambiguity pass the text through unchanged. Add the false-positive test. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-20 (PR #103, RED→green — W4 courses batch): `_strip_fence` unwraps only when the interior's own fences stay balanced without the outer pair (CommonMark-ish walk — openers may carry a tag, closers must be bare, a tagged fence inside an open block is content); distinct leading/trailing blocks pass through unchanged, ambiguity passes through. e2e + unit pins, true-wrapper case pinned against overcorrection._

#### [Bug] #12: append_roster_topic read-modify-write race can silently lose a concurrent write to sweeps/topics.json
- **Where:** `backend/app/news.py:95-106` · severity low · confidence high
- **Why:** Two Add taps (FastAPI runs these sync handlers on a threadpool, and the UI shows up to 3 Add cards) or a hand-edit saved mid-flight gets clobbered while both writers see 200 ok — silent data loss on a file the brief explicitly names as dual-writer. The shar...
- **Acceptance:** Module-level threading.Lock around read→dupe-check→write→replace (sufficient single-process); use a unique tempfile for staging; optionally mtime-check before replace to narrow the hand-edit window. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #90, RED→green — W2 batch 3): `_roster_write_lock` serializes the whole section (prompt stamp included) + mkstemp unique tempfile with unlink-on-failure; deterministic two-racer barrier test pins the lost-update path. Optional mtime-check skipped — the lock covers the in-app writers, the deployed shape._

#### [Bug] #13: Topic scout's '>=3 distinct days' persistence gate buckets by UTC day, not local day
- **Where:** `backend/app/foryou.py:270-274` · severity low · confidence high
- **Why:** Same root cause as the streak bug: naive-UTC created_at truncated to a date with no conversion, so two sittings can satisfy a gate whose stated intent is 'a persistent interest, not one morning's rabbit hole', and the days_seen evidence on the suggestion ca...
- **Acceptance:** Parse created_at, attach UTC when naive, convert to America/Chicago, then take .date() as the bucket — mirroring _decay's normalization. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #90, RED→green — W2 batch 3): `_local_day()` (attach UTC when naive → America/Chicago → .date(), unreadable rows bucket to "") feeds the gate and the days_seen evidence; the regression fixture scores 11.25 across 3 UTC dates but only 2 Chicago days and is refused._

#### [Bug] #14: Deleting the last note of the filtered topic strands the filter and shows a false 'No notes yet' empty stat...
- **Where:** `frontend/src/pages/Notes.tsx:34-84` · severity low · confidence high
- **Why:** The stale topic filter hides all remaining notes behind a factually wrong 'No notes yet — add one from the Today brief' banner, and if only one topic remains the select unmounts so only a full reload recovers. Ordinary path for a notes page; data is intact,...
- **Acceptance:** Derive an effective filter: const effectiveTopic = topics.some(t => t.slug === topic) ? topic : 'all', used for both visible and the select value (or reset topic in remove() when deleting the filtered topic's last note). Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #93, RED→green — W2 batch 6): exactly the acceptance's first form — `effectiveTopic` drives both visibility and the select value, so the filter falls back to All the moment its topic vanishes (and snaps back if an FR10 undo restores it)._

#### [Bug] #15: Offline audio can be a different day's narration (or a broken player) presented as the cached brief's audio
- **Where:** `frontend/public/sw.js:76-86` · severity low · confidence high
- **Why:** Brief JSON and audio age independently in BRIEF_CACHE with no date pairing — offline Saturday can play Tuesday's narration under Friday's brief, and on the iPhone (Range probes → 206 → never cached) the player renders then errors, defeating the 'no player, ...
- **Acceptance:** When fromCache, hide or honestly label the player; better, store the brief date alongside the cached audio and have the SW delete the audio entry when it caches a brief with a different date. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #91, RED→green — W2 batch 4): both halves — sw.js date-pairs the cached audio (synthetic marker entry; different-dated brief evicts it) and Brief.tsx hides the player on a media error (covers the iOS never-cached 206 case). sw.js itself now under test via a ?raw harness._

#### [Bug] #16: Per-note delete button stays enabled in offline (fromCache) mode, contradicting the offline banner
- **Where:** `frontend/src/pages/Brief.tsx:143-149` · severity low · confidence high
- **Why:** The banner promises 'Notes and Ask are disabled until you're back online' and readOnly disables the two composers, but the ✕ delete escaped both the implementation and the dedicated offline test — tapping it fails with a generic 'Failed to fetch' that looks...
- **Acceptance:** disabled={readOnly} on the delete button with the same title treatment as the composers ('Offline — deletes need the hub'). Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #91, RED→green — W2 batch 4): exactly the acceptance — disabled={readOnly} + 'Offline — deletes need the hub' title + disabled:opacity-50, pinned beside the existing composer-disabling offline test._

#### [Bug] #17: Failed note delete renders under the 'Couldn't load notes' banner title
- **Where:** `frontend/src/pages/Notes.tsx:72-78` · severity low · confidence high
- **Why:** Shared error state means a failed DELETE displays 'Failed to delete the note' under a hard-coded load-failure heading while the fully loaded list renders below — the heading misstates what failed and implies missing data.
- **Acceptance:** Neutral banner title ('Something went wrong') or a separate delete-error state with an accurate title. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #93, RED→green — W2 batch 6): separate delete-error state with the accurate "Couldn't delete the note" title (the second acceptance form); with FR10 the failed commit also restores the row, so the list below the banner stays truthful. **Closes W2 batch 6 — the wave's last stub.**_

#### [Bug] #18: Course write paths are not exception/crash-safe: an OSError mid-write skips rollback and can destroy course...
- **Where:** `backend/app/courses/writer.py:52-63, 102-119` · severity low · confidence high
- **Why:** The 'rolls back byte-identical' contract holds only when validate_dir returns ok:false normally; any raised exception (ENOSPC truncation, EACCES, validate_dir's own uncaught read_text, the second write in write_material) aborts before restore, and non-atomi...
- **Acceptance:** try/except around the write→validate sequence that restores snapshots before re-raising; write each file via tmp + os.replace; in write_material restore the material file if the manifest write raises. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-20 (PR #103, RED→green — W4 courses batch): both write paths wrap write→validate in try/except restoring the byte-identical snapshots before re-raising (write_material restores material AND manifest whichever step raised), and every file lands via same-dir mkstemp + os.replace (the news.py roster idiom) so a mid-write crash can't truncate in place. Three raise-path restores pinned; in-process crash atomicity itself rides on os.replace, not a unit test._

#### [Bug] #19: On-wake catch-up does not cover a powered-off/rebooted Mac
- **Where:** `sweeps/schedule/com.homebase.sweep.plist.template:24-34` · severity low · confidence medium
- **Why:** launchd coalesces StartCalendarInterval fires missed during sleep only; with RunAtLoad=false, an overnight auto-update reboot or shutdown means no sweep all day, yesterday's brief served as latest, and nothing signals staleness — it looks like a quiet news ...
- **Acceptance:** Set RunAtLoad=true — already safe because SWEEP_SKIP_DONE makes an on-load fire a no-op on swept days — and fix the comment; optionally have GET /api/brief flag when the served date is older than today. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #87, RED→green — W2 batch 1): template `RunAtLoad=true` + honest comment; safety pinned by a test on run-scheduled.sh's `SWEEP_SKIP_DONE=1`. The optional stale-flag half deliberately skipped — the stale banner already exists. Live-verified same session: install-schedule.sh re-run from the main checkout; the on-load fire skipped 8/8 swept topics (SWEEP_SKIP_DONE) and exited rc=0 — reboot coverage proven, no re-sweep._

#### [Bug] #20: FlashcardReview load() has no cancellation
- **Where:** `frontend/src/pages/FlashcardReview.tsx:37-65` · severity low · confidence medium
- **Why:** The deck lives in a search param so React Router re-runs the effect without remounting; two racing loads let the last-resolved win regardless of currency, and grade() then POSTs the stale deck's index against the current path — server-side data corruption, ...
- **Acceptance:** Apply the house cancellation pattern: per-invocation token/alive flag, skip all setStates when a newer load has started. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-20 (PR #103, RED→green — W4 courses batch): exactly the acceptance — load() takes a per-invocation ref token, then/catch bail when a newer load has started, and the effect cleanup retires in-flight loads on param change/unmount; the race pin switches decks mid-flight and resolves the stale load last._

#### [Bug] #21: Reorder failure revert restores a whole-course snapshot, clobbering concurrent lesson-completion toggles
- **Where:** `frontend/src/pages/CourseDetail.tsx:147-168` · severity low · confidence medium
- **Why:** onToggle deliberately uses functional updates to compose concurrent toggles (per its own comment), but applyOrder's non-functional setCourse(prev) on the designed ok:false failure path rewinds a toggle whose POST already succeeded — UI and server disagree u...
- **Acceptance:** Revert only what the reorder changed via a functional update that restores module order while preserving each lesson's current completed flag. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-20 (PR #103, RED→green — W4 courses batch, closes the batch): exactly the acceptance — applyOrder's catch becomes a functional update restoring prev's module/lesson order while carrying each lesson's current object, so a mid-flight completion whose POST landed survives the revert; progress counters stay current (an order revert changes no counts)._

#### [Bug] #22: render_brief.py writes the live-served <topic>.json non-atomically
- **Where:** `sweeps/render_brief.py:174-177` · severity low · confidence medium
- **Why:** write_text truncates then writes at the exact path the always-on server reads per request, so a reader in the window sees an 'unreadable <topic>.json' error card on the morning brief — transient but trust-damaging, and the .md fallback is written after the ...
- **Acceptance:** Write both artifacts to .tmp and os.replace into place, .md first then .json, mirroring audio_brief.py's render(). Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #87, RED→green — W2 batch 1): implemented as a wrap — render_brief.py is frozen (trust-critical), so sweep.sh renders into a mktemp stage dir inside `$OUT_DIR` and mv-renames into place, .md first then .json (same-fs atomic rename; the server ignores subdirs; failures still land .raw.txt). Stage-dir probe + failure-path + real-renderer end-to-end tests._

#### [Bug] #23: Regen/chat lanes spawn claude -p with no tool restriction and inherited repo cwd
- **Where:** `backend/app/chat.py:108-129 (also regen.py:109-130)` · severity low · confidence low
- **Why:** Nothing passed to the subprocess enforces the documented no-tools guarantee for permissionless read tools, and running from the repo root means the child loads this repo's CLAUDE.md/.claude settings into every chat/regen context. Code facts confirmed; concr...
- **Acceptance:** Run the child with cwd set to an empty scratch dir (confines default reads, stops CLAUDE.md/settings pickup) and pass explicit tool denial (--disallowedTools or setting-sources isolation) in both chat.py and regen.py. Regression test first.
- **Size:** S
- **Added:** 2026-07-19
- _✅ fixed 2026-07-19 (PR #89, RED→green — W2 batch 2): both lanes pass `--tools ""` (the CLI's documented disable-all — stronger than a deny-list) and run inside an empty TemporaryDirectory cwd; scratch-cwd emptiness recorded at call time in the tests._
