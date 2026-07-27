# Builder-Kyle vs reader-Kyle: the habit metric certifies the wrong person

**Status:** Idea — not committed. Added by `/replenish` (Premortem lane) on 2026-07-26.

_The ~08-03 v1 success check (≥5 mornings/week) reads brief_visits — and POST /api/brief/visit -> record_brief_visit() (backend/app/store/db.py:193) stores only (day, visited_at) with ZERO source attribution. So every localhost dev-server load, every Playwright smoke run, and every '8/8 clean' Claude verify pass during July's M0→M8-plus-four-moonshots build blitz counts as a 'morning visit'. The check passes on build exhaust; the Mirror's 'You this week' recaps a habit that may be pure verification traffic; and when the backlog finally runs dry and builder-Kyle stops opening the repo, the visits quietly collapse to zero with no early warning — the project having certified a reading habit that was actually a building habit the whole time. The verification culture that keeps this repo trustworthy is exactly what poisons the well: every clean verify IS a counted visit. The antibody: thread FastAPI's Request into the visit log, tag each visit by origin (phone = tailnet 100.x client vs mac-localhost vs known test/dev origin), and report phone-sourced distinct days as the honest habit number alongside the raw one — so the 08-03 check judges reader-Kyle, not the sum of both Kyles._

## Premise

The success criterion that decides whether Home Base is working starts measuring reader-Kyle instead of builder-Kyle-plus-the-robots — so the 08-03 verdict is honest, and the day the reading habit actually starts to fade, the phone-sourced number falls while the contaminated raw count would have hidden it.

**Why now:** The 08-03 check is the single gate that decides whether v1 succeeded, and it's weeks away — right at the moment the build blitz that generated all the localhost/verify traffic is winding down. Certify on contaminated data now and the wrong-bet (Kyle loved BUILDING Home Base, not USING it) gets stamped 'healthy habit' and rides uncorrected into the whole next year of decisions.

## The bet

That the real morning-reading number is materially lower than the raw brief_visits count once dev/verify traffic is stripped — i.e. that some meaningful fraction of the 'habit' the metric currently shows is build exhaust, not Kyle-on-his-phone. A project veteran should flinch here: this repo's whole trust story rests on that 08-03 number, and it's being computed from a table that can't tell a Playwright run from a Tuesday morning. If phone-sourced days come back nearly identical to raw, great — the bet was cheap and the metric is now trustworthy; if they diverge, the project just avoided declaring a dead habit alive.

## Decisions / open questions

(1) Can July's existing unattributed rows be partially back-classified (e.g. from server logs), or does the honest number simply start now? (2) Classification map: is tailnet-100.x = "phone" safe when Kyle sometimes reads on the desktop over tailnet? (3) Does the v1 criterion itself change to phone-sourced days, or report both and let Kyle judge?

## Credible first step

One sitting: thread FastAPI's Request into log_brief_visit in backend/app/api/brief.py (line 344), add a nullable source column to brief_visits at the next schema bump in backend/app/store/schema.py (line 125), classify each visit at write time (tailnet 100.x -> 'phone', 127.0.0.1/localhost -> 'mac-localhost', test/dev origins tagged), and make backend/app/mirror.py + the 08-03 check report phone-sourced distinct days as the honest number beside the raw count.

## Dependencies

POST /api/brief/visit + record_brief_visit (store/db.py), a nullable source column at the next schema bump (v13), backend/app/mirror.py, FastAPI Request client IP.

## Explicitly out of scope (revisit later)

No analytics platform, no session tracking, no user-agent fingerprinting beyond the coarse origin buckets — a single source tag per visit, nothing else.

## Identity/positioning note

none — tethered.
