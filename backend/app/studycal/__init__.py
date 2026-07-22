"""Study Scheduler (v0) — opt-in Google Calendar study blocks for a learning path.

Behind a per-track opt-in flag, a deterministic session planner reads a path's incomplete steps + a
per-kind duration model, pulls the learner's free/busy, and proposes concrete time-blocks; on one
confirm the batch is written to a dedicated "Study" calendar and recorded in a removable ledger
(``app.store.study_blocks``). The calendar is reached through a ``CalendarPort`` seam so the whole
feature is testable against an in-memory fake; the real Google adapter is one isolated implementation.

Named ``studycal`` (study calendar), deliberately distinct from the unrelated ``app.study`` package
(the SM-2 interleaving *review* planner) and ``app.store.scheduler`` (the SM-2 spaced-repetition
scheduler) — this package only ever schedules calendar blocks for an opted-in track.
"""
