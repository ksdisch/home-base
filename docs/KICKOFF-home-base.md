# Kickoff Brief — Home Base
*Created 2026-07-13 · approved 2026-07-13 · status: scoped · repo: `ksdisch/home-base` (renamed from `learning-hub` at kickoff)*

> ⚠️ marks assumptions approved by default at kickoff — challengeable anytime.

## One-liner
Evolve the Learning Hub into Kyle's daily home base: a self-updating morning briefing across his topics (AI, his teams, fantasy, news) that he can annotate with his own takes — with the existing learning machinery riding along.

## Why now / the problem
Kyle wants to stay informed on AI/LLMs, his teams, fantasy strategy, and general news — but has **no system**, just a YouTube algorithm, scattered apps (CBS Sports, Google News), and Reddit scanning he can't find time for. This isn't replacing beloved feeds; it's **filling a vacuum with time-compression**: Morning-Brew-Daily-style curation, but across *his* topic roster, in a page he owns. Secondary driver: the hub today is homework you visit deliberately; a daily brief makes it somewhere you *start*.

## Who it's for
Kyle, privately, on his laptop. ⚠️ *Assumed: no public audience, ever, for v1 — notes are for you, not readers.*

## What success looks like (3 weeks in)
- **v1 done means:**
  1. **Habit (keystone):** opened ≥5 mornings/week, unforced — measured by a visit log in the hub, not vibes.
  2. **Catches what matters:** significant events in your topics ≤1/week reach you from elsewhere first.
  3. **Foraging → ~zero:** Google News wandering and Reddit fantasy-scanning effectively stop.
  4. **It compounds:** ≥3 notes/takes/questions per week attach to brief items, or spawn a deeper dive in the hub.
- **Would be amazing (later):** audio version of the brief · mobile access · ESPN league integration · auto-courses from news items · chat-with-the-brief.
- **Explicitly NOT trying to:** be a publishing platform, a breaking-news pager, or comprehensive journalism.

## Scope
**In (v1):**
- Briefing homepage: per-topic sections, N items each with headline · 2–4 sentence digest · why-it-matters · source links · "as of" timestamp.
- Topic roster with seasonality: add / pause / quiet topics via a config file ⚠️ *(assumed: config file first, curation UI later)*.
- Inline notes: a take/question attached to any brief item, stored in the hub's SQLite, browsable per topic. ⚠️ *Assumed: flat notes, no threads/expansion in v1.*
- "Your learning" section on the home page: due reviews / active courses from the existing hub. ⚠️ *Assumed: surfacing only — no deeper news↔learning bridge in v1.*
- Visit logging (for the habit metric).
- Sweep engine: per-topic Claude agent runs with web search → structured JSON → hub ingest. Manual/on-demand first, scheduled later.

**Out / deferred:** mobile access · ESPN league integration · audio brief · auto-generated courses/notebooks · breaking-news alerts · public writing · in-app chat.

## Shape
Evolution of this repo — renamed `learning-hub` → `home-base` at kickoff (2026-07-13); **not a new project.** The brief becomes the home route of the existing React frontend; sweeps land via the existing FastAPI/SQLite backend. Rationale: the learning pillar, custom-topics infra, store, and Claude tooling already live here; laptop-only means no deployment mismatch. The current hub home moves to a "Learning" tab/section — **"Learning Hub" survives as the name of that section.**

## Inputs & data
- No loyal sources to integrate — sweeps are **search-driven** per topic, seeded with known tastes (Late Round-style fantasy strategy, Morning Brew-style market/tech lean, team-specific queries).
- Topic roster v1: AI/LLMs · Chiefs · Celtics · Indiana (FB+BB) · Kansas (BB) · St. Louis Blues · fantasy football (seasonal) · general news (market/tech lean).
- Risk: web-search recency/quality per niche (e.g., college hoops off-season) — exactly what Milestone 0 tests.

## Integrations & dependencies
Claude Code agent runs with WebSearch (the sweep) · launchd or scheduled agents (later, for automation) · existing hub stack. No new external APIs, accounts, or scraping in v1.

## Constraints
- No deadline; milestones sized ADHD-small — each independently shippable.
- **Open cost question:** daily multi-topic sweeps burn tokens (order cents–$2/day depending on depth/model, more in football season). Needs a lane decision (subscription-authed local runs vs API) and a monthly comfort number.

## Riskiest assumptions & unknowns
1. **Brief quality/trust (the killer):** an autonomous sweep can reliably catch what matters per topic without hallucinated or stale slop, every morning. Two bad mornings and the habit dies. — *Cheap test: Milestone 0 runs sweeps manually for a week with zero UI; grade each morning's output A–F in 2 minutes against reality (and against Morning Brew Daily for overlap days). No UI work until it passes.*
2. **Staleness plumbing:** laptop-only means sweeps must run on wake/login without thinking about it. — *Test in M3; mitigated meanwhile by honest "as of" stamps and a one-command manual refresh.*
3. **Better-than-generic:** the cross-topic page beats subscribing to three newsletters. — *M0 comparison grades cover this.*
4. **Novelty wear-off:** residual risk; measured by the visit log, accepted.

## Open questions
- Sweep lane + monthly cost tolerance (see Constraints).
- Long-term scheduler: local launchd vs cloud agents committing to the repo.
- Season windows: hardcoded dates or manual pause flags? *(v1: manual flags is fine)*
- Note → custom-topic/notebook bridge shape (deferred with auto-courses).

## Phased plan
### Milestone 0 — De-risk: sweep quality week *(no UI)*
- Per-topic sweep prompt + tiny runner (`make sweep`) → JSON/markdown to a folder.
- Run daily ~5–7 days on 3 pilot topics (AI/LLMs · fantasy football · market/tech news); 2-min A–F grade each morning.
- Go/no-go + tuned prompts. Kill criteria: persistent misses or slop on pilot topics → rethink source strategy before building anything.
### Milestone 1 — Thinnest slice: the brief page
- New home route rendering stored sweeps: topic sections, digests, sources, as-of stamp; manual refresh command; visit log. Existing hub home → "Learning" tab.
### Milestone 2 — Full roster + notes
- All topics with pause/seasonal flags via config; inline notes on items, browsable per topic; "Your learning" section on home.
### Milestone 3 — Hands-off
- Scheduled sweeps (launchd on-wake catch-up), dedup vs history, cost guardrails, curation polish.

## Tech stack
Existing hub stack — FastAPI + React/TS + SQLite — plus Claude-agent sweeps with WebSearch and launchd for scheduling. Rationale: zero new surface area; every piece is already proven in this repo.
