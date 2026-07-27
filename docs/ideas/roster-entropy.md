# Roster entropy: the topics stopped being about current-Kyle, and every gauge stayed green

**Status:** Idea — not committed. Added by `/replenish` (Premortem lane) on 2026-07-26.

_The habit dies of boredom and dead air, not fabrication. sweeps/topics.json is heavily sports (Chiefs, Celtics, Indiana, Kansas BB, Blues, fantasy football) that go months-dormant off-season, and the M7 scout only ever ADDS topics — nothing retires or re-weights one, so the roster only accretes. Two distinct rots collide with every trust instrument (M0 grading, Calibrated Doubt, the trust gauge) reading perfectly healthy: (a) engagement drought — topics that produce events Kyle never touches (near-zero notes/chat/feedback for 30 days), and (b) supply drought — topics that stopped producing real events at all (near-zero trailing-45-day envelope events, high 'developing' repeat ratio). A brief that's 60% about a sport that's out of season and 20% about topics Kyle stopped reading is accurate, trustworthy, and boring — and boring is what actually ends a morning habit. The antibody is a deterministic dual detector computed entirely from exhaust the app already writes (per-topic trailing counts from brief_notes/brief-chat/news_events + the 'developing' labels M3 already emits), surfaced as a muted 'quiet for N weeks' badge on Today's topic chips with a one-tap pause that reuses the scout's existing topics.json write path — the first SUBTRACT affordance in a project that is all ADD._

## Premise

The morning brief stops silently drifting toward off-season sports and topics Kyle quit reading — cold topics become visible and one-tap-pausable — so the roster tracks current-Kyle instead of accreting forever, and the habit is defended against death-by-boredom, the failure mode every trust gauge is blind to.

**Why now:** Sports seasonality means the roster's relevance swings hard across a 12-month window — several of the current topics will hit their dead months well inside it — and the scout has been quietly accreting the roster since M7 with no counterweight. The 08-03 check will report visits and notes but has no per-topic view, so a roster that's slowly going cold is exactly the failure it can't see; a cold-topic readout gives that check eyes before the boredom compounds.

## The bet

That accuracy is necessary but not sufficient — that a fully-truthful, fully-trusted brief can still lose Kyle by drifting to topics that no longer earn his attention, and that per-topic engagement + supply signals (both already in the ledgers) predict that drift before the whole habit goes. What makes a veteran react: the project has enormous ADD machinery (scout, moonshots, ten gate overrides) and zero SUBTRACT machinery, and every existing 'is it healthy' instrument watches whether items are TRUE, none whether they're still WANTED. The dual signal names the blind spot precisely: a topic can be green on every gauge and dead to Kyle.

## Decisions / open questions

(1) Thresholds: 30-day zero-engagement and what developing-repeat ratio count as cold? (2) Badge on Today vs a roster health section on Progress? (3) Should the scout ever propose RETIRING a topic the way it proposes adding one?

## Credible first step

One sitting: a deterministic cold-topic detector alongside backend/app/mirror.py computing, per roster slug, (a) trailing-30-day notes+chat+feedback counts and (b) trailing-21-day 'developing'/repeat ratio from the stored envelopes; surface it as a muted 'quiet for N weeks' badge on Today's topic chips in the brief frontend with a one-tap pause that writes through the scout's existing sweeps/topics.json path; add a 'cold topics' sentence to the Mirror so the 08-03 check can finally see roster health.

## Dependencies

brief_notes / brief-chat.jsonl / news_events trailing counts, the developing labels (M3), sweeps/topics.json pause path, backend/app/mirror.py pattern, Brief.tsx chips.

## Explicitly out of scope (revisit later)

No auto-pause and no auto-retire — the detector proposes, Kyle taps. No LLM. No new store tables (computed from existing exhaust at read time).

## Identity/positioning note

none — tethered.
