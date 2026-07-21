# A color system, not a color — semantic + source tint

**Status:** Idea — not committed. Added by `/brainstorm` (Delight mode) on 2026-07-20.

_Grow the single muted-teal accent into a small system — `success/info/warn/danger` semantic tints at the same low saturation, plus a deterministic per-source tint (name-hash → one of ~6 desaturated hues at a fixed lightness/chroma) — so every News source line stops being identical `text-accent` gray-teal and starts signalling provenance at a glance, and the app's scattered `amber`/`text-red-600` one-offs collapse into one honest vocabulary._

## Premise

The palette today is one accent: `accent.DEFAULT #3f8f86` (+ `accent.soft #e6f0ee`), with warnings reaching for raw `amber` and the note error at `News.tsx` L378 using a bare `text-red-600`. Every News source renders identically as `text-accent` (`News.tsx` L309), so provenance is gray-on-gray. This introduces a token family in the same calm lightness/chroma envelope as the teal — semantic `success/info/warn/danger` for meaning, and a deterministic `source` tint computed from the source string — turning the source line into a parse-at-a-glance signal and giving warnings one consistent, honest color vocabulary instead of ad-hoc hexes.

**Why now:** "single accent color, no semantic/category color" and "the green source + time line repeats identically on every card" were both named complaints. The source line is one swap (`text-accent` → `sourceTint(item.source)`) from carrying signal, and the CSS-variable substrate this lays is exactly what Dusk mode ([[dusk-mode]]) needs next — so building color first de-risks dark mode.

## The bet

That color can add meaning and hierarchy without adding loudness (A3): provenance you feel before you read, and one honest warn/danger vocabulary — with every tint pinned to the teal's low-saturation envelope so nothing screams and no color ever implies "live" data (A2). The tint is text-only and computed from the string, so it costs nothing in assets (A4). A veteran nods when Reuters, The Verge, and a local outlet each read as themselves at a glance. The risk: too many hues turns calm into confetti, so the palette must stay small and desaturated.

## Decisions / open questions

1) How many source hues before it reads busy — ~6 buckets, or fewer with collisions accepted? 2) Is the source tint applied only to the source name, or also a hairline card accent (risk: louder)? 3) Do category tabs adopt the same tint so a category and its sources rhyme? 4) Should semantic tokens replace the existing `amber` Banner tone immediately, or coexist until every call site is migrated? 5) Fixed hand-picked hues vs. a hash into an OKLCH ramp for guaranteed even spacing?

## Credible first step

Add the token block to `frontend/tailwind.config.js` (semantic `success/info/warn/danger` + a small source ramp), ideally as CSS variables in `frontend/src/index.css` so Dusk mode can reuse them. Write a ~6-line `sourceTint(name)` helper (stable string-hash → one ramp class) beside `News.tsx`, and swap L309's `text-accent` → `sourceTint(item.source)` as the proof slice. One sitting proves the "gray breaks into provenance" moment before touching Today or the Banners.

## Dependencies

`frontend/tailwind.config.js` (`theme.extend.colors`); `frontend/src/index.css` (`:root` variables); `frontend/src/pages/News.tsx` L308-317 (source line + origin chip); `frontend/src/components/Banner.tsx` (the `amber`/accent tones, for later migration). No backend; source names already arrive on every `NewsItem`. Lays the variable substrate [[dusk-mode]] depends on.

## Explicitly out of scope (revisit later)

No per-category background fills or colored cards (that's loudness, not signal). No user-configurable palette. No imagery. The semantic-token migration of every existing `amber`/`red` call site can follow the first slice — v0 only needs the token layer + the News source tint proving the move. Not the type scale ([[news-lead-hierarchy]] carries the type side).

## Identity/positioning note

none — tethered. Every tint lives inside `#3f8f86`'s lightness/chroma envelope; the anchor green is preserved and remains the primary accent.
