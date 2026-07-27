# Archive search — 'where did I read that?' over every brief + note

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-07-26.

_A zero-LLM GET /api/brief/search?q= that walks data/sweeps/*/<topic>.json (headline, digest, why_it_matters) plus brief_notes newest-first with plain case-insensitive substring matching, capped ~50 hits, surfaced as a search box on the in-flight archive index page, each hit deep-linking to /brief?date=<day>._

## Premise

Kyle can find a half-remembered item across the whole growing history from his phone, so the archive and notes stop being write-only and start paying back.

**Why now:** Pure assumption-2 read path (deterministic file walk, no LLM) and assumption-6 phone-first (find a half-remembered item one-handed). It naturally extends the exact branch in flight — feat/brief-archive-nav — so it ships where the archive work already lives.

## The bet

The bet: the archive is only worth building if the corpus is findable, and it isn't — the just-landed archive index (commit c0d8455) made briefs browsable but not searchable. What convinces a veteran: no search exists anywhere over Kyle's own corpus (grep-confirmed — News-mode's term feeds query Google, not his history), the corpus grows by 8 files a day forever, and one endpoint simultaneously raises the value of the archive, the notes page, and every past and future morning.

## Decisions / open questions

(1) Search notes and briefs in one blended list or two labeled groups? (2) Response cap 50 right? (3) Does the endpoint belong on the archive page only, or also as a global header affordance later?

## Credible first step

Add get_brief_search beside get_brief_archive in /Users/kyledisch/Projects/home-base/backend/app/api/brief.py (line 486; glob data/sweeps/*/ newest-first, substring over item fields + the existing list_brief_notes, cap ~50); add a search input at the top of /Users/kyledisch/Projects/home-base/frontend/src/pages/BriefIndex.tsx linking each hit to the existing ?date= route.

## Dependencies

data/sweeps/*/<topic>.json glob, list_brief_notes, backend/app/api/brief.py (beside get_brief_archive), frontend/src/pages/BriefIndex.tsx — extends the in-flight feat/brief-archive-nav surface.

## Explicitly out of scope (revisit later)

No fuzzy/semantic search, no LLM, no index/store — a plain deterministic file walk; latency is acceptable at current corpus size and revisitable when it is not.

## Identity/positioning note

none — tethered.
