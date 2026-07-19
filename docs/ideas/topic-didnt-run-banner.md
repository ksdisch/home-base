# Say when a topic didn't run

**Status:** Idea — not committed. Added by `/brainstorm` (QuickWin mode) on 2026-07-19.

_A server-side diff of the active (non-paused) roster against the slugs that actually produced a file for the served date, surfaced as one Banner on Today so a silently-failed topic is visible instead of just absent._

## Premise

GET /api/brief already knows the full active roster (sweeps/topics.json, with pause flags) and already knows which slugs produced a <slug>.json/.md for the latest date (load_brief_topics). Today a topic with no file simply isn't in the topics list, so the page can't tell a quiet news day from a crashed sweep. Add the roster-minus-produced diff server-side (excluding paused topics), ship it as a `missing` list on BriefResponse, and render one small Banner on Today reusing the exact component that already handles the sibling topic.error case. No new writes, no new LLM call, no schema change — pure read-time honesty about data both sides already hold.

**Why now:** Eight topics have run unattended every morning since M3, and the ~08-03 v1 check rests on 'significant events reach Kyle HERE first' — which fails silently the first morning a topic dies and nothing says so. Both sides already hold the data; this closes the gap before the habit is tested.

## The bet

Targets assumption 1 (sweeps stay accurate/trustworthy — the project's own stated riskiest), inverted to its honesty edge: the trust-killer isn't a wrong item, it's an invisible one. The one thing that must be true: sweeps sometimes fail per-topic (one slug errors while the other seven land), making the gap between 'quiet Chiefs news day' and 'Chiefs never ran' a real and recurring event — not an all-or-nothing whole-dir failure. A veteran flinches because it deliberately puts a failure notice on the calm morning surface whose entire M0 thesis was earned trust; the steelman is that a brief which can't admit it's incomplete is exactly the brief that trains Kyle to stop believing a short day is really short.

## Decisions / open questions

(1) A topic that produced only a .raw.txt (failed validation) is skipped by load_brief_topics — should it show as 'didn't run' or get its own 'ran but didn't validate' wording, since it's a different failure? (2) Banner copy: one line naming the missing topics ('Chiefs and Blues didn't run today') vs. a per-topic placeholder inline in roster order? (3) Does this need to distinguish an off-season sport (predictably empty most days) from a true failure, or is surfacing every non-paused miss the honest default?

## Credible first step

backend/app/api/brief.py get_brief() (line 56) already holds `roster` (from load_roster, which carries the `paused` flag) and `raw_topics` (each with a slug) — compute `missing = [t['slug'] for t in roster if not t['paused']] - {t['slug'] for t in raw_topics}`, add it as a field on BriefResponse; frontend/src/pages/Brief.tsx renders one page-level Banner (same component already used at lines 273–277 for topic.error and 404–450 for page banners). Correction to the input wedge: the diff must exclude paused topics, or a legitimately-paused roster entry reads as a failure — load_roster exposes `paused`, so the exclusion is one predicate.

## Dependencies

load_roster (already returns the paused flag) and load_brief_topics (already computes present slugs) in backend/app/sweeps.py; the Banner component (frontend/src/components/Banner) already imported in Brief.tsx. No new store, endpoint, or sweep-side change.

## Explicitly out of scope (revisit later)

Not the empty-sweep-dir blanking fix (that's the complementary bug-hunt #1 whole-page case — this is the per-topic surfacing); no retry or re-run trigger; no alerting/notification outside the app; no historical record of which topics failed on which days; no change to how sweeps write or validate.

## Identity/positioning note

none — tethered.
