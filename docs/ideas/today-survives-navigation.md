# Today doesn't survive you leaving it

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-19.

_Every Today→News→Notes→Today hop tears the whole page down and rebuilds it from a blank slate: pulse-skeleton flash, refetch of identical brief data, scroll reset, and the audio brief silently snapping back to 0:00 mid-walk._

## Premise

Home Base's core loop is a constant bounce — listen to the brief on a walk, tap into an item to note or ask, graze News, come back to Today — but React Router tears down and rebuilds the entire Today page on every return: skeleton flash, refetch, scroll reset, and worst of all the audio snapping back to 0:00. This lifts the brief payload and a single persistent audio element above the route mount so Today survives navigation the way the loop already assumes it does. The fix is pure frontend state-lifting inside the existing shell; the one nontrivial part — hoisting a live media element above the router — is exactly what the walk case demands.

**Why now:** M6 made the phone the primary surface and post-M7 promoted News to a thumb-reachable tab, so the core loop (listen on a walk → tap to note/ask → graze News → return) now bounces Today↔News↔Notes in one tap — turning the remount teardown into a per-hop, every-morning tax.

## The bet

That the papercut worth an App-layout refactor is the audio-reset-on-a-walk, not the load flash — the walk is the soul brief's named core-loop mode, so a live media element MUST outlive navigation. Targets no load-bearing assumption; it defends the core loop's continuity. A veteran flinches because surviving the router means hoisting a playing <audio> element above React Router's own mount model — the largest blast radius in the friction pool.

## Decisions / open questions

Persist via a React context/provider vs a module-level cache plus a portal for the audio element? Should the persistent audio keep playing while Kyle is on News/Notes (likely yes — that's the walk case) or pause on route change? How to invalidate the in-memory brief cache when a fresh sweep lands mid-session.

## Credible first step

In frontend/src/App.tsx, lift the brief payload and a single persistent <audio> element into a context/shell rendered above <Routes> (line 121) so React Router's unmount of <Route path="/" element={<Brief/>}> (line 123) can't destroy them; Brief.tsx (useEffect fetch lines 360-376, <audio> line 400) consumes the shared state instead of owning it. Repo-verified: no localStorage/sessionStorage/module cache exists anywhere in frontend/src and the audio element lives inside the route-scoped component, so the input's named files are correct.

## Dependencies

frontend/src/App.tsx, frontend/src/pages/Brief.tsx, api.briefWithMeta()/briefAudioUrl(); no backend change.

## Explicitly out of scope (revisit later)

No cross-day brief history/navigation (that is QU1's ?date= param); no change to the M6 offline SW cached-brief path; the player stays the bare <audio controls> — persistence only, not the chapter chips (FR4).

## Identity/positioning note

none — tethered.
