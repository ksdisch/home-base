# Sweep Pipeline

## Purpose
How the morning brief gets from nothing to `GET /api/brief` — the complete end-to-end
chain: prompt files → `sweep.sh` → `render_brief.py` → `data/sweeps/<date>/` → `app/sweeps.py`
→ the API. This page synthesizes the runner, the renderer, the scheduling automation, and the
honesty rules that no single doc covers in full.

## Key understanding

### Components and their roles

| Component | File | Role |
|---|---|---|
| Topic roster | `sweeps/topics.json` | Ordered `[{slug, title, paused}]`; read fresh per request (no restart needed for edits). Missing/invalid → empty roster, never a crash. |
| Prompts | `sweeps/prompts/<slug>.md` | One file per topic; instructs `claude -p` how to research and structure its output. Tuned by M0. |
| Runner | `sweep.sh` | Reads the roster, shells `claude -p` per topic, captures the `--output-format json` envelope, pipes the result to `render_brief.py`. |
| Envelope | `sweeps/envelope.py` | Parses the `claude -p` JSON envelope (`result`, `total_cost_usd`, `usage`, `duration_ms`) and appends one row to `data/sweeps/.runs.jsonl` per topic. |
| Renderer / trust gate | `sweeps/render_brief.py` | Validates the model's JSON and writes BOTH output artifacts. On failure: writes `<topic>.raw.txt` and exits 1 (loud per-topic failure — bad output never silently reaches the page). |
| Sweep output dir | `data/sweeps/<YYYY-MM-DD>/` | One dated folder per run. Gitignored; regenerable. |
| Ingest | `backend/app/sweeps.py` | Reads the folder at request time; shapes it for `GET /api/brief`. Never writes to the folder. |
| Scheduler | `sweeps/schedule/com.homebase.sweep.plist.template` | launchd `StartCalendarInterval` at 06:00 CT + `on-wake catch-up`; runs a missed job once on first wake. |
| Wrapper | `sweeps/schedule/run-scheduled.sh` | Sets the absolute nvm PATH, hard-unsets `ANTHROPIC_API_KEY`, sets `SWEEP_SKIP_DONE=1`, redirects logs to `data/sweeps/logs/<date>.log`. |

### What render_brief.py validates (the trust gate)
**Fact** (`sweeps/render_brief.py`): On valid JSON, it writes:
- `<topic>.json` — the machine-readable brief the hub ingests.
- `<topic>.md` — the human-gradeable Markdown view (the M0 grading loop format).

Validation rules enforced at write time (a failed item never reaches the hub silently):
- `top_line` must be a non-empty string.
- `items` must be a list.
- Each item must have `headline`, `attribution`, `digest`, `why_it_matters` (all non-empty strings).
- **Each item must carry ≥1 real-looking source URL** — this is the M0 sourcing rule: a model that
  omits sources fails validation. **Fact** (`render_brief.py` `validate()`): the rule is enforced at
  write time, not at read time.

