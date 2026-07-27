# The News re-scan tax — read stories look identical to unread

**Status:** Idea — not committed. Added by `/replenish` (Friction lane) on 2026-07-26.

_Play the already-logged click signal back into the feed so a return visit scans only what's new: category and For-You feed builders load recent click item_ids from the news_events log and stamp clicked:true on matching items (one set-membership pass), and News.tsx renders clicked items muted with a small ✓ — turning the second and third daily visit into 'what's new' instead of re-reading the same 30 headlines._

## Premise

A second or third News visit becomes a scan of only what's new instead of a re-read of the same headlines — the feed remembers what Kyle already opened.

**Why now:** The For-You ranker consumes clicks today; the read/unread distinction Kyle needs for repeat same-day visits was never surfaced, and repeat visits are exactly the 6:45am / lunch pattern.

## The bet

The bet: half the loop already exists and only the eyes-facing half is missing — the ranker eats Kyle's clicks but Kyle's own eyes never got the replay. What makes a project veteran react: News.tsx already fires signal('click', item) (verified line 366) into news_events with a stable id (sha1(link)[:12], news.py:184), foryou.py:125 ALREADY reads those click events by item_id — and the anchor is custom-styled so the browser's native :visited never applies, so a clicked headline returns pixel-identical to an unread one on a feed Kyle opens multiple times a day. Must be true: the click log has enough recent rows to matter and item ids are stable across refetches (they are — sha1 of the link).

## Decisions / open questions

(1) Lookback window for "read" (48h? 7 days?) so old clicks don't mute a genuinely re-newsworthy story. (2) Mute only, or also sink clicked items lower in For You (ranker already has the signal — is double-counting wrong)?

## Credible first step

In /Users/kyledisch/Projects/home-base/backend/app/news.py have the category/For-You feed builders load recent click item_ids from the news_events log (via the existing store read used by foryou.py) and stamp clicked:true; in /Users/kyledisch/Projects/home-base/frontend/src/pages/News.tsx render clicked items text-muted + ✓. Zero new storage.

## Dependencies

news_events click rows (stable sha1(link)[:12] ids), the store read foryou.py already uses, backend/app/news.py feed builders, frontend/src/pages/News.tsx card styles.

## Explicitly out of scope (revisit later)

No read-state sync beyond clicks (no scroll-into-view tracking), no per-item dismiss (exists already), no unread counts/badges.

## Identity/positioning note

none — tethered.
