# Stranded at the bottom of the feed

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-20.

_After thumbing through 30–40 News cards one-handed, there's no one-tap route back to the top — Kyle either long-scrolls back up or re-taps the News tab, which remounts the page and wipes his position entirely._

## Premise

The News feed is a single long scroll with no return affordance. When Kyle reaches the bottom of a category or For You, getting back up means a manual re-scroll or tapping News again — and that tap remounts the component, resetting the tab, scroll, and hidden cards (the very loss the `news-survives-navigation` idea fixes). A floating, thumb-reachable "back to top" button is the standard escape from a one-way descent. It composes with survive-navigation: scroll-restore brings Kyle back where he was; jump-to-top lets him leave the bottom on his own terms.

**Why now:** post-M7 News is a primary phone tab with genuinely long feeds; the only "up" today is a manual re-scroll or a state-wiping remount.

## The bet

That the bottom of a long feed is a real one-handed dead-end (assumption **A2**) and a floating FAB is the cheap, standard fix. Honest scope (the Invented-Pain critic): this bites on the *longer* News sessions, not literally every loop — a smaller, cleaner win than the survive-navigation or card-hierarchy fixes.

## Decisions / open questions

Scroll threshold before it appears (~400px feels right). Keep the appearance minimal (a quiet fade) to honor the calm soul — no bouncing. Does it also belong on the Today brief? Probably not — Today already has the sticky jump-to-topic chips.

## Credible first step

In `frontend/src/pages/News.tsx`, a local `scroll` listener toggling a piece of local state, rendering a single ≥44px circular button pinned `bottom-20 right-4` (above the mobile tab bar, in the thumb zone) that calls `window.scrollTo({ top: 0, behavior: 'smooth' })` and fades out near the top.

## Dependencies

`frontend/src/pages/News.tsx` only; no API, no new route, no shared state.

## Explicitly out of scope (revisit later)

No jump-to-top on Today (the sticky topic chips already serve that); no scroll-progress indicator or reading-position bar.

## Identity/positioning note

none — tethered.
