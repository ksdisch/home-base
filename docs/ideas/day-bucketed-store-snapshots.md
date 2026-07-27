# Day-bucketed store snapshots: stop the restore point from rotating itself away

**Status:** Idea — not committed. Added by `/replenish` (Harden lane) on 2026-07-26.

__snapshot_before_migrations in backend/app/store/db.py snapshots the SQLite store on EVERY init_db() (every server start) and keeps only the newest 5 microsecond-stamped .bak files (`[:-_SNAPSHOT_KEEP]` unlinks the rest). The LaunchAgent has KeepAlive=true: a bad migration or crash-loop afternoon burns all 5 slots with POST-damage copies in minutes, rotating away the last pre-damage copy — under the exact failure the snapshot exists to survive. On-disk proof it's already happening: two of the five current baks are from the same day (20260724T003254 + 20260724T010342). Guard: change retention from 'newest 5 files' to 'first snapshot per local day, newest N days' — derive a local-day stamp, skip copying if a .bak for today already exists (the day's FIRST snapshot is the most pre-damage one), prune to the newest 5 distinct days. One test that calls init_db() 10 times across a mocked day boundary and asserts day-one's snapshot survives._

## Premise

A crash-loop or bad migration can no longer rotate away the last clean copy of Kyle's store — the disaster-recovery guarantee actually holds when it's finally needed, instead of only on a calm day.

**Why now:** This is the shipped pre-migration-snapshot guard's own hidden self-defeat, not a re-proposal — the on-disk evidence shows slot churn is live, and the next store-corrupting migration or crash-loop (v13+ ADD COLUMN work is ongoing) is the moment the missing restore point costs Kyle his data.

## The bet

That the .bak siblings ARE the entire disaster-recovery story (db.py's own docstring: 'One Mac, one file, no managed-DB restore') — so a retention policy that evicts the last good copy at the worst moment silently defeats the guard under its own scenario. A veteran reads the crash-loop math: KeepAlive respawn plus unconditional snapshot-on-start plus newest-5 means five restarts erase every pre-damage copy in seconds, and the two same-day baks on disk prove the churn is real, not theoretical.

## Decisions / open questions

(1) Keep 5 days or 7? (2) Also keep the single most recent snapshot regardless of day (belt-and-braces for a multi-migration day)?

## Credible first step

backend/app/store/db.py _snapshot_before_migrations (lines 42-59): derive a local-day stamp, skip if today's .bak exists, prune to newest 5 distinct days instead of 5 files (~8 lines); add a test in backend/tests calling init_db() across a mocked day boundary asserting the first-of-day survives.

## Dependencies

backend/app/store/db.py _snapshot_before_migrations (the shipped HA11 guard — this hardens the guard itself), local-day stamping (America/Chicago).

## Explicitly out of scope (revisit later)

No restore automation, no snapshot of anything but the store file, no change to when snapshots fire (still every init_db) — only which ones survive.

## Identity/positioning note

none — tethered.
