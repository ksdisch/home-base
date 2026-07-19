# One mis-tap, no take-backs: destructive taps need an undo beat

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-19.

_Three one-tap destructive actions on the phone surfaces commit instantly with no confirmation, no undo, and no trace beyond the thing vanishing: News "Not interested" (fires a -8 not_interested signal into For You AND hides the card), and note Delete on both /notes and inline on Today._

## Premise

On a one-handed phone, three of Home Base's most reachable buttons destroy state the instant they're touched: /news "Not interested" both logs a -8 not_interested event (foryou.py) and hides the item, and Delete on /notes and on Today's inline notes removes a note with a single unconfirmed tap. None offers confirmation or undo. This adds one shared Undo-toast primitive that holds the mutation for a few seconds before it commits, and wires the three existing destructive handlers through it — turning fire-and-forget-permanent taps into catchable ones without touching the ranker, the weights, or the button layout.

**Why now:** M6 put Kyle on a one-handed, PWA-installed phone where thumb-reach mis-taps are the norm, and "Not interested" sits inches from "More like this" in the same card row (verified News.tsx:294-305). The ≥3-notes/week v1 criterion is judged ~08-03 — a note lost to a fat-finger Delete directly damages the exact metric the project is measured on, so the grace window protects a success number, not just a feeling.

## The bet

Assumption directly targeted: none — this guards the habit/trust loop rather than a load-bearing assumption. The bet that makes it one move instead of three: the friction is identical across News and Notes (a fire-and-forget mutation behind a thumb-reach button), so a single shared "hold-then-fire behind an Undo toast" primitive is worth building once and wiring into every destructive call site. A veteran's reaction is mild — undo-on-delete is table stakes — so the non-obvious, defensible part is the MERGE: recognizing not_interested, /notes delete, and Today's inline delete as the same move, credited jointly with the Harden lane (HA10).

## Decisions / open questions

One shared toast component or per-surface toasts (News already has a card-list layout; Notes/Brief differ)? Does Undo also need to work after a route change, or is holding the mutation client-side for the window and only firing on timeout enough? Should the not_interested hide be optimistic (card vanishes immediately, restored on Undo) or deferred (card stays until the timer fires)?

## Credible first step

Build one small toast-with-Undo timer helper and route all three destructive handlers through it — hold the API call and the client-side removal behind a ~5s dismissible toast instead of firing both synchronously on click. Verified call sites: frontend/src/pages/News.tsx (not_interested button lines 296-305 + the signal() closure at line 48 that POSTs logNewsEvent), frontend/src/pages/Notes.tsx (remove() lines 36-40 → deleteBriefNote, button lines 99-103), frontend/src/pages/Brief.tsx (remove() lines 83-85 → deleteBriefNote, button lines 144-145). CORRECTION to the input wedge, which named only News.tsx lines 296-305 + the line-48 closure: the merged family (FR11 note-delete confirm + Harden HA10 "note delete needs a beat") also lives in Notes.tsx AND inline in Brief.tsx — both confirmed to call deleteBriefNote immediately — so the steelmanned move spans three call sites across two surfaces, not one.

## Dependencies

frontend/src/pages/News.tsx signal() + not_interested handler; frontend/src/pages/Notes.tsx remove(); frontend/src/pages/Brief.tsx remove(); api.logNewsEvent and api.deleteBriefNote client methods (unchanged, just deferred); a small toast/timer helper (none exists in frontend/src/components today — verified no delete-guard component). No backend change.

## Explicitly out of scope (revisit later)

No change to the For You ranker, the -8 weight, the 14-day decay, or button placement (the FR10 objection is explicit: only the timing changes). No server-side soft-delete or tombstone rows — keep it a client-side hold-then-fire window. Not a modal confirm dialog (that adds a tap every time); the beat is a passive undoable toast, not a gate.

## Identity/positioning note

none — tethered.
