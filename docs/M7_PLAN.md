# M7 Plan — News mode (the Google-News-style second mode)

_Status: 🔄 **Phase 1 shipped 2026-07-18, PR #58** · Phases 2–4 planned.
Approved by Kyle 2026-07-18 after a recon-backed interview (live Google News structure +
Yahoo comparison + Google's published For-You mechanics); the three architecture forks
below were decided by Kyle from an explicit menu. Planning/building ahead of the M0
verdict (~07-19) is the **fifth deliberate override** of that gate, in writing, same as
M1–M3/M6 — M7's Phase 1 adds **zero new LLM surface** (pure RSS, $0/day), so it can't
muddy the grading. Renumbered from the working "M6 — news" label after M6 — mobile
shipped first (PRs #55/#56)._

## What this is

A **second mode** for the news portion of Home Base, sitting beside the custom morning
brief (Mode A, Today): a general-news page emulating Google News — standard categories,
real linkable articles, and (Phase 3) a **For You** feed learned from Kyle's behavior
inside this mode only. For You also acts as a **scout for Mode A** (Phase 4): when the
profile notices a persistent interest not in `sweeps/topics.json`, it suggests adding it
to the morning brief, one click, dismiss-remembered. The two modes stay distinct by
construction — the ranker never reads `topics.json`; overlap only happens when clicks
earn it.

Recon that shaped the layout (2026-07-17, live): Google News = one horizontal tab bar
(`For you | Top | Local | U.S. | World | Business | Technology | …`), text-dense cards
with source + relative time, story clusters with multi-outlet perspectives (deliberately
cut from v1 — dedup covers the practical need), and a Local section geolocated to Lake
County, IL.

## The decided forks (don't relitigate)

### 1. Sourcing — Google News public RSS, not LLM sweeps (Kyle, 2026-07-18)
Mode B is browsable *articles*, not synthesized briefs — dozens per category, live,
with real links. Google News publishes free per-section RSS (`/rss/headlines/section/
topic/<SECTION>`), per-geo feeds, and per-search-term feeds (`/rss/search?q=…` — Phase
3's beyond-the-categories candidate source). $0/day, no keys, effectively live. Known
quirks handled in `app/news.py`: `" - Source"` title suffixes, Google-redirect links
(kept — they open the original), no images (UI is text-first, like Google's own
density). LLM-sweeps-per-category (cost, daily cadence, unreliable links) and the
hybrid (LLM ranking pass) were declined; if Phase 4's keyword extraction proves too
dumb, a tiny tagging pass on clicked headlines is the known, deferred upgrade path.

### 2. Local — Chicago / Lake County, IL (Kyle, 2026-07-18)
Two merged geo feeds (Chicago + Lake County), deduped by item id. Config-file
category roster at `sweeps/news_categories.json` — same pattern as `topics.json`:
reorder/hide/re-point by editing JSON, `NEWS_CATEGORIES_FILE` override for tests.

### 3. For You signals — clicks + category visits + explicit feedback; no seeding (Kyle, 2026-07-18)
The Google-published recipe at single-user scale: article clicks (+3), "More like
this" (+5), "Not interested" (−8), category visits (+1), exponential decay with a
~2-week half-life. **No warm-start from Mode A data** (notes, chat, `topics.json`) —
Kyle explicitly wants the modes distinct; cold start shows Top stories with a
"still learning you" note until ~20 events exist.

## Phases (each its own PR)

- [x] **Phase 1 — News shell** ✅ built 2026-07-18: `sweeps/news_categories.json`
      (Top · Local · U.S. · World · Business · Technology · Science · Health · Sports ·
      Entertainment) · `app/news.py` (stdlib-only RSS fetch/parse/normalize, sha1(link)[:12]
      ids matching the brief's id shape) · `news_feed_cache` store table (schema v7,
      ~15-min TTL; failed refresh serves the expired payload marked `stale`, no cache =
      honest 502) · `GET /api/news/categories` + `GET /api/news/{slug}` · `/news` page
      with the horizontal category tab bar (`?cat=` deep-links), text-first cards opening
      at the source · desktop nav + mobile More entries (morning-loop tabs untouched) ·
      13 backend tests (fixture RSS through an injected fake fetcher — never the network)
      + 5 page tests.
- [x] **Phase 2 — Signals** ✅ built 2026-07-18 (PR # recorded on merge): `news_events`
      table (schema v8 — item events snapshot headline/source/url because cache payloads
      roll over; deliberately not `activity` rows) · `POST /api/news/events` (click ·
      visit · more_like · not_interested; invalid events 400 and write nothing) ·
      page wiring: visit signal per tab open, click-through logging, More-like-this
      (once, acknowledged) / Not-interested (logs + hides the card) · all signals
      fire-and-forget — reading the news never breaks on a logging hiccup · 9 backend
      + 4 page tests.
- [ ] **Phase 3 — For You**: decaying interest profile from `news_events` → candidate
      pool (cached category feeds + per-term search RSS) → interest × freshness ranking,
      already-clicked and not-interested penalties, title-similarity dedup · For You tab
      first in the bar · cold-start state.
- [ ] **Phase 4 — Topic scout**: persistent high-scoring profile terms not covered by
      `sweeps/topics.json` → suggestion cards in For You → one-click add via the existing
      custom-topics path (next 06:00 sweep picks it up) · dismissals remembered.

## Evidence — Phase 1

- Backend: `backend/tests/test_news_api.py` — 13/13 green (config-order roster, broken
  config degrades to no categories, unknown slug 404, " - Source" suffix → source field,
  RFC-822 pubDate → UTC ISO, newest-first with undated last, malformed item skipped not
  fatal, multi-feed Local merge dedupes by link, TTL cache = one fetch per window,
  expired refetch, failed-refresh-serves-stale, no-cache 502, unparseable-XML 502).
- Frontend: `frontend/src/pages/News.test.tsx` — 5/5 green (tabs + articles at source,
  tab switching, stale banner, section error survives tabs, empty-config state);
  `make typecheck` clean.
- Live smoke against real Google News RSS (PR #58): all 10 categories 200 with fresh
  articles — Local returned actual ABC7 Chicago stories — and `fetched_at` stable across
  repeat requests (cache hit).
