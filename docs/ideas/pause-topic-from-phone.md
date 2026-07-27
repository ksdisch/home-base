# Pause a topic from the phone — the roster flag with no toggle

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-07-26.

_QuickWin lane; doubles as the actuator half of the Premortem roster-entropy antibody ([`docs/ideas/roster-entropy.md`](roster-entropy.md))._

_A PATCH /api/brief/topics/{slug} that flips the existing paused flag in sweeps/topics.json, plus a small pause/resume control on the Today topic chips — the first roster verb with UI besides the scout's add. One sitting._

## Premise

Kyle can mute a topic that's gone quiet (or expensive) from his phone in one tap, keeping the brief trustworthy and cheap without editing a JSON file on the Mac.

**Why now:** Targets assumption 1 (sweep accuracy sustains the habit) at its highest-pressure point: 6 of 8 topics are sports and it's late July, exactly when offseason thin-news fabrication pressure peaks. Also assumption 6 — today a pause requires SSH-editing JSON on the Mac. The ledger shows each opus topic runs ~$1.2/day, so a pause has direct, felt savings.

## The bet

The bet: the ability to mute a thin-news topic in one tap keeps the roster honest and the habit alive. What a veteran respects: the flag already exists and is already honored end-to-end (sweeps.py:52 reads it, render gate obeys it), sweeps/README.md line 37's OFFICIAL procedure is literally 'flip paused: true by hand', and the atomic-write machinery is already built — append_roster_topic in news.py owns the _roster_write_lock + tmp-file-and-replace at line 138. The only missing piece is a PATCH and a chip toggle.

## Decisions / open questions

(1) Long-press vs an explicit small control on the chip — what's the right one-handed gesture that can't misfire? (2) Should pause require the same confirm beat as other destructive-ish taps (undo toast)?

## Credible first step

Add set_topic_paused(roster_file, slug, paused) beside append_roster_topic in /Users/kyledisch/Projects/home-base/backend/app/news.py (reuse its _roster_write_lock + atomic replace, line 138), wire a PATCH route in /Users/kyledisch/Projects/home-base/backend/app/api/brief.py, add a paused-state toggle to the topic chips in /Users/kyledisch/Projects/home-base/frontend/src/pages/Brief.tsx.

## Dependencies

sweeps/topics.json paused flag (honored end-to-end already), _roster_write_lock + atomic replace in backend/app/news.py, a PATCH route in backend/app/api/brief.py, Brief.tsx topic chips.

## Explicitly out of scope (revisit later)

No auto-pause (that's the roster-entropy detector's call to propose, Kyle's to tap), no topic delete, no reordering.

## Identity/positioning note

none — tethered.
