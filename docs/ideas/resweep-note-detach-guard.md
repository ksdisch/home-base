# The Note That Vanishes When You Distrust the Sweep

**Status:** Idea — not committed. Added by `/brainstorm` (Harden mode) on 2026-07-19.

_A manual same-day re-sweep (TOPIC=<slug> ./sweep.sh) rewrites headlines, which shifts every item's sha1(date|slug|headline) id, so notes Kyle already attached silently detach from the Today view with no error, no log line, nothing._

## Premise

Kyle glances at a thin-looking topic mid-morning, having already left a note on an item, and reruns just that topic by hand for a fuller pass. The fresh websearch rewords the headline even for the same underlying story, so _structured_topic's sha1(date|slug|headline) id changes for every item and the notes join in GET /api/brief (keyed on item_id) finds nothing to attach — the inline indicator silently disappears from Today. The note isn't lost, but the read-time join that makes notes 'attach to what you're reading' breaks exactly when he re-triggers the sweep. This card adds a cheap, loud pre-overwrite warning so that break stops being invisible.

**Why now:** Post-M7 the roster runs 8 topics unattended every morning and M2's read-time id + inline notes are the trust anchor the ≥3 notes/week v1 criterion (~08-03 check) rests on. Manual single-topic re-sweep is a documented, supported path (sweep.sh header line 12, no SWEEP_SKIP_DONE guard for a hand-run) — and it's the exact action Kyle takes when he distrusts the first pass, i.e. precisely when he's most likely to have just been reading and annotating that topic.

## The bet

Targets assumption 6 (the brief is read-time-assembled; ids/joins happen at render over the raw sweep JSON). The bet: the harm here is the SILENCE, not the detach itself — the note still lives in brief_notes and on /notes — so the correct harden is to make the moment loud, not to prevent the id shift. A veteran flinches because a warn-only guard leaves the orphaning fully intact: ids still move, notes still drop off Today. Steelmanning it as harden means refusing to blunt it into a safer 'auto-rematch' or 'back up the JSON' move — the canonical guard for a silent-wrongness break is a loud signal fired at the exact command Kyle typed, and that stays true to the mode.

## Decisions / open questions

(1) Warn-only vs. the two sibling guards the convergent family also proposed — a .bak snapshot of the JSON before overwrite (Silent-Wrongness lens), or a headline-equality fallback in the brief.py notes join to auto-rematch orphaned notes (Source-of-Truth-Drift lens): warn-only is the smallest and most on-mode, but should the fallback-rematch land as a v2? (2) A stderr line during a manual CLI run is easy to miss — is a non-zero exit hint or a summary count at the end of the run worth it? (3) Should the same warning cover the developing-dedup labels, which also key off the shifting id?

## Credible first step

In sweep.sh's per-topic loop, right after the SWEEP_SKIP_DONE existence check (line 93) and before the RENDERER writes $OUT_DIR/$topic.json (~line 127): when $OUT_DIR/$topic.json already exists for today, shell one python3 line calling store.list_brief_notes(topic_slug=topic, brief_date=DATE) (backend/app/store/db.py:289, already filters by slug+date) and, if the count is >0, print a loud stderr warning naming the note count before overwriting. Verify by running TOPIC=ai-llms ./sweep.sh, adding a note via the notes API, re-running the same command, and confirming the warning names 1 note. The input's wedge location is correct — the id contract lives in backend/app/sweeps.py _structured_topic (sha1 at line 91), confirmed.

## Dependencies

sweep.sh per-topic loop (the SWEEP_SKIP_DONE branch, line 93); backend/app/store/db.py list_brief_notes (exists, slug+date filtered); the sha1 id scheme in backend/app/sweeps.py _structured_topic (line 91). No schema change, no write-path change, no new endpoint.

## Explicitly out of scope (revisit later)

Not preventing the id shift or blocking the overwrite; not auto-rematching orphaned notes by headline in the brief.py join; not snapshotting the JSON to .bak; not touching the notes write path or brief_notes schema. v1 is a single warn-not-block stderr line — converting silent to loud, nothing more.

## Identity/positioning note

none — tethered.
