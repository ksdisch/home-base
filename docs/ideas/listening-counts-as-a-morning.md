# Listening counts as a morning

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-08-12.
**Note:** Pairs with `uncounted-morning-visit-replay` (Harden): same certifying metric, different hole — audio-link mornings vs offline app reads.

_Log a `phone-audio` visit when the delivered tap-to-play link is opened, so the fastest morning path — buzz, tap, listen on the walk — stops being invisible to `mornings_phone`, the number certifying v1 on ~08-19._

## Premise

PR #183 made the iMessage a text plus a tap-to-play link, and `sweeps/deliver_brief.py::audio_link()` (line 146) points it at `{base_url}/api/brief/audio?date=<day>` — the raw MP3 endpoint. But `mornings_phone` is counted only from tailnet-sourced POSTs to `/api/brief/visit`, which exactly one thing fires: the `useEffect` at `frontend/src/pages/Brief.tsx:459`. So the shipped happy path records nothing, and Kyle either pays a small daily tax of opening the app afterwards "so it counts", or doesn't — and the ~08-19 verdict grades a habit it cannot see. The email's HTML link already lands on the Today page and is already counted; the audio tap is the one hole, and it is the fast one. `get_brief_audio` (`backend/app/api/brief.py:231-259`) is a bare `FileResponse` with no `request` parameter, `visit_source.py` is a small well-factored bucket module, and `brief_visits.source` is free-text `TEXT` with no CHECK constraint (`backend/app/store/schema.py:131-137`) — so this is additive with no migration.

**Why now:** The tap link shipped at HEAD (`d447174`, PR #183) — the invisible path is brand new and about to be the dominant morning. The extended v1 verdict lands ~2026-08-19: every unlogged day between now and then is a day of the certification window graded blind, and none of them can be recovered later, because there is no server-side trace of a tap that was never recorded. Assumption #5 is the direct hit: HabitStrip's `PHONE_TITLE` tooltip (`frontend/src/components/HabitStrip.tsx:17`) states "Distinct days a tailnet (phone) client opened Today" — a claim the code keeps only by ignoring the delivery path Home Base itself sends every morning.

## The bet

The bet: the tap-to-play link is a real morning path Kyle actually uses, and counting it is a measurement fix rather than metric-gaming six days before the verdict. A veteran of this project reacts to the second half — "you are widening the number that certifies v1, mid-certification-window, in the week it gets graded." The answer that has to hold: the widening is forward-only (no `phone-audio` row can exist before ship, so every prior week's `mornings_phone` is byte-identical), the new reads land in their own bucket so the mix stays inspectable in `SELECT DISTINCT day, source`, and D12's supply-first rule already refuses to pass a week that lacks readable mornings. If Kyle would rather grade the window on the narrow number, the widen is one constant — but the row must still be written, or the data to re-grade on afterwards never exists.

## Decisions / open questions

- Kyle's call, and the merge should gate on it: widening `mornings_phone` inside the certification window. The row-write and the counting-widen are separable — ship the write unconditionally (it is pure measurement), and let Kyle say yes/no on flipping `PHONE_MORNING_SOURCES` before ~08-19. Recommendation: ship both, because the point of the fix is that the invisible mornings were real.
- Discriminator: `Sec-Fetch-Dest: document` alone, or OR'd with a `&from=msg` marker on `audio_link()`? The SPA's `<audio src>` sends `Sec-Fetch-Dest: audio`, never `document`, so the header separates a tap from the in-app player with no double count — but Sec-Fetch-* is a browser-version dependency (Safari 16.4+), and the metric certifying v1 should not rest on it alone. Recommendation: both, OR'd. The marker is fully in-repo, every message is regenerated daily, and the header keeps links already sitting in the Messages thread counting.
- iOS issues multiple 206 Range GETs per playback (verified in M6, noted at `frontend/public/sw.js:97-99`), so one tap can be several requests. `brief_habit_weeks` counts distinct DAYS so duplicates cannot inflate the metric — but recommendation: record only when `Range` is absent or starts at byte 0, so the table stays readable.
- Should a tap on an archived day's link (`?date=` older than today) count as today's morning? Recommendation: yes — `record_brief_visit` already stamps the LOCAL today regardless of which day is served, matching `/brief/visit`, which counts any Today load. State it in the bucket docstring rather than leaving it implicit.
- `HabitStrip.tsx:17`'s `PHONE_TITLE` says "opened Today" — false the moment audio taps count. Rewrite it in the same PR; assumption #5 is the whole reason this idea exists.
- The service worker passes `?date=` URLs straight through (`sw.js:92` — `if (url.search) return;`), so an online tap always reaches the server. Confirmed, not an open question — but it is the property the whole idea rests on, so a regression there silently re-blinds the metric.

## Credible first step

Five small seams, one sitting: (1) `backend/app/visit_source.py` — add `PHONE_AUDIO = "phone-audio"` plus an exported `PHONE_MORNING_SOURCES = {PHONE, PHONE_AUDIO}`, documented in the module's existing bucket list. (2) `backend/app/api/brief.py::get_brief_audio` (line 232) — add `request: Request` (`Request` is already imported at line 25) and, when `source_from_request(request) == PHONE` **and** the request looks like a tap rather than the in-app player, call `record_brief_visit(source=PHONE_AUDIO)` best-effort. (3) `backend/app/store/db.py:335` — `if r["source"] == PHONE` becomes `in PHONE_MORNING_SOURCES`. (4) `backend/app/mirror.py:105` — `if PHONE in sources` becomes a set intersection with the same constant; leave either reader narrow and the Mirror and the strip will disagree about the same week. (5) `sweeps/deliver_brief.py::audio_link` (line 146) — append the tap marker. Tests extend the existing harnesses: `backend/tests/test_visit_source.py`, `backend/tests/test_deliver_brief.py`, and `backend/tests/test_brief_api.py`.

## Dependencies

None blocking. `brief_visits.source` is already free-text `TEXT` with no CHECK constraint, so no schema bump and no migration entry. `base_url` must be set in the delivery config for the marker path — it already is, since #183 ships a working link. `Request` is already imported in `api/brief.py`. Untouched by the moonshot-lane freeze (D7): zero new LLM surface, zero new acting surface. Should land before ~08-19 to be worth anything, which makes it a same-week merge, not a queued item.

## Explicitly out of scope (revisit later)

Email-attachment listens: the MP3 travels as an attachment, Mail plays it locally, and no request ever reaches the server — that path stays invisible and the docstring must say so rather than imply full coverage. Genuinely offline taps (airplane mode) are likewise unobservable. No change to the ≥5-mornings / ≥3-notes bars, to D12's supply-first extension rule, or to the verdict date. No user-agent sniffing to split phone-from-desktop-over-tailnet — the v14 caveat's over-count stands. No retroactive backfill of taps that happened before this ships; inventing them would be exactly the fabrication `visit_source.py` exists to prevent. No new endpoint, no analytics, no session tracking.

## Identity/positioning note

none

## What it changes

`mornings_phone` starts reflecting the morning path Home Base actually delivers on, in both places it is read — the Today HabitStrip and the Mirror's "you showed up N of the last 14 mornings (M on your phone)" sentence. The daily tax disappears: listening on the walk is a counted morning, so opening the app "so it counts" stops being a thing. The `brief_visits` table gains a separable third reader-bucket, which means the ~08-19 re-grade can be run on either the narrow or the widened number and the difference is visible rather than assumed. No schema migration, no new endpoint, no new LLM surface, no change to the ≥5/≥3 bars.
