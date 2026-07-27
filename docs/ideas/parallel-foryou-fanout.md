# Kill the cold-cache morning spinner on News — parallelize the For You fan-out

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-07-26.

_Wraps the serial for-loop in get_news_foryou (backend/app/api/news.py, lines 108-118) — 11 categories, ~17 feeds plus up to 3 search feeds, each a 10s-timeout fetch behind a 15-min TTL that guarantees a cold cache every 06:15 morning — in a concurrent.futures.ThreadPoolExecutor(max_workers=6), so wall time is the slowest single feed (~1-2s) instead of the sum (10-40s). One sitting._

## Premise

The News tab loads in a second or two on the first cold morning open instead of stalling on a 10-40s spinner, so the habit's second surface stops punishing the daily visit.

**Why now:** Assumption 6 (phone-first): News is the second surface of the morning habit, and its cold cache is guaranteed at 06:15 by the 15-min TTL, so the very first daily tap is the slow one — precisely the moment the habit is most fragile.

## The bet

The bet: the first News tap of the day is a 10-40s spinner nobody profiled, and it's pure sum-vs-max latency. What lands with a veteran: the serial loop at news.py:108 has literally never been questioned (every shipped News change was UI or ranking), the fetch is embarrassingly parallel and independent, and NewsFetcher is already an injectable dependency so the existing fake-fetcher tests pass unchanged — one new test with a deliberately slow fake feed asserts the response returns in ~one-feed time, not the sum. Maximum felt latency cut per line changed.

## Decisions / open questions

(1) max_workers=6 right for ~17-20 feeds on the Mac? (2) Apply the same executor to the per-category route in the same PR (same pattern, same tests)?

## Credible first step

In /Users/kyledisch/Projects/home-base/backend/app/api/news.py, wrap the get_news_foryou fetch loop (lines 108-118) — and the per-category route's loop ~line 188 — in a ThreadPoolExecutor(max_workers=6), collecting results and skipping NewsFeedError exactly as the current except clauses do (lines 111, 118).

## Dependencies

backend/app/api/news.py get_news_foryou loop + per-category loop, concurrent.futures.ThreadPoolExecutor, the injectable NewsFetcher seam.

## Explicitly out of scope (revisit later)

No async rewrite, no cache-warming cron, no feed-level timeout changes — only the loop's concurrency.

## Identity/positioning note

none — tethered.
