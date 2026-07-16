# Scheduled sweeps (M3)

Runs the morning sweep automatically via a macOS **LaunchAgent**, so the brief is ready
without running `make sweep` by hand — the kickoff's _"sweeps must run on wake/login without
thinking about it."_

## Install

```bash
sweeps/schedule/install-schedule.sh          # daily at 06:00 local
sweeps/schedule/install-schedule.sh 07:15    # a custom time
```

It fills [`com.homebase.sweep.plist.template`](com.homebase.sweep.plist.template) with your
repo path + the nvm `bin` that holds `claude`, writes
`~/Library/LaunchAgents/com.homebase.sweep.plist`, and loads it into your GUI login session.
Re-run it anytime to change the time or after moving the repo (it's idempotent).

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
