# The habit strip counts mornings that never happened

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-08-12.

_Add `briefs_available` — renderable sweep days per week, counted from `sweep_dates()` — to the habit payload, and let the strip, the streak, and the Mirror's sentence read against mornings the stack actually served instead of a flat 7._

## Premise

The v1 habit bar (≥5 mornings/week) is graded against a denominator nobody checks. `BriefHabitWeek.mornings` is a raw distinct-visit-day count and `HabitStrip` compares it to a bare `MORNINGS_TARGET = 5`, with no notion of whether five mornings were even servable. The disk says that matters now: five days in `data/sweeps/` hold only `.raw.txt` — 07-24, 07-31, 08-01, 08-07, 08-08 — two of them a consecutive pair inside the extended measurement window. On those mornings there was nothing new to open, yet the strip scores them as Kyle not showing up and `consecutiveOnTarget` breaks his run for the stack's own outages. D12/F8 already rules that a week with <5 readable mornings extends the window rather than failing the habit — but that supply check exists only in prose; nothing computes it. This makes it a field, a bucket, and a comparison, using data the same router already loads.

**Why now:** Hard deadline: the extended v1 verdict lands ~08-19, and the moonshot-lane freeze plus the Agent Gate park (D7) are all downstream of it. The classification D12 requires — supply failure (extends) vs. habit failure (fails) — is currently uncomputable, so the verdict either gets read off the dishonest number or gets reconstructed by hand from a folder listing on the day. Week 1 is exactly at 5 readable and the next known outage pair is due 08-14/15, so the honest and dishonest readings are about to diverge by more than a rounding error. Landing this before 08-14 means the verdict window is instrumented while it is still being measured, rather than annotated after the fact.

## The bet

The one thing that must be true: `sweep_dates()`'s renderability bar is a faithful proxy for "a brief was servable that morning" — and it is, because it is the identical `_has_renderable_content` gate `latest_sweep_date` uses to decide what Today serves, so a day it counts is a day the page could render. Everything else follows mechanically. What makes a veteran of this project react: the ~08-19 verdict — three weeks and two extensions into the project's central question — is about to be read off a number that silently converts the sweep's own quota-wall outages into evidence the reader stopped showing up, on the exact assumption (5: no surface states a guarantee the code doesn't keep) that PR #182 was just written to defend. And the margin is gone: bucketed against the live `data/sweeps/`, graded week 1 (08-03) has exactly **5** readable mornings — sitting precisely on the bar — while week 2 (08-10) stands at 3-of-3-elapsed with the recurring Fri+Sat quota wall due 08-14/15, inside the window.

## Decisions / open questions

- Which number the supply check gates. D12 names `mornings_phone` as the certifying number, but `HabitStrip` grades `mornings`. Recommendation: do NOT move the criterion — report `briefs_available` beside both and let the strip render the classification honestly. Which number certifies v1 is explicitly Kyle's call at the verdict (stated in `models.py:1099`, `db.py:283`, and D12); this change must not pre-empt it.
- Streak semantics on a supply-starved week. Recommendation: skip it — neither extends nor breaks the run — matching D12's "extends the window, never a habit failure". The alternative (break, as today) is exactly the behavior this exists to kill.
- Partial current week. Recommendation: `briefs_available` counts renderable days so far and never extrapolates to 7 — a 3-day-elapsed week reads "3 of 3 served", not "3 of 7". Same honesty rule as the Mirror's insufficient-signal state.
- Servable vs. good. 08-09 rendered only 2 of 8 topics and still counts as available, so supply reads better than it felt. Recommendation: accept it and say so in the field's docstring — `briefs_available` measures that a brief was servable, not that it was complete; thin-day quality already belongs to `runs_summary`'s `thin` flag.
- Weeks with no day folders at all (before the first sweep, 2026-07-13). They read 0 and are already filtered out of the prior-weeks line by the `mornings > 0 || notes > 0` guard at `HabitStrip.tsx:127`. Verified safe: nothing prunes `data/sweeps/` (no `rmtree`/retention anywhere), so a 0 always means a real outage, never lost history.

## Credible first step

Backend, one sitting: in `get_brief_habit` (`backend/app/api/brief.py:405`) bucket `sweep_dates(settings.sweeps_dir)` — already imported at line 82 — by the same local-Monday rule `brief_habit_weeks` uses (`backend/app/store/db.py:332`, `d - timedelta(days=d.weekday())`), and stamp the count onto each week; add `briefs_available: int = 0` to `BriefHabitWeek` (`backend/app/models.py:1099`) beside `mornings_phone`. Keep the bucketing in the router, not the store, so `app.store.db` stays filesystem-free. Frontend: mirror the optional field in `frontend/src/api/types.ts:1022`, then in `frontend/src/components/HabitStrip.tsx` grade `targetHit` (line 132) against `Math.min(MORNINGS_TARGET, briefs_available)`, make `consecutiveOnTarget` (line 37) skip a supply-starved week instead of breaking on it, and add one copy clause to the line at 153 plus the `/Nb` figure to the prior-weeks recap at 181. Same sitting, same seam: `build_mirror` (`backend/app/mirror.py:70`) already receives `settings`, so its "You showed up {mornings} of the last {WINDOW_DAYS} mornings" (line 155) reads against served mornings too, with `briefs_available` added to `BriefMirror` (`models.py:847`). Tests land in the three files that already exist: `backend/tests/test_brief_habit.py`, `backend/tests/test_brief_mirror.py`, `frontend/src/components/HabitStrip.test.tsx`.

## Dependencies

None blocking. Everything needed exists and was verified at HEAD d447174: `sweep_dates` (`sweeps.py:111`) already imported into `brief.py:82`; `settings.sweeps_dir` (`settings.py:43`); `brief_habit_weeks`' local-Monday bucketing (`db.py:332`); `build_mirror` already takes `settings` (`mirror.py:70`). No schema migration, no new table, no new endpoint, no LLM surface — so no gate conversation and no conflict with the moonshot-lane freeze (this is a QuickWin). `data/sweeps/` is gitignored user data, so the live counts are verified by hand at review, not by a fixture. Timing dependency only: must land before the ~08-19 re-grade, ideally before the 08-14/15 quota wall.

## Explicitly out of scope (revisit later)

Moving which number certifies v1 (`mornings` → `mornings_phone`) — Kyle's call at the verdict. Any fix to the supply side itself: sweep retries, the weekly quota wall, failed-topic cost ledgering. Back-classifying pre-attribution visit rows. `isBestWeek` (a marker, not a bar — leave it comparing raw counts). Any new table, column, or schema migration. A supply-*quality* grade for thin days. Touching `brief_habit_weeks`' SQL or making the store layer read the filesystem.

## Identity/positioning note

none — tethered. This is assumption-5 honesty work on an existing readout: no new surface, no new data source, no new capability, nothing about what Home Base IS changes.

## What it changes

The habit readout stops blaming the reader for the stack's outages. Concretely: (1) `/api/brief/habit` gains a supply figure per week, so D12's two-step classification — readable mornings counted first, <5 readable + `mornings_phone` <5 = supply failure that extends the window, never a habit failure — becomes computable rather than prose; (2) the strip's target, copy, and streak all read against supply, so an all-outage week neither scores as absence nor snaps a run; (3) the Mirror's weekly sentence stops asserting a 7-morning denominator it did not supply. The ~08-19 verdict becomes a glance at the strip instead of a manual folder listing, and the number Kyle rules on is one the code can defend.
