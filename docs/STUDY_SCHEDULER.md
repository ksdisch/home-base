# Study Scheduler (v0) — opt-in Google Calendar study blocks for a learning path

> **Status:** v0 built + fully tested (PR #PENDING), anchored on the M8 **Jacobian Learning Path**
> fixture. The deterministic core + the real Google adapter both ship; a **live** calendar write
> needs Kyle's one-time OAuth provisioning (below) — until then the app degrades honestly to a
> "Connect your Google Calendar" state. Idea + settled decisions: [`ideas/study-scheduler.md`](ideas/study-scheduler.md).

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
| Opt-in flag + removable block ledger | `app/store/study_blocks.py` (+ schema v11: `study_opt_in`, `study_blocks`) | Same content-on-disk / progress-in-SQLite split as `path_step_progress`. |
| Duration model | `app/studycal/duration.py` | Pure per-kind minutes + `is_foldable`. |
| Deterministic session planner | `app/studycal/planner.py` | Pure: packs whole steps into session-length blocks (never split), places them in the earliest free slot in a daily study window, skipping busy, never the past, one block/day. `America/Chicago` (DST-correct RFC3339). |
| Calendar seam | `app/studycal/port.py` | `CalendarPort` protocol + in-memory `FakeCalendarPort` (tests/dry-run). |
| Real adapter | `app/studycal/google.py` | Google Calendar API behind the port; **lazy** imports so the app + tests run without the libs. `python -m app.studycal.google login` for the one-time consent. |
| Negotiation lane | `app/studycal/negotiate.py` | free-text → clamped planner knobs + a one-line message via the M5 `claude -p` lane. |
| API router | `app/api/study.py` | `GET /schedule` · `POST /schedule/{opt-in,propose,confirm,remove}` under `/api/paths/{id}`. |
| UI | `frontend/src/pages/PathPlayer.tsx` (`StudySchedule`) | Toggle → propose → review (droppable) → one confirm → written blocks + remove. Mirrors the Overnight strip's tap/error posture; honest "connect" state. |

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
`test_study_store.py` (opt-in + removable ledger), `test_study_duration.py`, `test_studycal_planner.py`
(packing/no-split/glue-fold/busy-skip/one-per-day/DST/past-guard/max-blocks), `test_studycal_port.py`,
`test_studycal_negotiate.py`, `test_study_api.py` (opt-in roundtrip · read-only propose · confirm→ledger
· remove · honest not-connected degrade · negotiation logging). Frontend: `PathPlayer.test.tsx` gains 5
Study-Scheduler tests (connect state · propose→confirm · drop · toggle · remove).

## Not in v0 (future)

Recurring/unattended maintenance · completion-reclaim (block ↔ actual step completion) · Courses
parity (the engine is shared — a `track_kind='course'` away) · scheduling against the Study
calendar's own events in free/busy (v0 reads `primary` only) · scaling past the bundled fixture.
