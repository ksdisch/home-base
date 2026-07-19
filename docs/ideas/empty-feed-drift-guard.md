# The Feed That Went Quiet Without Saying So

**Status:** Idea — not committed. Added by `/brainstorm` (Harden mode) on 2026-07-19.

_A Google-News RSS template change that drops every <item> through parse_rss's title/link filter while the XML still parses cleanly makes get_category_items overwrite a good cache with an empty result at stale=False, so a category (or a whole For You feed) goes permanently, invisibly blank with nothing in any log._

## Premise

get_category_items today treats any successful XML parse as ground truth, overwriting the cache regardless of how many items survived the title/link filter. NewsFeedError fires only on fetch failure or unparseable XML; a document that parses to zero surviving items reads as 'genuinely nothing new' and caches at stale=False. When Google News or an outlet feed reshapes its item markup, a category can go permanently blank with no exception, no stale flag, and no log line. This guard compares the live item count against the existing cache before overwriting -- strictly zero-live-while-cache-nonempty serves stale and logs once.

**Why now:** Post-M7, News mode is live in production with For You as the default tab and 15-min per-category caching; the ~08-03 v1 check counts on significant events reaching Kyle HERE first, which a silently-blank category directly defeats. Feeds only drift further over time, so the risk compounds every month the frozen parser runs unattended -- and nothing currently watches the item count of a parse that succeeded.

## The bet

Bet: item-shape drift is a realistic, not exotic, failure -- providers reshape RSS templates without notice, and news.py already parses defensively for title-suffix stripping and missing <source>/<pubDate> because that drift is expected. This targets assumption 1 (trust sustains the habit) as it applies to Mode B: a category that silently reads 'nothing new' forever, indistinguishable from a genuinely quiet niche, erodes trust the same way a fabricated sweep would. The load-bearing thing that must be true: the existing stale-cache philosophy ('serve last-good rather than show wrong') is a real commitment, so NOT extending it to the zero-items-that-parsed case is an inconsistency, not a choice. Veteran flinch: the code looks correct and every test passes because zero surviving items IS a valid parse -- the bug only surfaces months later when Google moves the URL off <link>, and by then the '~08-03 events-reach-Kyle-here-first' promise is quietly already broken.

## Decisions / open questions

(1) Trip condition: strictly zero live items while cache non-empty (the steelman's choice -- avoids masking a legitimately quiet niche category) vs a small fewer-than-N floor (blunter, risks false positives). (2) For multi-feed categories (Local merges several feeds into `merged`), does the zero-check apply to the merged total or per-feed, so one dead feed among several doesn't trip the whole category? (3) How loud is 'log once' -- per-category-per-day dedup in the log, or a surfaced signal (news_events) so a persistently-drifted category becomes visible rather than only logged?

## Credible first step

In backend/app/news.py get_category_items (VERIFIED lines 168-200): after the parse_rss merge loop (lines 183-191) and before set_news_cache (line 199), if len(merged) == 0 while the already-fetched `cached` (line 179) holds a non-empty payload, return the cached items marked stale=True instead of overwriting, and log the anomaly once. Verifiable by feeding a valid-XML feed whose every <item> fails the line-126 `link.startswith("http")` filter and asserting the prior cache survives with stale=True. (Input's wedge location is correct; no correction needed.)

## Dependencies

backend/app/news.py alone -- get_category_items, parse_rss, get_news_cache/set_news_cache, NewsFeedError all live in one module, no cross-file reach. The 15-min cache TTL and news_events signal log already exist. No frontend change for v0: stale=True already renders on the News page.

## Explicitly out of scope (revisit later)

No change to parse_rss's per-item title/link filter (that filter is correct, not the bug). No proactive re-fetch, retry, or alerting beyond serve-stale + log-once. No auto-detection of WHICH markup element moved (that's a manual follow-up when the log fires). No Mode A sweep changes -- this is Mode B news only. Cross-lane: complements verified bug-hunt #3 (one dead feed freezes a category), which fixes fetch failure; this guards the parse-that-looks-like-success case.

## Identity/positioning note

none — tethered.
