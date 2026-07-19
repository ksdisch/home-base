# The Readiness Brief — tomorrow, not yesterday

**Status:** Idea — not committed. Added by `/brainstorm` (Moonshot mode) on 2026-07-19.

_A forward-tense section pinned above the brief that projects Kyle's next ~72 hours by colliding the swept world against his own calendar and job-search/life state, so its unit is a collision that rehearses him for what's coming, not a card that reports what happened._

## Premise

Today's brief is strictly a record of the past — sweeps store raw JSON, the page assembles yesterday's items at read time. As news commoditizes, the scarce good isn't the headline but the rehearsal: 'Your Corewell interview is Thursday — three things moved in healthcare analytics you could name; the Celtics play the night before, plan around it; a bill's due Friday that collides with the paycheck gap.' The same sweep machinery points forward, joining the external world against Kyle's own calendar and life-state to output collisions, not cards.

**Why now:** Post-M7 both arcs are complete and the retrospective brief has hit diminishing returns exactly as the ~08-03 v1 check approaches. M3 already ships the machinery — read-time developing/first_seen trajectory labels computed across days — but it is used only to describe the present. Turning that same cross-day trajectory read forward is the cheapest moment to test whether readiness beats recency, before the habit calcifies as 'a thing I read.'

## The bet

Targets assumption 6 (the brief is read-time-assembled from a stored raw record of the PAST), with a reach into assumption 2 (Mac-local). The one thing that must be true: as feeds commoditize, readiness — not news — is the scarce good, and Kyle will value being rehearsed for the next 72 hours over being told the last 24. A veteran flinches because a 'Coming up' calendar widget is trivial, but the collision/rehearsal reframe forces the brief to reach into calendar+vault state the read-time-from-sweep-JSON pipeline was deliberately built never to touch, inverting the past-tense premise the whole thing was architected around.

## Decisions / open questions

(1) Where do the Google Calendar + 30-job-search/ vault reads live relative to this Mac-local app, and is a read-only bridge acceptable under assumption 2? (2) With only in-repo developing-streak trajectories, is a v0 forward projection felt as real readiness or as a thin 'trending' list — is the calendar join load-bearing for the whole idea? (3) The collision ranker (proximity-in-time × relevance): who tunes it, and does a projected/inferred item need the same generative gate as every other surface (assumption 4)?

## Credible first step

Add a read-time forward-projection in backend/app/sweeps.py alongside _annotate_developing / _history_first_seen (verified: both already walk prior-day data/sweeps/<date>/ JSON), emitting a ranked 'Coming up' list onto BriefResponse in backend/app/api/brief.py's get_brief, pinned above the topics in frontend/src/pages/Brief.tsx. CORRECTION: the input named sweeps/render_brief.py, but that file is only the per-topic JSON validator + gradeable-Markdown renderer sweep.sh pipes each topic through — it never assembles the served brief and never reads cross-day history; the read-time assembler is backend/app/sweeps.py served by backend/app/api/brief.py. v0 collides only in-repo developing-streak trajectories; the flagship calendar + 30-job-search/ vault join lives outside this repo.

## Dependencies

backend/app/sweeps.py history walker (_history_first_seen) and the load_brief_topics assembler; backend/app/api/brief.py + BriefResponse; frontend/src/pages/Brief.tsx for the pinned strip. For the flagship collision: read-only Google Calendar access + the 30-job-search/ vault, both outside this repo in Kyle's Cowork/vault environment.

## Explicitly out of scope (revisit later)

No writes to calendar or vault (read-only). No new LLM call for v0 — the projection is deterministic over sweep-JSON trajectory history. Does not replace the retrospective brief; it is pinned above it, not instead of it. Not a general calendar client — only collisions that touch a swept item.

## Identity/positioning note

stretch — reaches into calendar/vault state the read-time pipeline never touches and flips the brief's tense from retrospective to anticipatory, but v0 lands as an added pinned section rather than a full replacement. At full realization it becomes identity-shift: the project stops being a past-tense newspaper and becomes a future-tense readiness engine — flagged so the ambition isn't quietly sanded down to a next-events widget.
