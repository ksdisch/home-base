# The News card has no front door

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-20.

_The headline is the primary action — it opens the article — but it's styled like body text, while three equal tiny buttons ("More like this / Not interested / Note") sit under it drawing the eye, so it's unclear what to tap or where the tap lands._

## Premise

On the phone the News headline's only "I'm a link" cue is `hover:text-accent`, which never fires on touch (assumption **A2**). Meanwhile three equal-weight `text-xs` buttons read as loud as — or louder than — the headline they serve, so the card looks like a three-option form rather than a story you open. This promotes the headline to the unmistakable primary tap and visually subordinates the two low-value feedback signals so they stop competing with it — **without burying them**, because burying the ranker signals behind an overflow would starve the For You profile (the No-Smoothing critic's flag).

**Why now:** notes-on-news and the destructive-tap undo toast both recently landed on this card, so the action row is now *three* equal buttons crowding the headline. The hierarchy debt is visible and compounding.

## The bet

That the card's primary action being invisible on the actual (touch) surface causes a per-card half-hesitation Kyle pays all through News triage, and the highest-leverage fix is making the existing affordance obvious (assumption **A2**), not adding anything new. A veteran winces because the headline IS a link and always was — just styled mute.

## Decisions / open questions

Headline promotion: `font-semibold` + a trailing `↗`/`ChevronRight` glyph + a full-height tap block (`block py-1`). For the feedback row, **subordinate** (lighter / smaller / right-aligned, still one-tap) rather than hide in an overflow `···` — pick subordinate to keep the ranker fed. Does the `↗` glyph read clearly as "opens the source"? Fold in the C5 tab-target hygiene here (`min-h-[44px] px-4` + `snap-x snap-mandatory` on the category pills) since it's the same file and the same thumb-target theme.

## Credible first step

In `frontend/src/pages/News.tsx`, the pure-styling headline promotion on the `<a>` element (weight + `↗` glyph + `block py-1`) — no behavior change, the `onClick` click-logger already exists. Then subordinate the two feedback buttons; then the category-pill `min-h-[44px]` + `snap-x` fold-in.

## Dependencies

`frontend/src/pages/News.tsx` only; no API. (Coordinate with the Delight `news-lead-hierarchy` idea — both reshape the `<article>`/headline; do them adjacent.)

## Explicitly out of scope (revisit later)

No swipe-gesture triage layer (considered and cut — poor gesture discoverability, conflicts with vertical scroll + the horizontal tab strip, and a bigger build than the hierarchy fix warrants); no change to what the buttons DO; the 5s undo toast stays.

## Identity/positioning note

none — tethered.
