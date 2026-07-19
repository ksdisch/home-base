# Copy the Bytes Before You Touch Them

**Status:** Idea — not committed. Added by `/brainstorm` (Harden mode) on 2026-07-19.

_init_db runs every forward migration unconditionally against the single learning-hub.sqlite file holding every note, SM-2 mastery record, custom topic, and reflection Kyle has ever saved, with no byte-level snapshot taken first -- so one typo'd ALTER, or a migration written against a table shape that drifted out-of-band, mutates the sole copy with nothing to restore from._

## Premise

store/db.py applies every forward migration on every connect, mutating the one .sqlite file that is Kyle's complete history of notes, mastery, custom topics, and reflections. There is no managed-DB redundancy (assumption 2). The shipped PR #52 migration-ledger hardening proves a migration ran but never copies the file first -- a genuinely different concern (record vs. preserve), which is why this is not a duplicate. This adds an unconditional pre-migration file snapshot so a typo'd or shape-drifted ALTER is recoverable instead of catastrophic.

**Why now:** Post-M7 the store has accreted M1-M7 tables and is still evolving (custom-topics UI surfacing, future modes); the drift incident already happened once on 2026-07-16. Both arcs are complete and the ~08-03 v1 check is near, but schema changes will keep landing, and every unguarded migration startup is another roll of the dice against the sole copy of everything Kyle has saved.

## The bet

Bet targets assumption 2 (Mac-local by design): there is no managed-DB redundancy -- one Mac, one file, no hosted-Postgres point-in-time restore backstopping it. What must be true for this to be worth it: a single irrecoverable loss of all notes/mastery/reflections is catastrophic enough to justify one line of copy2, and a file snapshot is genuinely cheaper insurance than a migration-test suite that would otherwise have to stay perfect forever across an actively-evolving schema (M1-M7 each added tables). The 2026-07-16 incident documented right in the init_db comment proves migrations already collide with a store shape that drifted outside the app. Veteran flinch: the shipped PR #52 ledger hardening LOOKS like it made migrations safe -- it made them idempotent and honest, but it never preserves the pre-migration bytes, so the ledger faithfully records the damage it cannot undo. The sharp, uncompromising form is the point: the snapshot must be UNCONDITIONAL once-per-startup before the loop, NOT gated on schema_migrations -- gating it reintroduces exactly the ledger-as-gate PR #52 removed, so in the precise drift incident (ledger says applied but _safe_alter re-runs the ALTER by table shape) a gated backup is skipped at the exact moment the ALTER fires.

## Decisions / open questions

(1) Retention: keep only the most recent snapshot (overwrite each startup), a bounded ring of N, or timestamped-and-never-pruned (cheapest to write, needs eventual cleanup)? (2) Unconditional once-per-startup copy2 vs once-per-new-version -- the steelman argues unconditional to avoid re-introducing the ledger-as-gate PR #52 deliberately removed; confirm the startup-frequency cost is acceptable (the SQLite file is small and LaunchAgent startups are infrequent). (3) Where do snapshots live -- beside the db, or in a data/backups/ subdir so they don't clutter and are easy to gitignore/prune?

## Credible first step

backend/app/store/db.py init_db (VERIFIED lines 38-62): before the `for version in sorted(MIGRATIONS)` loop (line 50), shutil.copy2 the resolved db_path (get_settings().db_path) to a timestamped sibling (e.g. {db_path}.bak-{utc-timestamp}), UNCONDITIONALLY -- only skipping the fresh-DB case where the file doesn't exist or is empty. Verifiable: run init_db against a populated fixture DB and assert a .bak-* file with identical bytes appears before any ALTER executes. (Input's wedge line ~43 is close; the snapshot goes immediately before the migration loop at line 50, and the steelman drops the input's schema_migrations gating -- flagged in open_questions.)

## Dependencies

backend/app/store/db.py (init_db, connect, get_settings().db_path) and shutil (stdlib). No schema.py change, no new table, and deliberately NO dependency on the schema_migrations ledger (see the_bet). Sits adjacent to the already-shipped PR #52 ledger hardening inside the same init_db function.

## Explicitly out of scope (revisit later)

Not a rollback/restore command -- v0 only takes the snapshot; restoring is manual (copy the .bak back). NOT gated on schema_migrations (that's the anti-pattern PR #52 removed and the security-theater objection's exact trap). No change to _safe_alter or the migration loop's behavior. No snapshot pruning/rotation automation in v0 (an open question, not the wedge). Not a general app-wide backup system -- just the one pre-migration file copy.

## Identity/positioning note

none — tethered.
