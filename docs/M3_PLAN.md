# M3 Plan — Hands-off (scheduled sweeps · dedup · cost guardrails)

_Status: ✅ shipped 2026-07-15 (PR #43) · schedule installed at 06:00 CT · first unattended
fire verified clean 2026-07-16 (8/8 topics, rc=0, fresh briefs + ledger rows). Kickoff M3 spec: "Scheduled sweeps (launchd on-wake catch-up), dedup
vs history, cost guardrails, curation polish." Kyle green-lit M3 on 2026-07-15 — a **third**
deliberate override of the "wait for the M0 verdict" gate (after M1 on Day 0 and M2 on Day 1),
noted in writing; the M0 grading week + go/no-go verdict continue in parallel and are **not**
being declared done. Approach **A** ("Hands-off MVP") was chosen from the `/explore-plan` fork
on 2026-07-15._

## The gating unknown, settled first (the spike)

M3's core bet — kickoff riskiest-assumption #2: _"laptop-only means sweeps must run on
wake/login without thinking about it."_ Before building anything, a throwaway GUI-session
LaunchAgent ran one non-interactive `claude -p … --output-format json`:

- **Subscription auth holds under launchd** — `is_error:false`, `result:"OK"`, `claude_exit=0`,
  no Keychain prompt or hang. (The token is not a `~/.claude/credentials.json` file; it's
  reached via the login Keychain, and a **GUI / Aqua-session** LaunchAgent gets it as the same
  user.)
- **`claude` lives under nvm** (`/Users/kyledisch/.nvm/versions/node/<v>/bin`), so the wrapper
  **must** export an absolute PATH — launchd's default PATH finds neither `claude` nor `node`.
- **The `--output-format json` envelope** carries `result` (the model's brief JSON, unwrapped
  before the existing `extract_json`), plus `total_cost_usd`, `usage` (input/output/cache
  tokens + `server_tool_use.web_search_requests`), `duration_ms`, and a per-model `modelUsage`
  breakdown — everything the cost ledger needs.

## The three forks, decided

### 1. Scheduler — launchd LaunchAgent + idempotent wrapper (not cron, not a cloud agent)
`StartCalendarInterval` at a morning time; launchd runs a **missed** job once on wake — the
"on-wake catch-up," free from launchd with no polling daemon. A wrapper makes re-runs safe: it
sets `SWEEP_SKIP_DONE=1` so `sweep.sh` **skips topics already written today**, so launchd's
on-wake re-fire of a completed morning is a no-op and a half-finished morning finishes the rest.
This resolves the kickoff open question _"local launchd vs cloud agents committing to the repo"_
→ **local launchd** (laptop-only; no repo-committing bot; briefs stay regenerable + gitignored).

### 2. Cost guardrails — reframed as **lane + rate + observability**, not dollars
On the `claude -p` subscription lane there is **no per-run dollar meter** (the kickoff's
"cents–$2/day" assumed API billing). The real exposures, and the guards for each:
- **Never silently bill the API** — the wrapper hard-`unset ANTHROPIC_API_KEY`, and `sweep.sh`
  refuses to run if it's set unless `SWEEP_ALLOW_API=1`.
- **Don't run away** — idempotent skip-if-already-swept + a soft `SWEEP_MAX_TOPICS` ceiling.
- **Make usage observable** — capture `total_cost_usd` / tokens / `web_search_requests` /
  duration per topic from the JSON envelope into `data/sweeps/.runs.jsonl` (gitignored,
  regenerable). This answers the kickoff's open "monthly comfort number" with real data instead
  of a guess.

### 3. Dedup vs history — read-time **soft label**, not drop, not prompt-side
The item id is **date-scoped by design** (`sha1(date|slug|headline)[:12]`), so cross-day
identity matches on **normalized headline + primary source host/path**, not the id (M2_PLAN
left this door open). `app/sweeps.py` builds a small recent-history index over the last K
day-dirs and flags a recurring item `developing: true` + `first_seen: <date>` — **nothing is
dropped**. Rationale: for a morning brief a repeated story is usually a real *update*; silently
deleting it would hide news. Files stay frozen + regenerable (the read-only-backend invariant
holds); no persistent in-file ids are needed. The subtle "developing · since &lt;date&gt;" chip on
Today is the kickoff's "curation polish."

## The slice

```
sweeps/schedule/                      NEW — the automation
  com.homebase.sweep.plist.template     launchd agent (StartCalendarInterval + on-wake catch-up)
  install-schedule.sh                   idempotent bootstrap/enable + uninstall; fills the template
  run-scheduled.sh                      wrapper: absolute nvm PATH · hard unset ANTHROPIC_API_KEY ·
                                        SWEEP_SKIP_DONE=1 · network preflight (≤90s, honest
                                        abort) · log → data/sweeps/logs/<date>.log
  README.md                             install/uninstall + how on-wake catch-up works

sweep.sh                              per-topic `claude -p --output-format json`; unwrap the
                                      envelope's .result → hand the brief JSON to the renderer;
                                      refuse-on-API-key guard (SWEEP_ALLOW_API=1) · soft
                                      SWEEP_MAX_TOPICS ceiling · SWEEP_SKIP_DONE idempotent re-runs ·
                                      append per-topic usage/cost/duration → .runs.jsonl
sweeps/render_brief.py                UNCHANGED — the trust-critical validate + render write path
                                      stays frozen; sweep.sh hands it the same brief JSON as before

backend/app/sweeps.py                 recent-history index (normalized headline + source host/path
                                      over last K days) → per-item developing/first_seen at read time
backend/app/models.py                 BriefItem += developing: bool = False · first_seen: Optional[str]
frontend/src/api/types.ts             hand-sync the two optional fields (client.ts unchanged)
frontend Today item                   subtle "developing · since <date>" chip

data/sweeps/{logs/,.runs.jsonl}       already gitignored via `/data/sweeps/` — no .gitignore change
```

## Deliberately NOT in M3
- **No sqlite run-ledger / cost dashboard / status API** — the JSONL is enough for a single-user
  laptop; the `sweep_runs` table + `GET /api/sweeps/health` + a Today health strip is the
  Approach-B upgrade, deferred until the JSONL proves insufficient.
- **No prompt-side dedup** — kept out of the trust-critical prompt path (still being validated by
  the grading week) and off the token bill; read-time labeling is deterministic + reversible.
- **No hard removal of repeated items** — dedup labels, never deletes (updates matter).
- **No persistent in-file item ids** — read-time identity suffices; revisit only if a real need appears.
- **No parallel/concurrent topic sweeps** — sequential ~30 min is fine unattended; parallelism is a
  later optimization.
- **No curation UI** — the config file remains the interface (kickoff stance).

## Verification
- **Spike (done):** launchd GUI-agent `claude -p` → authenticated, exit 0, envelope confirmed.
- Backend pytest (test-writer house style): dedup labeling (a recurring headline across two
  synthetic day-dirs → `developing`/`first_seen`; the date-scoped-id edge; source-URL
  normalization), `.runs.jsonl` append shape, and the wrapper's skip-if-complete decision;
  degrade-safe when history is empty. Suite stays green.
- `bash -n` on the three scripts + a real dry-run of `run-scheduled.sh` (skip path + a single
  `TOPIC=` run) that writes a brief and a `.runs.jsonl` row.
- `make typecheck` + `make lint`; contract-reviewer pass on the two new TS fields.
- End-to-end: `install-schedule.sh`, then `launchctl kickstart` the real agent once and confirm a
  full brief + log + ledger rows land — before trusting the morning schedule.
- **Verified in production (2026-07-16):** first real unattended fire — log wake 06:00:04,
  `sweep finished (rc=0)` 06:25:39, 8/8 topics in `data/sweeps/2026-07-16/`, 8 clean rows in
  `.runs.jsonl` (~$10.06 equiv total, avg ~$1.26/topic), spot-checked brief carried
  same-morning news. Observability note: `web_search_requests`/`web_fetch_requests` were 0
  across all topics while content was demonstrably fresh — the envelope's `server_tool_use`
  counters don't see the CLI's client-side WebSearch/WebFetch, so don't read them as a
  freshness signal; the M0 grades remain the real quality check.
