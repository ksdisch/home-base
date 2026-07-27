# Network preflight on the 06:00 sweep: don't fire into a dead Wi-Fi and call it done

**Status:** Idea — not committed. Added by `/replenish` (Harden lane) on 2026-07-26.

_sweeps/schedule/run-scheduled.sh does a claude-on-PATH check then goes straight to ./sweep.sh — no network preflight. When the pmset wake lands at 06:00, launchd runs the sweep in the seconds before Wi-Fi re-associates; every topic's fetch/claude call fails, and because the scheduled fire technically HAPPENED, launchd's missed-time on-wake re-fire never triggers. The brief stays empty until Kyle manually re-sweeps — on the exact sleep-wake mornings the unattended pipeline exists for. Guard: a preflight loop at the top of the wrapper — up to ~90s of `curl -sm 3 https://news.google.com/ >/dev/null` retries at 5s intervals, logging each wait tick to the existing dated log; on timeout, log an honest 'network never came up' line and exit nonzero WITHOUT touching topic state, so the next wake or a phone-triggered sweep finishes the day. SWEEP_SKIP_DONE=1 already makes a re-run finish only missing topics, so the wait composes cleanly. Verify by running with Wi-Fi off: observe the ticks, the honest abort, the clean completion once Wi-Fi returns._

## Premise

The morning brief is there when Kyle wakes even after the Mac slept, instead of blank because the sweep raced Wi-Fi — the unattended promise holds on exactly the mornings it's tested.

**Why now:** This is the failure mode of the pipeline's whole reason to exist — unattended fire after the Mac slept — and the v1 success check (~08-03: >=5 mornings/week) is imminent; a run of empty sleep-wake mornings would fail the criterion for a reason that has nothing to do with sweep quality.

## The bet

That a reliably-EMPTY brief on sleep-wake mornings erodes the morning habit as surely as a wrong one — and that everything shipped for this class (didn't-run banner, heartbeat, trust gauge, sweep-from-the-phone) SURFACES the failure but nothing PREVENTS the Wi-Fi-association race. A veteran knows the wake-before-network race is the canonical unattended-scheduler bug and that a blank brief on the mornings the Mac was asleep is precisely when Kyle most needs it to have worked.

## Decisions / open questions

(1) 90s cap right for post-wake Wi-Fi association? (2) Probe target: news.google.com vs a plainer connectivity check (captive-portal false positives)? (3) Should an aborted morning notify (heartbeat lane) or is the existing stale banner + next-wake retry enough?

## Credible first step

sweeps/schedule/run-scheduled.sh: insert the curl-retry preflight block after the `command -v claude` check and before `./sweep.sh`; log ticks to the existing $LOG; exit nonzero on timeout without invoking sweep.sh so no topic state is written. Dry-run with Wi-Fi toggled off.

## Dependencies

sweeps/schedule/run-scheduled.sh (after the command -v claude check), curl, the existing dated $LOG, SWEEP_SKIP_DONE=1 semantics, launchd wake behavior.

## Explicitly out of scope (revisit later)

Pure shell — no Python changes, no retry-inside-sweep logic, no launchd plist changes.

## Identity/positioning note

none — tethered.
