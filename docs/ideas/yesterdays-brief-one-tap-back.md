# Yesterday's brief, one tap back

**Status:** Idea — not committed. Added by `/brainstorm` (QuickWin mode) on 2026-07-19.

_An optional ?date= on GET /api/brief plus a /brief/:date route, so a note's date/headline snapshot on /notes links straight into that archived morning and prev/next arrows let Kyle walk the never-pruned sweep history._

## Premise

Every brief_notes row already snapshots item_id, topic_slug, brief_date, and item_headline precisely so a note outlives its sweep file, and load_brief_topics(sweeps_dir, date, roster) is already date-generic. Yet /notes shows that snapshot as flat text with no way to see the item in its original context, and once a new sweep lands the whole prior day is gone from the UI. This threads an optional date param through the one endpoint that hardcodes 'latest', adds one route, and turns the note snapshot into a link — covering both the note-linkback (Almost-Done lens) and prev/next-day navigation (Force-Multiplier + Free-Lunch lenses) as one archived-day view.

**Why now:** Post-M7 the notes surface (M2) and the whole per-date sweep archive both exist and are stable, but 3 lenses independently flagged that get_brief() only ever calls latest_sweep_date — the strongest QuickWin convergence in the pool. With the ~08-03 v1 check watching '≥3 notes/week', making notes into live anchors (not inert captions) sharpens the exact surface the success criterion rewards, right when the archive is deep enough to be worth browsing.

## The bet

Targets assumption 6 (the brief is read-time-assembled; stored sweep JSON is the raw record). The one thing that must be true: that Kyle values revisiting an archived morning — verifying weeks later what he actually reacted to — enough to justify opening a door that's been shut since M1. A veteran reacts because this is the FIRST feature that reads an arbitrary old day's raw record on demand: every data/sweeps/<date>/ folder has sat on disk forever (no prune logic, _history_first_seen already walks them) yet the instant a new sweep lands, every prior morning goes literally unreachable in the UI. The design promised the stored JSON was a durable record; this is the first time the product cashes that promise.

## Decisions / open questions

Should the historical day's audio player thread date or just hide when not latest? Should the 'this brief is from a previous day — run make sweep' stale banner (Brief.tsx:424) be suppressed when Kyle intentionally opened a past day, so it doesn't nag? Does v1 ship prev/next arrows too, or land the note-link first and add arrows as a fast follow?

## Credible first step

backend/app/api/brief.py get_brief() (line 56): add date: Optional[str] = None, default to latest_sweep_date when absent, 404 if the passed day_dir doesn't exist — the notes-join at lines 61-70 already keys on the served date, so it works unchanged. frontend/src/App.tsx: add a /brief/:date route in the Routes block (lines 121-138) rendering the existing Brief page parameterized by date. frontend/src/pages/Notes.tsx: wrap the date/headline snapshot line (lines 91-97) in a react-router Link to /brief/:date. CORRECTION to the input wedge: get_brief_audio (brief.py:88) also hardcodes latest_sweep_date, so a past-day view either threads date there too or hides the 🎧 player when the viewed date isn't latest — the input's wedge omitted this.

## Dependencies

load_brief_topics (verified date-generic, sweeps.py:227), the data/sweeps/<date>/ folders (verified never pruned — no retention logic in sweeps.py), the notes-join keyed on brief_date (brief.py:61-70), and react-router already in use (App.tsx).

## Explicitly out of scope (revisit later)

No retention/prune changes; no new stored record or table; no regenerating audio for historical days; no editing or re-sweeping a past day — read-only time travel over what's already on disk.

## Identity/positioning note

none — tethered.
