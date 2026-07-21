# Dusk mode — a true low-light morning surface

**Status:** Idea — not committed. Added by `/brainstorm` (Delight mode) on 2026-07-20.

_Re-express Home Base's exact identity in low light — warm paper `#f7f6f3` becomes a warm near-black ground, `bg-white/60` cards become a barely-lifted charcoal, and the teal nudges up just enough to stay legible without glowing — driven by CSS variables + `prefers-color-scheme`, so a morning app read in a dark pre-dawn room stops flashing a bright field into your eyes._

## Premise

The app is `color-scheme: light` only (`frontend/src/index.css`), with base colors as raw hexes (`#f7f6f3` body, `bg-white/60` cards) and tokens `ink`/`muted`/`accent`. Home Base is a *morning* app, often read in the dark — phone in bed before dawn — where a bright field is a small assault. Dusk mode re-tints the exact same tokens through CSS variables under a `@media (prefers-color-scheme: dark)` block: the warm paper becomes a warm near-black, cards a charcoal that's barely lifted off the ground, the teal legibility-tuned rather than neon. It is not a redesign — nothing moves, no new chrome — just the same calm, honest surface expressed at the light level the morning actually happens at.

**Why now:** dark mode is the single biggest gap named in the Delight seed, and it rides the CSS-variable substrate the color-system idea ([[semantic-source-color-system]]) introduces — so the two sequence naturally (color tokens first, dusk second). The shared chrome (header `App.tsx` L88, mobile tab bar L43, both `bg-[#f7f6f3]/…`) is where dark mode lives or dies, and that identity surface is already centralized.

## The bet

That dark mode done as a re-tint of the same tokens — not a parallel design — keeps the calm, honest identity intact across both schemes (A6), and that the felt payoff is specific and real: a 6am phone-in-bed read that meets the room's light instead of searing it. It must not add latency (A1) — one CSS layer — and every honesty surface (staleness, `warning`, cold-start) must keep identical semantics in dark, so nothing becomes less legible or less truthful in the dark scheme. A veteran nods the first dark morning the app doesn't make them squint. The risk: a charcoal that's too flat loses the figure/ground an elevation pass would give, so the card lift must be tuned by eye.

## Decisions / open questions

1) Auto-only (follow `prefers-color-scheme`) for v0, or ship a manual toggle — and if a toggle, where does it live and does it persist? 2) How far up does the teal shift before it reads as a different accent — is there a single dark-scheme accent value that stays "the green"? 3) Do the `accent.soft` fills (active tabs, info Banners) need their own dark values to avoid muddiness? 4) Does the PWA `theme-color` meta need to track the scheme? 5) How do the semantic tints from [[semantic-source-color-system]] re-map in dark without losing their low-saturation calm?

## Credible first step

Move the base hexes (`#f7f6f3`, the card `white/60`, `ink`, `muted`, `accent`) into CSS variables in `frontend/src/index.css`; add a `@media (prefers-color-scheme: dark)` block redefining them; flip `color-scheme` to `light dark`. First slice = the shared chrome (header + mobile tab bar + body ground) reading correctly and calmly in dark; cards and the News/Today surfaces follow once the variable swap is proven. Verify against real staleness/warning states so honesty survives the scheme.

## Dependencies

`frontend/src/index.css` (`:root`, `color-scheme`, body bg, focus ring); `frontend/tailwind.config.js` (token→variable wiring); the shared chrome in `frontend/src/App.tsx` (header L88, tab bar L43); every `bg-white/60` / `bg-[#f7f6f3]/…` surface. Best sequenced after (or with) [[semantic-source-color-system]], which introduces the variable substrate. No backend.

## Explicitly out of scope (revisit later)

No third theme or user-tunable palette; no per-surface dark overrides beyond the token re-tint. No AMOLED-black or high-contrast variant. No scheduled/time-based switching in v0 (system preference only). Not a redesign of any layout — dark mode that moves things is out of scope by definition here.

## Identity/positioning note

none — tethered. The identity is deliberately preserved; dusk mode is the same Home Base at a different light level, and its whole discipline is that the calm and the honesty carry across both schemes.
