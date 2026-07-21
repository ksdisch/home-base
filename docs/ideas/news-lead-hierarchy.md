# Lead story vs. the field — News gets a front page

**Status:** Idea — not committed. Added by `/brainstorm` (Delight mode) on 2026-07-20.

_On News, promote the first item to a real lead — a larger `text-lede` headline with `p-5` breathing room and the meta on its own line — while the rest stay the compact field, so the eye lands on a front-page story first instead of skating a `divide-y` wall of identically-weighted headlines. Ships with the two type tokens (`text-lede`, `text-meta`) it needs, which the rest of the app can then inherit._

## Premise

Today the News feed (`frontend/src/pages/News.tsx` L302-406) renders every article through one `feed.items.map` at identical weight: a `text-xs text-muted` meta row, a `font-medium text-ink` headline, and a repeated action row — all inside a single `divide-y divide-stone-200 rounded-2xl border bg-white/60` container. There is no lead-vs-minor distinction, so a major story and a trivial one look exactly alike and the eye has nowhere to land. This promotes `items[0]` to a lead treatment — a larger headline on its own generous card, meta lifted to its own line — while the tail keeps today's compact row. The feed gets a front page instead of a spreadsheet, and the change is carried by two reusable size tokens rather than magic numbers.

**Why now:** News is the flat surface the Delight brainstorm used as its worked example, and "no hierarchy between a lead story and a minor one" was the single most concrete complaint. The change is small and demoable — one split in the existing map plus two Tailwind `fontSize` tokens — and it salvages the useful residue of a fuller type-scale idea the gate killed as too abstract on its own.

## The bet

That a single focal point makes the morning News read *faster*, not slower — a front page is quicker to triage than a wall of equals — so hierarchy pays for itself against the fast-glance assumption (A1) while honoring that the calm look is intentional and the fix is hierarchy, not loudness (A3). A veteran of this app nods the first morning their eye actually lands somewhere. The risk the bet accepts: on the For You tab the "lead" is only ever "the current #1," so the treatment must not imply an editorial certainty the ranker doesn't have.

## Decisions / open questions

1) Does the lead treatment apply on every tab, or only on category tabs where "top" is chronological/authoritative — and is a plain "the current #1" honest enough on For You, or does it need a quieter lead than a category's? 2) One lead, or a lead + a two-up second tier before the compact field? 3) Should the lead ever carry a first-line-of-digest deck, or stay headline-only to protect the glance? 4) Does the same lead pattern belong on Today's topic items, or is News the only feed with a meaningful "top"?

## Credible first step

In `News.tsx`, split the `feed.items` render so index 0 renders a new `<LeadCard>` (headline at the new `text-lede`, `p-5`, meta on its own line above) and indices 1+ keep today's compact row inside the existing `divide-y` container. Add `fontSize` tokens `lede` and `meta` to `frontend/tailwind.config.js` so the sizes are shared tokens, not one-offs. One sitting for the visible win; the tokens are then reusable on Today and anywhere meta appears.

## Dependencies

`frontend/src/pages/News.tsx` (the `feed.items.map` at L302-406); `frontend/tailwind.config.js` (`theme.extend.fontSize`, currently absent). No backend, no API, no new data — pure presentation over the items already fetched. Pairs with [[semantic-source-color-system]] (the two compose into one "News front page" pass).

## Explicitly out of scope (revisit later)

No thumbnails or imagery (content is text-only; A5). No new ranking or "why this is the lead" logic — the lead is just render order. Not the full abstract four-step type scale (the gate killed that as hollow on its own); this ships only the two tokens the lead actually needs. No change to the action row or the card container beyond the index-0 branch.

## Identity/positioning note

none — tethered. Same calm palette and card family; one headline gets size and air.