The renderer tolerates two common LLM output flubs: a ```` ``` ````-fenced JSON block, and a stray
leading/trailing wrapper (it finds the first `{` to the last `}`).

### Authentication and API key containment
**Fact** (`sweep.sh`, `docs/M3_PLAN.md`): The sweep runner refuses to start if `ANTHROPIC_API_KEY`
is set, unless `SWEEP_ALLOW_API=1` is passed explicitly. Rationale: plain `claude -p` uses the
logged-in Claude subscription (not metered API billing); a set key might silently route to the
API lane. The scheduled wrapper hard-`unset`s the key before calling `sweep.sh`.

**Fact** (Wave 2 batch 2, PR #89): the `claude -p` brief-chat lane (`app/chat.py`) also scrubs the
full env set, runs with `--tools ""` and a scratch cwd, and frames content with untrusted-data
markers.

### Idempotency: `SWEEP_SKIP_DONE`
**Fact** (`docs/M3_PLAN.md`, `sweep.sh`): `SWEEP_SKIP_DONE=1` makes the runner skip any topic whose
`<topic>.json` already exists for today. The launchd `on-wake catch-up` always runs the wrapper with
this flag, so a re-fire after a completed morning is a no-op and a half-finished morning completes
the remaining topics. **Inference**: this is also why FR2 (phone-triggered sweep via `POST
/brief/sweep`) is safe — it re-uses `SKIP_DONE` so it can't double-write a topic.

### How `app/sweeps.py` reads the output
**Fact** (`backend/app/sweeps.py`, `docs/M2_PLAN.md`):
- `latest_sweep_date(sweeps_dir)` finds the newest YYYY-MM-DD folder with at least one `.json` or
  `.md` file (skips empty/fully-failed dirs that contain only `.raw.txt`).
- `load_brief(sweeps_dir, date, roster)` builds the `BriefResponse`: for each active roster topic,
  tries to load `<topic>.json`; falls back to `<topic>.md` as `raw_markdown` with an error note;
  missing → a `BriefMissingTopic` entry (QU12 didn't-run banner). A topic is **never silently dropped**.
- Item ids are derived at read time: `sha1(date|slug|headline)[:12]`. **Decision** (PR #39): ids stay
  read-time, not write-time, so the trust-critical write path (render_brief.py) stays frozen during
  the M0 grading week.

### The `developing` label (cross-day dedup)
**Fact** (`docs/M3_PLAN.md`, `backend/app/sweeps.py`): `_annotate_developing()` builds a recent-history
index over the last K day-dirs (normalized headline + primary source host/path). A repeated story is
flagged `developing: True` + `first_seen: <date>` — it is **never dropped**. Rationale: a recurring
story on a morning brief is usually a real update, not a duplicate error.

**Fact** (FR13, Wave 3, PR #99): `prior_digest` captures the digest as it read on `first_seen` day,
so the "what changed" badge shows the verbatim prior version. Determined from disk at read time —
zero new LLM surface.

### Scheduler mechanics
**Fact** (`docs/M3_PLAN.md`, `sweeps/schedule/`):
- launchd `StartCalendarInterval` fires at 06:00 CT. A launchd GUI/Aqua-session LaunchAgent
  reaches the login Keychain where `claude`'s subscription token lives — **this was proven by a
  throwaway spike before any automation was built**.
- `StartCalendarInterval` semantics: launchd fires a missed job **once** on the next wake, so a
  laptop that wakes up at 09:00 gets one catch-up run, not nine.
- `com.homebase.server` KeepAlive LaunchAgent keeps FastAPI up. Its PATH was corrected in PR #139
  to include `~/.local/bin` so `nlm` and the `claude` fallback are reachable from the always-on server.

### The cost/usage ledger
**Fact** (`docs/M3_PLAN.md`, `sweeps/envelope.py`): Every topic run appends one JSON row to
`data/sweeps/.runs.jsonl` (gitignored). Fields: `date`, `topic`, `total_cost_usd`, `duration_ms`,
token counts (`input`, `output`, `cache`), `web_search_requests`. On the subscription lane `total_cost_usd`
is an estimate only (not billed). **Inference**: this is how the "monthly comfort number" open
question from the kickoff is answered with real data.

### Audio brief production
**Fact** (`docs/M4_PLAN.md`, `sweeps/audio_brief.py`): After every sweep, `sweeps/audio_brief.py`
renders a ~650-word ear script from the day's JSON files and feeds it to local Kokoro TTS (via
`com.voicemode.kokoro`), producing `data/sweeps/<date>/brief.mp3`. This is best-effort — an audio
failure never fails the sweep. The `GET /api/brief/audio` endpoint streams the MP3; `audio_available`
in the `BriefResponse` reflects whether the file exists for the served day.

### Reliability rules (not breakable without understanding them)
**Fact** (multiple Wave 2 items):
- **Atomic render staging** (PR #87, #22): the renderer never writes a partial file — output is staged
  to a temp path and renamed atomically.
- **`render_brief.py` is frozen** (PR #89 comment, Wave 2 batch 2): the trust-critical write path must
  not be changed without understanding that it is the M0 sourcing-bar enforcement point.
- **Re-sweep note guard** (PR #87, HA2): if a note is attached to a brief item, re-sweeping that topic
  without `SWEEP_FORCE=1` warns and (in non-tty mode) refuses, so a note is never silently orphaned.
- **Parsed-empty cache guard** (PR #90, HA8): an RSS fetch that returns an empty list does not clobber
  the last good cache; it serves stale. (News mode, but same principle as the brief side.)

## Sources
- [`sweep.sh`](../sweep.sh) — the authoritative runner; inline comments are the operational spec
- [`sweeps/render_brief.py`](../sweeps/render_brief.py) — the trust gate; `validate()` encodes the M0 rules
- [`backend/app/sweeps.py`](../backend/app/sweeps.py) — the read layer that shapes output for the API
- [`docs/M3_PLAN.md`](../docs/M3_PLAN.md) — the hands-off automation design (all three forks decided here)
- [`docs/M0-sweep-grades.md`](../docs/M0-sweep-grades.md) — the grading week evidence + the AI prompt tune
- [`docs/MASTER_PLAN.md`](../docs/MASTER_PLAN.md) — Wave 2 batch PRs where reliability rules were encoded

## Uncertainties & contradictions
- **Unresolved**: the `claude -p` PATH fix for the always-on server (PR #139, `~/.local/bin`) must be
  re-pointed after a Node/nvm upgrade. There is no automated check for this.
- **Unresolved**: sweep accuracy long-term is the project's stated riskiest assumption. A ~08-19 re-grade
  is scheduled (`docs/sweep-trust-log.md`).
- **Unresolved**: `render_brief.py` is described as "frozen" (trust-critical write path) but this is
  convention, not enforced by a code lock. A future contributor could change it without realizing its role.

## Related pages
- [Architecture](Architecture.md) — where the pipeline fits in the larger system
- [Data-Model](Data-Model.md) — the `brief_notes` and `brief_visits` tables the brief feed writes into

## Relevance to current work
Any feature that touches sweep output or adds a new brief surface must respect:
1. `render_brief.py` is the trust gate — validation changes need deliberate review.
2. The `SWEEP_SKIP_DONE` idempotency contract — a new runner path must honor it.
3. Item ids are date-scoped read-time hashes — never assume cross-day stability.
4. Audio and chat surfaces degrade gracefully; a sweep failure must not cascade.

_Last reviewed: 2026-07-26_
