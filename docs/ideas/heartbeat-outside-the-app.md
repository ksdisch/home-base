# The Silence Nobody Hears

**Status:** Idea — not committed. Added by `/brainstorm` (Premortem mode) on 2026-07-19.

_The whole Mac-local stack (both LaunchAgents, Tailscale, Kokoro, launchd, the nvm/venv/Homebrew paths baked into the plists) can stop firing with zero notification, so the first signal of death is an empty morning brief — by which point the ≥5-mornings/week habit is already broken._

## Premise

Home Base's entire value depends on a Mac-local stack that runs unattended for months at a time, and today nothing watches whether it's still alive — the cost ledger records every successful run but nothing reads it for staleness. A tiny independent dead-man's-switch, deliberately built to fail differently from the sweep pipeline, reads the last-run timestamp and reaches Kyle through a channel outside the app (macOS notification / iMessage / a Desktop flag) the moment the stack goes quiet for too long. The failure this guards is the one that kills the habit invisibly: an empty morning nobody was warned about.

**Why now:** Post-M7 the full stack now runs genuinely hands-off forever: com.homebase.sweep + com.homebase.server LaunchAgents installed once via install-schedule.sh filling __PLACEHOLDER__ paths, plus Tailscale + Kokoro + launchd on-wake catch-up. The ~08-03 v1 habit check is weeks out and measures exactly the ≥5-mornings/week metric a single silent death between now and then would zero — with no instrumented warning before it does.

## The bet

That a liveness check built to fail differently from the pipeline — and to reach Kyle OUTSIDE the app he's already stopped opening — catches the death before the empty morning trains him to quit. It targets assumption 2 (Mac-local by design): one Mac, one process tree, no managed redundancy, nothing watching the watcher. A veteran reacts because an unattended single-machine stack that has run 'clean' for months is precisely the one whose first failure is invisible — the .runs.jsonl ledger records every SUCCESS and nothing ever reads it for absence.

## Decisions / open questions

Threshold + schedule (36h vs tighter, and 09:00 CT only works if the Mac is awake then — an asleep Mac defers osascript, so does the flag-file path need the server to surface it too?); which out-of-band channel is most reliable given the Mac may itself be asleep/off (Desktop file vs osascript vs self-iMessage); should the heartbeat also probe tailnet reachability (PR9) directly, or only ledger staleness.

## Credible first step

New sweeps/schedule/heartbeat.sh + sweeps/schedule/com.homebase.heartbeat.plist.template, mirroring the real sweeps/schedule/com.homebase.sweep.plist.template and installed the same way through sweeps/schedule/install-schedule.sh, scheduled independently (~09:00 CT) so it can't die the same way as the sweep. It stats the newest `ts` row in data/sweeps/.runs.jsonl (VERIFIED: sweeps/envelope.py ledger_row writes a per-topic UTC `ts`, and sweeps/schedule/README.md confirms the path) and, if >36h stale, fires an out-of-band alert — osascript display-notification and/or a Desktop flag file — a channel that reaches Kyle even when the app/tailnet is down. Per the selection_note, one antibody must cover all three folded failure modes: PR1 (baked nvm/claude path rots after a Node/Python bump), PR8 (an in-app staleness banner structurally can't escalate when the whole server is down), PR9 (Tailscale node-key expiry). The in-app banners cannot cover the case where the app itself isn't reachable — that is exactly the gap this fills.

## Dependencies

data/sweeps/.runs.jsonl (gitignored ledger written by sweeps/envelope.py); the existing sweeps/schedule/ install pattern (com.homebase.sweep.plist.template + install-schedule.sh); macOS launchd + osascript; optionally the server's degraded-state rendering path to surface a flag file in-app as a secondary channel.

## Explicitly out of scope (revisit later)

Auto-remediation/self-healing of the dead stack; in-app-only staleness banners (that's PR8's lane and it's the channel this explicitly routes around); any change to the sweep pipeline itself; a hosted/off-Mac watcher (parked: hosted phone access).

## Identity/positioning note

none — tethered.
