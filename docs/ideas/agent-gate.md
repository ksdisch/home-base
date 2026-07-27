# The Agent Gate — Home Base as the accreditation chokepoint for every AI acting on Kyle's behalf

**Status:** Idea — not committed. Added by `/replenish` (Moonshot lane) on 2026-07-26.

_IDENTITY-SHIFT. Home Base stops being only the app Kyle reads and becomes the single gate every other agent in his life — Claude Code crons, future email/shopping/scheduling agents — must file through. Proposals land in the existing draft-only Overnight queue tagged by source agent; Kyle's approve/discard verdicts accrue into a per-agent calibration ledger; an agent's earned track record then governs how its future proposals are framed (the untrusted-item-framing idea generalized from news items to acting agents). The whole thing reuses machinery that already exists: the Overnight queue reduce, the approve/discard resolution rows, the trust-framing surface. Nothing new gets sent — this is the inverse of the parked vault bridge: agents reach IN through the queue; Home Base still reaches out to nothing._

## Premise

Kyle's morning stops being authored solely by the sweep. Other agents in his life file proposals that inherit the same draft-only trust discipline, and each agent visibly earns (or loses) standing over time — the brief becomes the accountable arbiter of every AI acting on Kyle's behalf, without any of them ever acting unattended.

**Why now:** Agent proliferation is the defining platform shift of the horizon, and Home Base is unusually well-positioned: the overnight.jsonl append-only ledger (first-proposal-per-id wins) and the approve/discard resolution rows already ARE an accreditation substrate — the ledger falls out of data the queue is already writing. Wait, and the trusted chokepoint gets built somewhere Kyle doesn't control.

## The bet

THE ONE THING THAT MUST BE TRUE: in 2-5 years of agent proliferation, the scarce asset is a single trusted human-in-the-loop chokepoint that arbitrates competing agents — and Home Base already owns the only ground truth for it: years of Kyle's real approve/discard/note/wager verdicts. TARGETS: the implicit single-author axiom (the sweep is the sole author of the morning), while KEEPING assumption 4 (everything inbound stays draft-only) and assumption 5 (still local, still single-human). VETERAN FLINCH: nothing anywhere in Home Base grades the AGENTS — M0 and Calibrated Doubt grade items and the sweep's own predictions; this turns self-grading into a reputation economy over third parties, and a project veteran built the queue as a one-author surface and now sees authorship becoming open and reputation-scored.

## Decisions / open questions

(1) Trust ledger granularity — per-agent, or per-agent-per-errand-type (matching the Overnight send-gate design)? (2) Does an external proposal ever get to REQUEST a send, or is inbound strictly draft-only forever? (3) Auth for the propose endpoint beyond localhost-only (tailnet peers?).

## Credible first step

One sitting, no new axiom broken today: sweeps/actions_queue.py already appends well-formed proposal rows to backend/data/overnight.jsonl and backend/app/overnight.py reduces them tolerantly (confirmed: kind/id/date/type/slug/item_id/body schema, first-row-wins). Add an optional source_agent field (actions_queue writes source_agent:"sweep"), plus a localhost-only POST /api/overnight/propose router in backend/app/api that appends a well-formed proposal row — so any local Claude Code session or cron can file into tomorrow's queue today. Render source_agent on the queue card and derive a per-agent approved/discarded tally from the resolution rows already on disk.

## Dependencies

backend/data/overnight.jsonl schema + backend/app/overnight.py reducer (first-row-wins), sweeps/actions_queue.py, the untrusted-item-framing pattern, a new POST route in backend/app/api/.

## Explicitly out of scope (revisit later)

No send/execute for third-party agents ever unlocks by default — the per-errand-type graded send gate applies doubly here. No vault bridge. No remote (non-tailnet) inbound. v0 grades and frames; it does not rank or throttle agents.

## Identity/positioning note

identity-shift: Home Base's identity moves from 'the single pane Kyle reads' to 'the single gate agents must pass' — the morning brief becomes infrastructure with an inbound protocol, and the calibration machinery turns from self-grading into a trust economy over third parties.
