# Stuck on Stale, Phone in Hand

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-19.

_When the served brief is a day old, the only recovery the UI offers is a `make sweep` terminal command (Brief.tsx stale banner, lines 424-432) — unusable on the keyboard-less iPhone that M6 shipped Today to._

## Premise

M6 shipped Today to Kyle's phone for the 6:30am read, and assumption 2 guarantees the brief will sometimes be stale (Mac asleep, catch-up not yet fired). The one recovery the UI offers — `make sweep` in a terminal — is impossible on a keyboard-less phone. This turns the stale banner into a tap: a lock-guarded POST that re-invokes the same ./sweep.sh pipeline launchd already runs, then polls until the fresh brief lands. It crosses assumption 2's read-only-phone line on purpose, and the concurrency guard is what keeps that crossing safe.

**Why now:** M6/M7 put Kyle on the phone at 6:30am as the scoped primary moment, and assumption 2 (Mac asleep/off = stale brief) guarantees the stale-banner case actually happens — so the one recovery path is precisely the one he structurally cannot take from where he is standing.

## The bet

That letting the phone reach back and kick the Mac is worth deliberately crossing assumption 2's read-only-phone-reach line — the sweep and the server already run on the same Mac, so the capability is a lock-guarded POST, not new infrastructure. A veteran flinches because it opens a write/trigger surface on a Tailscale-exposed server that today only reads, and double-firing while the on-wake catch-up sweep is already running is the obvious footgun the guard must close.

## Decisions / open questions

Guard concurrency with a lockfile/PID check or by reusing sweep.sh's own SWEEP_SKIP_DONE idempotency? Does the trigger need any auth beyond the single-user tailnet trust boundary (assumption 5)? Full 8-topic sweep or offer per-topic re-run? How the button reflects in-progress state while polling for the newer date.

## Credible first step

Add a POST route in backend/app/api/brief.py (alongside get_brief, line 55) that shells out the repo-root ./sweep.sh (what `make sweep` runs, and what run-scheduled.sh→sweep.sh fires at 06:00) as a detached subprocess, guarded by a single lock so a tap is a no-op when a sweep is already running; wire a 'Refresh now' button into the `stale && !fromCache` banner (Brief.tsx 424-432) that calls it and polls get_brief until a newer date lands. Covers the family per the selection note: subsumes FR1 (the banner-copy-only fix) and extends to FR12 (phone-reachable roster edits) as the same phone-can-see-but-cannot-act gap. Repo-verified: brief.py exposes only GET/notes routes today with no sweep trigger, and `make sweep`→./sweep.sh (repo root, executable) is the real pipeline.

## Dependencies

backend/app/api/brief.py, ./sweep.sh (repo root), frontend/src/pages/Brief.tsx stale banner + a poll on api.brief; requires the server running on the Mac (it is, per com.homebase.server).

## Explicitly out of scope (revisit later)

No new LLM surface — it re-invokes the existing sweep pipeline verbatim; not the offline `fromCache` banner (that needs the hub reachable at all); FR12's roster-removal UI is named as the same family but not built in this first step.

## Identity/positioning note

stretch — a genuine new capability (phone triggers the Mac pipeline) against assumption 2's read-only phone reach, though it reuses the existing sweep pipeline and adds zero LLM surface.
