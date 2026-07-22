# Study Scheduler — opt-in Google Calendar study blocks for a learning path

> **Status:** v0 built + fully tested (PR #137/#138); **v1 flexible-preferences rework** shipped
> 2026-07-22 (schema **v12**). Anchored on the M8 **Jacobian Learning Path** fixture. The
> deterministic core + the real Google adapter both ship; a **live** calendar write needs Kyle's
> one-time OAuth provisioning (below) — until then the app degrades honestly to a "Connect your
> Google Calendar" state. Idea + settled decisions: [`ideas/study-scheduler.md`](ideas/study-scheduler.md).

## v1 — flexible preferences (Kyle, 2026-07-22)

v0 ignored the two things a learner asks for most: **which days** and **what time of day**. There was
no day-of-week concept anywhere, and the evening-only window meant a "before 2pm" preference got
silently repaired back into a 6–7pm slot. v1 fixes both and makes the panel a real back-and-forth:

- **Explicit controls are the source of truth:** day-of-week chips (Mon→Sun = Python `weekday()`
  0→6), a time-of-day range (`day_start_hour`/`day_end_hour`), session length, and max blocks. The
  planner honors them directly — no LLM required for the common case.
- **Day-of-week knob:** `PlanConfig.days_of_week` (a `frozenset[int]`, `None` = every day); the
  planner skips disallowed weekdays. "weekdays / weekends / Tue-Thu" are now honorable.
- **Free-text still works, and it *refines the controls*:** every propose sends the current controls;
  a non-empty note refines them server-side. A **local deterministic parser** (`app.studycal.parse`,
  no LLM) handles the common patterns — days (weekday/weekend/specific/"not Mondays"), time-of-day
  ("before 2pm", "no earlier than 2pm", "2–5pm", "mornings"), session length ("sixty-minute", "1
  hour"), max blocks ("at most 3 blocks") — instantly and always, even when the CLI is unreachable.
  Only a phrasing the parser doesn't recognize falls back to the `claude -p` lane; if neither can read
  it, the plan is left **unchanged** and an honest message is shown (never the old silent no-op that
  displayed the untouched default as if it were the answer). The response echoes an `applied` plan and
  the controls **snap to it**; note-turns accumulate through the persisted base ("weekdays before 2pm"
  → "not Mondays").
- **Refine precedence:** the note wins for the keys it names; the controls hold for the rest.
- **Flag conflicts + double-book (Kyle, 2026-07-22).** When the requested window is booked and steps
  go unscheduled, the proposal **flags the conflicting events by name** (`conflicts`, via a titled
  `port.busy_events` over the primary calendar's `events.list` — the freebusy API has no titles) and
  offers `can_double_book`. "Book over it anyway" re-proposes with `allow_double_book=true`, which
  places into the window ignoring free/busy (`plan_sessions(ignore_busy=True)`); each block that lands
  on an existing event carries an `overlaps` list so the UI badges *"⚠ double-books X"*. For the
  common case where a shared calendar has events you can study through (Kyle's girlfriend adds items
  for awareness). Placement still respects busy by default; double-book is an explicit per-proposal
  opt-in. `busy_events` is best-effort — an adapter hiccup degrades to no titles, never a failed
  propose (freebusy still drives placement).
- **claude fallback needs the CLI on the server's PATH.** The always-on `com.homebase.server` runs
  with a minimal launchd PATH; `claude` installs under nvm (a version-pinned dir not on it), so the
  fallback lane logged `"claude CLI not found"` and silently degraded. Fix: symlink it into
  `~/.local/bin` (already on the server PATH via the #139 fix) — `ln -sf "$(which claude)"
  ~/.local/bin/claude`. Re-point after a Node/nvm upgrade. The parser covers the common cases with no
  CLI dependency, so this only affects unusual phrasings.
- **Persistence (schema v12):** the control set is saved per-track on the `study_opt_in` row
  (`day_start_hour`/`day_end_hour`/`days_of_week` CSV/`max_blocks`), so "weekdays before 2pm" sticks
  across visits and devices. `propose` persists the effective config (calendar untouched — still
  read-only against Google); `GET /schedule` returns the prefs to hydrate the panel.

On a learning path, Kyle opts in to a scheduling assistant that reads his Google Calendar free/busy,
works out how long study sessions should be, proposes concrete time-blocks for the path's next
incomplete steps, and — once he reviews and confirms the set in **one pass** — writes the whole
batch to a dedicated "Study" calendar so the plan has real, cleanly-removable time defended on it.
It's Home Base's **second** step from *reporting* into *acting on an external account* (after
Overnight) and the first that writes to a Google service — kept honest by a light plan-level
confirm plus the fact that a study block is self-only, non-communicating, and trivially reversible.

## Decisions (Kyle, 2026-07-22)

- **Build shape:** full v0 in one PR — the deterministic core **and** the real Google adapter.
- **Opt-in per track**, on the **Jacobian Learning Path** first (the shared ordered-step engine lets
  Courses opt in later with no schema change — `track_kind = 'path'` today).
- **Calendar write = approve-the-plan-once → batch-write** to a **dedicated "Study" calendar** (safer
  than the primary; easy to mute/hide/bulk-clear). Every block records its Google `event_id` so it is
  **cleanly removable** — the one hard rule.
- **Durations:** per-kind defaults, folding micro-glue. Audio uses its real `estimated_minutes`;
  quiz/flashcards/read/bridge get sensible per-kind minutes; intro/reflect/recap fold into an
  adjacent block rather than claiming their own slot.
- **One-off** blocks in v0 (recurring is a later flip-on), **deterministic** slot-finding **plus** a
  grounded `claude -p` **negotiation lane** — a free-text preference ("mornings only", "≤3 blocks")
  is turned into planner *knobs* only; the model never emits a time, so all placement stays
  deterministic and grounded (the M0 no-fabrication bar).

## Architecture

A distinct package `app.studycal` (**not** `app.study` — that's the unrelated SM-2 interleaving
*review* planner — and **not** `app.store.scheduler`, the SM-2 spaced-repetition scheduler):

| Piece | File | Notes |
|---|---|---|
| Opt-in flag + removable block ledger + **persisted window prefs** | `app/store/study_blocks.py` (+ schema v11: `study_opt_in`, `study_blocks`; **v12** adds the pref columns + `set_study_prefs`) | Same content-on-disk / progress-in-SQLite split as `path_step_progress`. |
| Duration model | `app/studycal/duration.py` | Pure per-kind minutes + `is_foldable`. |
| Deterministic session planner | `app/studycal/planner.py` | Pure: packs whole steps into session-length blocks (never split), places them in the earliest free slot in a daily study window, skipping busy, never the past, one block/day, **only on allowed `days_of_week`**. `America/Chicago` (DST-correct RFC3339). |
| Calendar seam | `app/studycal/port.py` | `CalendarPort` protocol (+ **`busy_events`** for titled conflicts) + in-memory `FakeCalendarPort` (tests/dry-run). |
| Real adapter | `app/studycal/google.py` | Google Calendar API behind the port; **lazy** imports so the app + tests run without the libs. `free_busy` (freebusy, placement) + **`busy_events`** (events.list, titles for flagging — skips all-day/declined/free). `python -m app.studycal.google login` for the one-time consent. |
| Preference parser | `app/studycal/parse.py` | **Local deterministic** free-text → knob-overrides (days · time window · session length · max blocks), refining the current controls. No LLM/clock/network — the note box's primary engine. |
| Negotiation lane (fallback) | `app/studycal/negotiate.py` | free-text → clamped planner knobs (incl. **`days_of_week`**, with worked "before 2pm"/"weekdays" examples) + a one-line message via the M5 `claude -p` lane. Only invoked when the parser returns nothing. |
| API router | `app/api/study.py` | `GET /schedule` · `POST /schedule/{opt-in,propose,confirm,remove}` under `/api/paths/{id}`. `propose` builds config from controls → merges the LLM lane by per-key precedence → persists the effective prefs → echoes `applied`. |
| UI | `frontend/src/pages/PathPlayer.tsx` (`StudySchedule`) | **Controls (day chips · time range · session length · max blocks) + a conversation thread**, hydrated from persisted prefs; propose → review (droppable) → one confirm → written blocks + remove. Controls snap to `applied` after each propose. Honest "connect" state. |

**Honest degrade:** every calendar op goes through the injected `CalendarPort`. When Google isn't
wired (no token/libs), `is_connected()` returns `False`, propose returns `connected:false` with no
blocks, and confirm/remove 409 — never a 500.

## One-time OAuth setup (Kyle — required for a live write)

The repo has no Google integration otherwise; this is the one part only you can provision.

1. **Install the libs** in the backend venv: `pip install -r backend/requirements.txt` (adds
   `google-api-python-client`, `google-auth-oauthlib`, `google-auth`).
2. **Create an OAuth client** in [Google Cloud Console](https://console.cloud.google.com/): a
   project → enable the **Google Calendar API** → *Credentials* → *Create credentials* → *OAuth
   client ID* → application type **Desktop app**. Download the client-secret JSON.
3. **Drop the secret** at `backend/data/google-oauth-client.json` (backend `data/` is gitignored).
4. **Consent once:** from `backend/`, run
   `PYTHONPATH=. .venv/bin/python -m app.studycal.google login` — it opens a browser, you approve the
   Calendar scope, and it writes `backend/data/google-token.json` (refreshed silently thereafter).
5. Reload the hub. The Study-time panel on a path now shows the propose/confirm controls, and the
   first confirm creates the "Study (Home Base)" calendar automatically.

Scope: `https://www.googleapis.com/auth/calendar`. Tokens/secrets live under `backend/data/` (never a
sidecar — the `guard-sidecars` invariant), never committed.

## Tests

Backend (all against `FakeCalendarPort` + a fake `claude` runner — real Google never touched):
`test_study_store.py` (opt-in + removable ledger + **prefs roundtrip / enabled-preserving**),
`test_study_duration.py`, `test_studycal_planner.py` (packing/no-split/glue-fold/busy-skip/one-per-day/
DST/past-guard/max-blocks + **days-of-week skip / specific-days / morning window / ignore-busy
double-book**), `test_studycal_port.py` (+ **titled `busy_events`**),
`test_studycal_negotiate.py` (+ **`days_of_week` parse/clamp + prompt examples**),
**`test_studycal_parse.py`** (the local parser — Kyle's exact sentence · days/exclusions · time
windows · ranges · named windows · session length · max blocks · unrecognized→`{}`),
`test_study_api.py` (opt-in roundtrip · read-only propose · confirm→ledger · remove · honest
not-connected degrade · **explicit controls honored · prefs persist · note refines controls ·
exclusion refines current days · parseable note skips claude · unparseable note→claude+logs ·
unreadable note is honest, not a silent no-op · `applied` echo · **booked-window flags conflicts +
offers double-book · double-book places over busy + labels overlaps**). Frontend: `PathPlayer.test.tsx` —
Study-Scheduler surface tests (connect · propose→confirm · drop · toggle · remove) **plus the v1
controls (render · hydrate from prefs · deterministic knobs · `applied` reflected · note refines +
shows the reply)**. v1 migration verified to heal a pre-v12 store.

## Not in v0 (future)

Recurring/unattended maintenance · completion-reclaim (block ↔ actual step completion) · Courses
parity (the engine is shared — a `track_kind='course'` away) · scheduling against the Study
calendar's own events in free/busy (v0 reads `primary` only) · scaling past the bundled fixture.
