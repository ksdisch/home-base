# The companion voice, not the system dialog

**Status:** Idea — not committed. Added by `/brainstorm` (Delight mode) on 2026-07-20.

_Give the calm `<Banner>` tones (`info`/`muted` — never `warning`) a thin `accent/40` left rule, so the honesty-copy that carries the app's most trust-sensitive moments — "Still learning you", "Showing saved articles", "Nothing here right now" — reads as the app speaking to you in its own margin, a patient companion admitting it's early, instead of a stock system alert. One edit to a shared component; every honesty surface inherits it._

## Premise

`frontend/src/components/Banner.tsx` is the single component behind every honest moment in the app — cold-start ("Still learning you", `News.tsx` L207), staleness ("Showing saved articles"), empty ("Nothing here right now"), "No sweeps yet" — via a three-tone `TONES` map (`warning`/`info`/`muted`). Today all three read as generic alert chrome. This gives only the *calm* tones (`info`/`muted`) a thin `accent/40` left rule (`border-l-2 pl-3`), reframing the app's admissions-of-limits as a companion voice in its own margin, while the `warning`/failure tone keeps its full-fill amber alarm untouched — so honesty about failure still shouts, but honesty about *learning* feels warm.

**Why now:** "no personality in empty/loading states" was a named complaint, and honesty is the product's defining feature — the moments where the app says "I'm still learning you" are exactly where a warmer voice earns trust. It's the highest look-to-effort change in the whole Delight set: one edit to a shared component, inherited everywhere.

## The bet

That the surfaces where the app is honest about its own limits (A2) are the ones that most reward a considered voice — a consistent margin-frame makes "still learning you" feel like a patient companion rather than an error — and that reframing the *calm* states while leaving the *failure* state loud keeps the honesty gradient intact (a stale-data warning must not get cozier). A veteran nods that the cold-start moment finally feels like the app talking to them. The risk: softening the wrong state (a real failure) would trade honesty for comfort, which is why `warning` is explicitly excluded.

## Decisions / open questions

1) Left rule only, or also a small leading glyph/mark for the companion tones? 2) Does the info tone used for *actionable* prompts (e.g. the scout "add to my brief" card) want the companion voice, or only the passive honesty states? 3) Should the rule use flat `accent/40`, or track the semantic token from [[semantic-source-color-system]] once it exists? 4) Any copy pass to match the visual voice, or purely the frame in v0?

## Credible first step

In `Banner.tsx`, add `border-l-2 border-accent/40 pl-3` (or equivalent) to the `info` and `muted` entries of the `TONES` map only; leave `warning` as its current full-fill amber. Every consumer inherits it with no call-site changes. Roughly fifteen minutes; verify against the real cold-start ("Still learning you") and stale ("Showing saved articles") states, and confirm a `warning` Banner still reads as an alarm.

## Dependencies

`frontend/src/components/Banner.tsx` (the `TONES` map). Every Banner consumer inherits automatically (`News.tsx`, `Home.tsx`, `Brief.tsx`, and others). No backend, no API, no new tokens (uses the existing `accent`).

## Explicitly out of scope (revisit later)

No change to the `warning`/failure tone (honesty about failure stays loud). No new Banner variants or a full copy rewrite in v0 — this is the visual voice-frame only. No motion. No per-surface custom Banners.

## Identity/positioning note

none — tethered. Reuses the existing component and accent; only the calm honesty states gain a margin voice.
