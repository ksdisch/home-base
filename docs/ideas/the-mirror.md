# The Mirror — the brief reads Kyle, not the world

**Status:** Idea — not committed. Added by `/brainstorm` (Moonshot mode) on 2026-07-19.

_A new top strip on Today that renders a candid, sourced read of Kyle himself each morning — 'You asked about agent evals 4 mornings running and wrote zero Celtics notes on the topic you've paused-then-unpaused three times; attention this week: 71% AI, 18% markets' — assembled fresh from this week's own behavior logs, not a stored profile._

## Premise

Every existing sweep points a telescope outward at AI, the Celtics, the market, while the exhaust of Kyle's own use — clicks, notes, asks, pause churn — sits in signal tables nobody reads. The Mirror inverts the telescope: the top strip of Today becomes a fresh, deterministic, sourced read of Kyle this week, grounded entirely in that logged signal so it re-reads him as he changes. No stored profile document, no outward LLM call for v0 — just counts plus one framing sentence assembled at read time, turning analytics-nobody-reads into the day's headline about himself.

**Why now:** After M7, four signal sources — news_events, brief_notes, brief-chat.jsonl, and topics.json pause churn — have been accumulating exhaust that nothing ever reads back to Kyle. The ~08-03 v1 check is itself about his behavior (≥5 mornings/week, ≥3 notes/week); the Mirror surfaces exactly those numbers as daily content instead of leaving them buried as a hidden success gate.

## The bet

That a mirror of Kyle's own logged behavior is a more compelling day-one headline than any external item, because his world is 90% his own life — and that turning the news_events/notes/chat exhaust from analytics-nobody-reads into the day's first story is a genuine new verb (reflect), not a dashboard. It targets assumption 6 (read-time-assembled from a stored raw record) by inverting what gets assembled: pure read-time synthesis over signal tables that already exist, no outward sweep, no new stored record. A veteran flinches because every prior sweep pointed the telescope outward; this turns it around and makes the product's subject the user, risking either uncomfortable candor or a limp stats widget.

## Decisions / open questions

1) brief-chat.jsonl and news_events may be sparse from light early use — what's the honest cold-start render ('not enough signal yet') so the mirror never fabricates a pattern from three data points? 2) v0 is deterministic counts + one hand-templated framing sentence (no LLM, honoring assumption 4) — is the deterministic sentence sharp enough, or does the candor that makes it a mirror eventually need a gated generative pass? 3) How candid is too candid — does surfacing 'you saved this and never opened it' feel like insight or nagging?

## Credible first step

Add a read-only 'You this week' aggregator and pin it atop the brief. Correction to the input wedge: this belongs in the BACKEND at read time — extend `get_brief` in `backend/app/api/brief.py` (which already joins notes read-time via `list_brief_notes`) with a deterministic aggregation over `list_news_events` + `list_brief_notes` (backend/app/store/db.py), the brief-chat.jsonl ledger (config.brief_chat_ledger), and topics.json pause churn, plus one framing sentence — surfaced as a new field on BriefResponse rendered in Brief.tsx. It must NOT go in `sweeps/render_brief.py`, which is a sweep-time, stdlib-only JSON validator with zero access to the SQLite store or news_events.

## Dependencies

backend/app/store/db.py helpers list_news_events + list_brief_notes (both verified present), foryou.py build_profile pattern for decayed weighting, config.brief_chat_ledger (brief-chat.jsonl), sweeps/topics.json pause flags, get_brief + BriefResponse in backend/app/api/brief.py, Brief.tsx for the strip. All read-only; no new writes.

## Explicitly out of scope (revisit later)

No new outward sweep and no new LLM surface for v0 — deterministic aggregation plus one templated framing sentence only. No stored profile record (that's the parked learner-profile doc). No writes of any kind, no cross-day trend charts, no learning-only scope; it's a whole-home-base behavioral render or nothing.

## Identity/positioning note

identity-shift: the product's subject changes from news to Kyle — Home Base stops being a window on the world and becomes a window on him. (Distinct from the parked static learner-profile doc: this is a live cross-surface behavioral render, re-computed every morning, spanning the whole home base, not just learning.)
