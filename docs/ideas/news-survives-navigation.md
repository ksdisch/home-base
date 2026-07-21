# News forgets where you were

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-20.

_Leaving News to note something on Today and coming back snaps the tab to For You, resets the scroll to the top, re-fetches the feed, and un-hides every card you dismissed — every single loop._

## Premise

Today already survives navigation: `components/BriefShell.tsx` hoists the brief payload and the audio element above `<Routes>` so a Today→News→Today hop can't tear them down. News is the un-shipped sibling — all of its state (selected category tab, scroll position, hidden/liked sets) is local to the `News.tsx` component, so React Router remounts it from scratch on every return. Kyle pays the full re-orient tax on the loop's most natural gesture. This ports the proven survive-navigation pattern to News.

**Why now:** M6 made the phone primary and post-M7 promoted News to a thumb-reachable tab, so the daily loop now bounces Today↔News every morning. With Today already surviving the hop, News's reset is the conspicuous asymmetry — the same fix, one surface over.

## The bet

That the single biggest repeated friction in the loop is News's per-mount reset (assumption **A4** — News does NOT survive navigation), and the fix is porting a shipped pattern, not inventing one. A veteran winces in recognition because Today was fixed this exact way (`BriefShell`) and News was left behind.

## Decisions / open questions

Hoist via a `NewsShell` context rendered above `<Routes>` (mirroring `BriefShell`) vs. a module-level ref vs. `sessionStorage`? Restore scroll before paint (a layout effect) to avoid a visible jump. **Reconcile the restored hidden/liked sets against the fresh fetch** so a since-removed article doesn't stay ghost-hidden and a newly-arrived one isn't wrongly suppressed (the No-Smoothing critic's flagged side-effect). Persist across a full app restart (`localStorage`) or only within a session (in-memory / `sessionStorage`)?

## Credible first step

In `frontend/src/pages/News.tsx`, initialize the selected category from `sessionStorage` and write it on every tab change (~2 lines) so at minimum the tab survives the hop. Then add scroll-position restore, then the hidden/liked sets with the reconcile-against-fetch rule. If it grows, lift into a `NewsShell` beside `components/BriefShell.tsx`, wired in `frontend/src/App.tsx` above `<Routes>`.

## Dependencies

`frontend/src/pages/News.tsx`; optionally a new `components/NewsShell.tsx` + a wire-in in `frontend/src/App.tsx`; no backend change. `BriefShell.tsx` is the reference implementation.

## Explicitly out of scope (revisit later)

No change to the For You ranker or the signal events; the re-fetch itself stays (honest — stale/offline banners still fire, A5); scroll restore is best-effort/approximate, not pixel-perfect; the M6 offline SW path is untouched.

## Identity/positioning note

none — tethered.
