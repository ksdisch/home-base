# Master Plan — Home Base

_The **one document** that shows the whole plan and where it stands. The detailed per-phase/
per-milestone plans stay where they are (linked below); this page is the unified progress view
so nobody has to click through a dozen docs to see the state of the project._

> ## 🔄 This is a LIVING document — the maintenance contract
> **Any session that starts, finishes, or reshapes a piece of the plan MUST update this file
> in the same commit/PR as the work**: tick the checkbox, adjust the status column, move the
> card on the Kanban board below, and touch the "Last updated" line. Adding a brand-new
> plan/milestone doc? Add it to the checklist, the board, and the doc map here.
> The rule that enforces this lives in `CLAUDE.md` → "Master plan upkeep".

**Last updated:** 2026-07-15 · main @ `335da9a` (PR #40)

---

## Where we are, in one paragraph

The repo has two arcs. **Arc 1 — Learning Hub** (the original SPEC build order, Phases 1–5,
plus extension Phases 6–7): **fully shipped**, including the SM-2 spaced-repetition core and
the first two Course-pipeline milestones. **Arc 2 — Home Base** (kickoff 2026-07-13: the
morning-brief evolution): **M1 and M2 are shipped**; **M0's sweep-quality grading week is the
only thing in flight** (Kyle grades daily through ~2026-07-19), and its go/no-go verdict gates
**M3 (hands-off automation)** — the next big build. Later course-epic milestones (M3–M5) and
the kickoff's deferred list are parked, not scheduled.

---

## Kanban

```mermaid
kanban
  done[✅ Done]
    lh15[LH Phases 1–5 — SPEC build order<br/>(catalog · quiz player · progress · review queue · custom topics)]
    lh6[LH Phase 6 — SM-2 SR core + daily study plan + reflections journal]
    lh7[Courses M1 — course sidecars, read+track API, Courses UI, /build-course]
    lh7m2[Courses M2 — course quizzes in the quiz player + per-course SM-2]
    hbm1[HB M1 — the brief page (Today route, /api/brief, visit log) · PR 36]
    hbm2[HB M2 — full 8-topic roster + inline notes + Your-learning strip · PRs 38-39]
  doing[🔄 In progress]
    hbm0[HB M0 — sweep-quality grading week<br/>Kyle grades daily through ~2026-07-19<br/>Day-0: A− / A / A · 7-15 full-roster run clean]
  decide[⏸️ Awaiting decision]
    hbm3gate[HB M3 go/no-go — rides on M0's verdict (Kyle, ~2026-07-19)]
  next[⬜ Up next (once unblocked)]
    hbm3[HB M3 — hands-off: scheduled sweeps (launchd), dedup vs history, cost guardrails]
  later[🧊 Later / parked]
    cm3[Courses M3 — multi-agent generation at depth + rubrics]
    cm4[Courses M4 — NotebookLM enrichment in-flow]
    cm5[Courses M5 — authoring loop in the hub]
    fcui[Course flashcard review UI (spec'd in Courses M2, not shipped)]
    defer[Kickoff-deferred: mobile · ESPN · audio brief · auto-courses · alerts · chat-with-brief]
```

_If the board above doesn't render in your viewer, the checklists below carry the same truth —
the board is a convenience view, the checklists are the record._

---

## Arc 1 — Learning Hub (SPEC build order + extensions) — ✅ COMPLETE

The original product: a NotebookLM learning dashboard (see [`SPEC.md`](../SPEC.md)).
Phases 1–5 were the SPEC build order; 6–7 extended it.

| # | Milestone | Status | Plan doc | Evidence |
|---|-----------|:------:|----------|----------|
| 1 | Catalog + Home + Topic detail (read-only sidecar ingest) | ✅ shipped | [PHASE1_PLAN](PHASE1_PLAN.md) | June 2026 scaffold; parser anti-fabrication guards |
| 2 | In-hub quiz player (offline oracle, answer-key-free sessions) | ✅ shipped | [PHASE2_PLAN](PHASE2_PLAN.md) | `app/quiz/*`, `/api/quiz/*`, QuizPlayer UI |
| 3 | Progress dashboard (trends, streaks, shaky material) | ✅ shipped | [PHASE3_PLAN](PHASE3_PLAN.md) | `store/progress.py`, Progress page w/ inline-SVG sparklines |
| 4 | Mastery decay + "Review next" queue | ✅ shipped | [PHASE4_PLAN](PHASE4_PLAN.md) | `store/mastery.py`, `GET /api/review`, home badges |
| 5 | Custom (non-NotebookLM) topics on home | ✅ shipped | [PHASE5_PLAN](PHASE5_PLAN.md) | `/api/custom-topics` CRUD + "Custom" home section |
| 6 | SM-2 per-item scheduler + daily study plan + reflections journal | ✅ shipped | [PHASE6_PLAN](PHASE6_PLAN.md) | `store/scheduler.py`, `study/planner.py`, `GET /api/study-plan`, Plan page |
| 7 | Courses M1 — course-pipeline vertical slice | ✅ shipped | [PHASE7_PLAN](PHASE7_PLAN.md) | `app/courses/*`, `/api/courses`, Courses UI, `/build-course` |
| 7-M2 | Courses M2 — course quizzes in the player + per-course SM-2 | ✅ shipped | [PHASE7_M2_PLAN](PHASE7_M2_PLAN.md) | `7f2db03`; `course:<slug>` namespace, notebook aggregates filtered |

Also closed in this arc: the **bug-hunt audit** — all 11 low-severity findings resolved
(PRs #21–#31, [`docs/bug-hunt/`](bug-hunt/)).

**Open remainder from the course epic's M2 spec** (deliberately not shipped with 7-M2):
- [ ] Flashcard **review UI** (flashcards render inline on Course detail; a dedicated review
      surface was spec'd in [COURSE_PIPELINE_SPEC](COURSE_PIPELINE_SPEC.md) M2 and remains open)

---

## Arc 2 — Home Base (morning brief) — 🔄 IN FLIGHT

The current arc: evolve the hub into Kyle's daily home base — self-updating morning brief +
inline notes, learning riding along. Contract: [`KICKOFF-home-base.md`](KICKOFF-home-base.md).

- [ ] 🔄 **M0 — Sweep quality week** ([grades log](M0-sweep-grades.md)) — _the only in-flight item_
  - [x] Sweep engine: per-topic prompts + `make sweep` runner (PR #34)
  - [x] Day-0 source-verified audit: AI **A−** · fantasy **A** · market **A** (PR #35)
  - [x] JSON pipeline refit: prompts emit strict JSON → validated render (with M1, PR #36)
  - [x] First full-roster 8-topic production sweep verified clean, incl. cloud-session run (2026-07-15, PR #40)
  - [ ] **Kyle's daily A–F grades through ~2026-07-19** ← _the live task; pilots gate the verdict_
  - [ ] **Go/no-go verdict** on the 3 pilot topics → unlocks M3 (kill criteria: persistent misses/slop)
- [x] **M1 — The brief page** — ✅ shipped 2026-07-13, PR #36 ([plan](M1_PLAN.md); deliberate Day-0 override of the M0 gate)
      _Today route at `/` renders stored sweeps · `GET /api/brief` · visit log (habit metric) · old home → "Learning" tab_
- [x] **M2 — Full roster + notes** — ✅ shipped 2026-07-14, PRs #38 + #39 ([plan](M2_PLAN.md); second deliberate override)
      _`sweeps/topics.json` roster (8 topics, pause flags) · read-time item ids · inline notes (`brief_notes` v5, `/notes` page) · "Your learning" strip_
- [ ] ⏸️ **M3 — Hands-off** — _blocked on the M0 verdict (Kyle's call, ~2026-07-19)_
      _Scheduled sweeps (launchd on-wake catch-up) · dedup vs history · cost guardrails · curation polish_

**v1 success criteria to check ~3 weeks in** (from the kickoff): ≥5 mornings/week habit (visit
log) · significant events reach Kyle here first · foraging → ~zero · ≥3 notes/week attach.

---

## Parked / deferred (not scheduled — do not build without a decision)

- **Course epic M3–M5** ([roadmap](COURSE_PIPELINE_SPEC.md#roadmap-milestones)): multi-agent
  generation at depth + rubrics → NotebookLM enrichment in-flow → in-hub authoring loop.
- **Kickoff-deferred v1 outs**: mobile access · ESPN league integration · audio brief ·
  auto-courses from news items · breaking-news alerts · public writing · chat-with-the-brief.
- **BACKLOG parked ideas** ([BACKLOG.md](../BACKLOG.md)): study-planner subagent (superseded by
  Phase 6), learner-profile doc, "Generate from hub" button, hosted phone access.

---

## Doc map (the detailed plans this page summarizes)

| Doc | What it holds |
|---|---|
| [`SPEC.md`](../SPEC.md) | Arc-1 product spec (Learning Hub) |
| [`KICKOFF-home-base.md`](KICKOFF-home-base.md) | Arc-2 contract: brief, scope, risks, milestones |
| [`PHASE1..7_PLAN.md`, `PHASE7_M2_PLAN.md`](.) | Per-phase build plans (Arc 1) |
| [`COURSE_PIPELINE_SPEC.md`](COURSE_PIPELINE_SPEC.md) | Course epic vision + M1–M5 roadmap |
| [`M1_PLAN.md`](M1_PLAN.md) / [`M2_PLAN.md`](M2_PLAN.md) | Home Base milestone plans (record decided design forks — don't relitigate) |
| [`M0-sweep-grades.md`](M0-sweep-grades.md) | The grading week's durable evidence + running verdict |
| [`../BACKLOG.md`](../BACKLOG.md) | Parking lot for uncommitted ideas |
