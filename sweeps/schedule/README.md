# Scheduled sweeps (M3) + the heartbeat (PR12)

Runs the morning sweep automatically via a macOS **LaunchAgent**, so the brief is ready
without running `make sweep` by hand — the kickoff's _"sweeps must run on wake/login without
thinking about it."_ A second, independent agent — the **heartbeat dead-man's switch** —
watches that the first one is still alive.

## Install

```bash
sweeps/schedule/install-schedule.sh          # sweep daily at 06:00 local + heartbeat at 09:00
sweeps/schedule/install-schedule.sh 07:15    # sweep at a custom time (heartbeat stays 09:00)
```

It fills [`com.homebase.sweep.plist.template`](com.homebase.sweep.plist.template) with your
repo path + the nvm `bin` that holds `claude`, writes
`~/Library/LaunchAgents/com.homebase.sweep.plist`, and loads it into your GUI login session —
and does the same for [`com.homebase.heartbeat.plist.template`](com.homebase.heartbeat.plist.template).
Re-run it anytime to change the time or after moving the repo (it's idempotent).

## The heartbeat (dead-man's switch)

The cost ledger records every successful sweep; nothing ever read it for **absence** — so the
whole stack could die silently and the first signal would be an empty morning brief.
[`heartbeat.sh`](heartbeat.sh) runs at 09:00 (+ at login, closing its own post-reboot blind
spot) and checks the newest `ts` in `data/sweeps/.runs.jsonl` (file-mtime fallback for a
mangled row). Past **36h** of silence it alerts *outside the app*:

- plants `~/Desktop/HOMEBASE-STACK-SILENT.txt` with what to check and how to kick the sweep
  (auto-removed on the first healthy check after recovery), and
- fires a macOS notification (best-effort, after the flag is written).

It is deliberately dependency-free — plain bash + system tools, no venv/node/claude — so it
cannot die the same way the pipeline does. Logs to `data/sweeps/logs/heartbeat.log`; tests in
`backend/tests/test_heartbeat.py` run the real script with every path/threshold overridden.

## How "on-wake catch-up" works

`StartCalendarInterval` fires at the set time. If the Mac was **asleep or off** then, launchd
runs the missed job **once on wake** — so an overnight-closed laptop still sweeps when you open
it. The wrapper exports `SWEEP_SKIP_DONE=1`, so a re-fire after a completed morning is a no-op,
and a half-finished morning just finishes the remaining topics.

## Cost / lane

The wrapper hard-`unset ANTHROPIC_API_KEY` → always your Claude **subscription**, never metered
API billing. Every run appends per-topic cost/usage to `data/sweeps/.runs.jsonl` (see
[`../README.md`](../README.md)).

## Where it logs

- `data/sweeps/logs/<date>.log` — one file per day, the wrapper's full output.
- `data/sweeps/logs/launchd.log` — launchd's own stdout/stderr (catches start-up failures).

Both live under `data/sweeps/`, so they're gitignored with the briefs.

## Manage

```bash
sweeps/schedule/install-schedule.sh status                   # loaded? next run?
launchctl kickstart -k gui/$(id -u)/com.homebase.sweep       # run it right now
sweeps/schedule/install-schedule.sh uninstall                # remove it
```
