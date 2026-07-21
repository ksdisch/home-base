# For You never says what to do first

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-20.

_The cold-start banner honestly says "still learning you… top stories" but offers no next action — and after the ranker warms up, For You looks identical whether it's truly personalized or silently on the top-stories fallback._

## Premise

For You is the default landing on every News mount, so its cold-start "now what?" beat is the default re-entry state. The existing `feed.learning` Banner surfaces the *state* ("X of 20 signals") but never the *action*, and once past the threshold the banner vanishes and nothing tells Kyle whether his feedback ever mattered. Two small, honest copy moves fix both: a directional line in the cold-start banner, and (optionally) a persistent one-line personalization read-out. Zero new chrome — it deepens the existing honesty invariant (**A5**).

**Why now:** the For You ranker, the 20-signal threshold, and the cold-start banner all already exist; this is copy on branches that already render.

## The bet

That the cheapest honest fix is copy that turns a status banner into a directed nudge and makes personalization legible, without adding a control (assumptions **A5** + **A1**). Honest caveat (the Invented-Pain critic): for a fluent power user the "what do I do first" half is a mild trust/legibility itch more than a hard stall — the persistent "it's working" half is the sharper of the two.

## Decisions / open questions

Is the persistent "Personalized · N signals" / "Learning · 6 of 20" line worth its sliver of chrome (A1), or is the cold-start sentence enough on its own? Where does the persistent line sit (a `text-xs` line under the category tab strip)? Exact threshold copy. Should the nudge name the *fastest* warming action specifically ("More like this")?

## Credible first step

In `frontend/src/pages/News.tsx`, append one directional sentence inside the existing `feed.learning` Banner — e.g. "Tap 'More like this' on 3–4 stories to tune your feed." It clears at the same `≥20` threshold that already flips the banner away. The signal count is already tracked client-side.

## Dependencies

`frontend/src/pages/News.tsx`; the cold-start branch + signal-count state already exist; no API change.

## Explicitly out of scope (revisit later)

No onboarding flow or modal; no change to the ranker, the decay profile, or the threshold; no new setting or toggle.

## Identity/positioning note

none — tethered (it strengthens the calm-and-honest soul rather than shifting it).
