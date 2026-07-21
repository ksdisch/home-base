# Content that arrives, not pops

**Status:** Idea — not committed. Added by `/brainstorm` (Delight mode) on 2026-07-20.

_Instead of the morning brief popping in fully-formed from a gray skeleton, Today's topic sections fade-and-rise in a fast top-down cascade (~40ms stagger, ~180ms each) so the day unfolds from the top you're already reading; the "Ask about this" answer does the same gentle settle so a reply lands after its 10-20s wait. A sub-250ms entrance that only decorates a paint which already happened — every card hit-testable at frame 0, `prefers-reduced-motion` honored — so it adds a felt arrival with zero real latency. The deliberate wildcard of the set._

## Premise

Today's first paint (`frontend/src/pages/Brief.tsx`, the stacked topic `<section>` list ~L304-330) swaps from three `h-40 animate-pulse` skeleton blocks straight to fully-formed content — a hard pop. The "Ask about this" answer (L238-256) likewise blinks in cold after a 10-20s "Thinking…". This adds a small, well-mannered entrance: content sections cascade in top-down as the day "unfolds" from where the eye already is, and the Ask answer settles (`translate-y-1 → 0`, opacity) so the payoff of asking is felt. Header and jump-chips stay instant; only content cards move; the whole settle is under ~250ms and every card is in the DOM and hit-testable at frame 0, so nothing is delayed.

**Why now:** opening the brief is the single most-repeated moment in the product, and it's currently a jump-cut. The motion primitives are cheap (CSS keyframes + `animation-delay`), and doing it with restraint establishes the bar for any future motion in the app.

## The bet

That a sub-250ms entrance which decorates an already-completed paint adds a genuine felt *arrival* at zero cost to the fast glance (A1) — the reduced-motion guard and the frame-0 hit-testability are what keep it honest and un-intrusive. This is the wildcard: the boldest delight in the set and the one a purist calls motion on a deliberately-still soul (the brainstorm's own Soul-Keeper flagged exactly this tension). It's kept on purpose — the line between *calm* and *inert* — on the bet that considered motion, tightly budgeted and reduced-motion-safe, reads as craft, not noise. A veteran nods the first morning the brief unfolds instead of snapping. The risk it accepts: any perceptible latency or jank would violate the spine, so the budget and guards are non-negotiable — if it can't be that restrained, it should be cut, not softened.

## Decisions / open questions

1) Cascade the topic sections only, or also the items within the first section (risk: too much motion)? 2) Is ~40ms stagger / ~180ms per card the right budget, or tighter? 3) Should the cascade fire on every mount, or only on a genuine cold load (NOT on the FR15 Today↔News↔Today return, which must not re-animate)? 4) Does the Ask-answer settle belong in this idea or ship independently? 5) Exact `prefers-reduced-motion` fallback — instant paint, or a single whole-list fade with no stagger?

## Credible first step

Add one `.brief-cascade` utility (opacity + small `translateY`, `motion-safe` only) with keyframes in `frontend/src/index.css`, and apply it with `style={{ animationDelay }}` on the topic-section map in `Brief.tsx`; gate it so it fires on a real first load, not the shell-preserved return. Separately, wrap the `{answer && …}` block in a mount-transition. One sitting; verify the total settle is under ~250ms, content is readable at frame 0, and reduced-motion users get the instant paint.

## Dependencies

`frontend/src/pages/Brief.tsx` (the topic-section map + the Ask answer block); `frontend/src/index.css` (keyframes); coordination with the FR15 `BriefShell` so a Today↔News↔Today return does not re-trigger the cascade. No backend, no API.

## Explicitly out of scope (revisit later)

No route-transition or page-level animations; no motion on News/Notes/Learning in v0. No skeleton→content morph or shared-element transition. No parallax, no springs — a single tightly-budgeted fade-and-rise only. Nothing that adds real latency or that runs for reduced-motion users.

## Identity/positioning note

stretch (the wildcard) — this pushes gently on the "calm/quiet, deliberately still" reading of the soul by introducing entrance motion. It stays tethered via a strict sub-250ms budget, `prefers-reduced-motion` support, and firing only on a genuine cold load; the claim is that considered restraint makes the app feel *alive*, not *busy*. If in practice it reads as noise, it should be cut rather than softened.
