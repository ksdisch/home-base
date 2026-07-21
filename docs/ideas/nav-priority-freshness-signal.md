# Seven tabs, no signal which one matters this morning

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-20. **Flagged: STRETCH / interaction-model reframe.**

_The nav is seven equal desktop links (a five-slot mobile bar) with no weight hierarchy and no "something new here" indicator, so every open is a micro-decision — "which tab?" — whose answer is almost always Today._

## Premise

Kyle's real daily loop is Today + News (+ Notes to capture); Plan, Courses, and Progress are opened maybe weekly. But the nav renders all seven at identical weight, and nothing signals whether this morning's brief or fresh News has actually landed. Two composable moves give the nav the priority + freshness signal it lacks, using only data already on the payloads:

1. **(static) Priority hierarchy** — split the nav into a primary daily-loop cluster (Today · News · Notes) at full weight and a muted "reference shelf" (Learning · Plan · Courses · Progress): a `gap` split + a muted Tailwind color in `App.tsx`, no new route.
2. **(dynamic) Freshness dot** — a pure-CSS dot on Today (and News) driven by comparing `brief.date` / news item `published_at` (both already present) against a `localStorage` last-seen timestamp, cleared the moment the tab is opened. No badge counts, no notification system, no backend.

**Why now:** this is Kyle's explicitly #1-named friction ("seven equal top-nav items with no priority signal and no unread/new indicator"), and the data both halves need is already on the API responses.

## The bet

That surfacing hierarchy and freshness removes the "which tab?" decision without adding chrome or relabeling anything (assumptions **A1** + **A3** — Kyle is fluent, so the fix is hierarchy, not new labels). This is the run's one deliberate stretch: a bigger interaction-model change than the S–M friction removals.

## Decisions / open questions

**Flagged bigger bet — get Kyle's eyes first.** The Soul-Keeper flags the static cluster split as a real **information-architecture identity shift** (flat peers → a daily-loop vs reference-shelf model) — worth confirming before committing to the two-cluster shape. The dynamic dot has honest caveats: `localStorage` is per-device, so the dot won't agree across Kyle's phone and desktop; and "clear on open" can mark-seen on an incidental tap-through. Which half ships first? Does the mobile tab bar (Learning currently in a primary slot) get reordered, or stay?

## Credible first step

The lower-risk half: the **Today freshness dot** alone — in `frontend/src/App.tsx`, compare `brief.date` to `localStorage.getItem('lastSeenBrief')`, render a 2px accent ring/dot on the Today `NavLink` + mobile tab, and clear it (write the date) when the tab is opened. One sitting, no backend. Judge the feel before touching nav *structure* (the cluster split is the identity-shift half).

## Dependencies

`frontend/src/App.tsx` (both the desktop header nav and the mobile tab bar); `brief.date` (already on the brief payload) and news item `published_at` (already present); `localStorage`; no backend change.

## Explicitly out of scope (revisit later)

No badge counts or numeric unread indicators; no notification system; no backend-tracked "unread" state; no reordering the mobile tabs in v0.

## Identity/positioning note

**STRETCH.** The static cluster split changes what the nav says the app *is* — from seven flat peers to a daily-loop core plus a reference shelf. That IA shift is the flagged bigger bet; confirm before committing. The freshness dot on its own is tethered.
