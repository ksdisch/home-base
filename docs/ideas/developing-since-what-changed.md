# Developing since when? The badge that promises change and can't name it

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-19.

_The two affordances that most invite "so what actually changed?" — the prominent "developing · since Jul 14" badge and the adjacent "Ask about this" chat — both structurally cannot tell Kyle what moved, because neither compares the item against the prior-day digest that is already sitting on disk under data/sweeps/._

## Premise

Home Base flags an item "developing" whenever a matching headline or shared source URL appeared earlier that week, and puts an "Ask about this" chat one tap away. Both affordances connote that the system is tracking a story's movement — but developing is pure identity-match repeat-detection (it never compares digest text), and the chat prompt is built from today's served item alone with no prior-day lookup. So the two surfaces that most invite "tell me what's new" both silently can't. This threads the prior-day digest — already persisted as the raw sweep record — into the chat prompt for developing items, and exposes it verbatim behind the badge, closing the gap without any new sweep-time generation.

**Why now:** Post-M7 both halves of the promise now exist and both quietly under-deliver on the same implied continuity: developing labels shipped M3, Ask-about-this shipped M5, and neither ever reads the prior day. The badge already honestly renders "first appeared on X" (verified Brief.tsx:297-306), so the fix is a small honesty-upgrade on the project's own riskiest assumption right before the ~08-03 v1 trust check.

## The bet

Targets assumption 1 (sweeps stay accurate/trustworthy). The bet: continuity Kyle can see with his own eyes — the earlier digest rendered verbatim — earns more trust than a slicker model-summarized "what's new," and it can be delivered with zero new generative surface because the raw prior digest is already on disk and the chat route already holds sweeps_dir. A veteran flinches at "make the developing badge finally cash the check it's been writing since M3," then relaxes when it turns out to be bytes-already-on-disk plumbing, not a new LLM call.

## Decisions / open questions

Does the chat prompt include the full prior digest or a bounded window when an item has developed across several days (first_seen could be up to a week back)? Should the verbatim-prior-digest badge disclosure be a v1 deliverable or does the chat-continuity half ship alone first? How is the prior item matched when the same story spans multiple identity keys that drifted across days?

## Credible first step

Do the clean half first: the chat route chat_about_brief_item in backend/app/api/brief.py (~lines 116-131) already has settings.sweeps_dir and the served item carrying developing/first_seen from _annotate_developing — when item['developing'] is set, walk the prior day's data/sweeps/<first_seen>/<slug>.json (reuse the _history_first_seen identity-key match in backend/app/sweeps.py:175-202) to pull the earlier digest verbatim, and thread it into build_prompt. CORRECTION to the input wedge: build_prompt (backend/app/chat.py:58-86) takes only topic/item/question/brief_date and has NO sweeps_dir handle, so the prior-day lookup must happen at the brief.py call site (where sweeps_dir is in scope) and be passed in as a new param — the sweeps.py history walker is the reusable read helper, not the wiring seam. Testable via chat.py's existing fake-runner seam.

## Dependencies

backend/app/sweeps.py _history_first_seen / _item_identity_keys (read helper, already reads sweeps_dir); the served item's developing/first_seen fields from _annotate_developing; backend/app/api/brief.py chat route (holds sweeps_dir); backend/app/chat.py build_prompt (gains a prior-digest param) + its fake-runner test seam; the un-pruned per-date data/sweeps/<date>/<slug>.json history on disk.

## Explicitly out of scope (revisit later)

A summarized or model-generated "what changed" digest-diff — that is a new generative surface and trips the assumption-4 gate; v1 stays deterministic (verbatim prior digest + chat continuity only). No change to how developing is DETECTED (still identity-key match), no new sweep-time output, no new stored record.

## Identity/positioning note

none — tethered.
