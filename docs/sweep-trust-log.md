# Sweep trust log — the accuracy re-grade record

M0's graded week was an inspection, not a warranty: nothing after it re-checks sweep
accuracy unless a re-grade lands here (`docs/ideas/sweep-trust-warranty.md`). **Cadence:
monthly**, or after any sweep-prompt or model change. Each entry is a
`## YYYY-MM-DD — <verdict>` heading; `GET /api/brief/habit` serves the newest heading
date as `last_graded`, and the Today habit strip shows it — flagging a stretch longer
than 30 days as "re-grade due". Letting this file go stale is itself the visible signal.

**How to re-grade** (~15 min, against the M0 rubric in
[`M0-sweep-grades.md`](M0-sweep-grades.md)): pick 2–3 topics from that morning's brief,
cross-search ~3 items each against their cited sources, grade A–F on the M0 bar (any
fabrication = automatic F; exclusion carries the same sourcing bar as inclusion — the
ai-llms lesson), then append a dated entry below with the grades and anything caught.

---

## 2026-07-19 — M0 close-out, verdict PASS (baseline entry)

The founding grade: a full week graded (Day-0 audit · blanket B+ 07-15 · source-verified
07-16→18 audit with ~30 cross-searches) — **zero fabricated items across the week**;
market/fantasy excellent; AI passed with a prompt tune
(`sweeps/prompts/ai-llms.md`: exclusion now carries the same sourcing bar as inclusion).
Full record: [`M0-sweep-grades.md`](M0-sweep-grades.md).
