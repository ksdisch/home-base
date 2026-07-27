# Every page except News opens at the previous page's scroll offset

**Status:** Idea — not committed. Added by `/replenish` (Friction lane) on 2026-07-26.

_Add a ~10-line ScrollReset inside AppChrome that scrolls to top on route change for every route except /news (whose own post-feed-load restore must not fight a top-flash), so finishing a long Today read at HabitStrip depth and tapping Notes/Learning lands at that page's top with its header and filters on screen — not pre-scrolled to a meaningless offset that costs a corrective flick on nearly every hop._

## Premise

Kyle's first gesture on almost every tab hop stops being a corrective scroll-to-top — pages open where they should, headers and filters visible.

**Why now:** F1 landed News's position-preservation and made every other tab's inherited-offset behavior the odd one out; the inverse default (a fresh page starts at its top) was never addressed and is felt on nearly every navigation.

## The bet

The bet: this is the highest-frequency papercut in the app — it fires on almost every tab tap, and the fix is the smallest possible diff. What makes a project veteran react: there is NO scroll reset anywhere (verified App.tsx has none; the only navigation window.scrollTo is News's own restore at News.tsx:137), and shipping F1 (news-survives-navigation) made the gap sharper by making News the ONLY tab that lands correctly — so the app-wide default is now visibly inconsistent with its one exception. Must be true: React Router preserves window scroll across route swaps by default (it does — no built-in scroll restoration here, which is exactly why News had to add its own).

## Decisions / open questions

(1) Any other route that should preserve scroll (the FR15 Today same-commit return already restores its own state — confirm no fight)? (2) Instant jump vs behavior:"instant" explicitness for iOS.

## Credible first step

In /Users/kyledisch/Projects/home-base/frontend/src/App.tsx add a ScrollReset component inside AppChrome: useEffect(() => { if (!pathname.startsWith('/news')) window.scrollTo(0, 0); }, [pathname]). One file; existing News.test.tsx restore tests guard the exception.

## Dependencies

frontend/src/App.tsx AppChrome, react-router pathname, News.tsx:137's existing restore.

## Explicitly out of scope (revisit later)

No per-page scroll memory beyond what already exists (News, Today) — this is only the reset-to-top default for fresh pages.

## Identity/positioning note

none — tethered.
