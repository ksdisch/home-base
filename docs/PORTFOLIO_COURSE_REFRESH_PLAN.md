# Research-Portfolio Course Refresh — Plan (2026-08-04)

_Planner: cloud Claude session (branch `claude/portfolio-course-update-plan-czwyjs`), decisions
confirmed with Kyle 2026-08-04. Implementer: a **local Opus 5 Claude Code session started in
`~/Projects/home-base`** (the course sidecar lives in gitignored `backend/data/courses/`, so
this cannot run in the cloud). The paste-ready handoff prompt is at the bottom of this doc._

## Goal

Fully regenerate the hub course **"Research Portfolio — Reproduce & Measure"** (slug
`research-portfolio`, level **advanced**, interview-defense framing) so it reflects the
portfolio's current state: **all eight projects**, the two-lane story, and the updates landed
since the course was authored — most notably `blind-cite`'s park-and-resolution (well-powered
M1 null, 2026-08-03), `mute-map` complete (M0–M4 + collateral close-out, 2026-07-29),
`hush-gauge`'s pre-committed nulls (G1/G2/G3 FAIL at all three scales), and the **research
papers for blind-cite and hush-gauge that Kyle is generating today (2026-08-04)**.

## Decisions (confirmed with Kyle — do not relitigate)

| Decision | Choice |
|---|---|
| **Project scope** | **All eight**: dim-stage, forge-gap, decay-pin, lossy-wall, ghost-patch, blind-cite, **mute-map** (new), **hush-gauge** (new). ("blind-site" in the request = `blind-cite`.) |
| **Approach** | **Full regeneration, updated in place** — same slug `research-portfolio`, same URL. Rebuild syllabus + all materials from current portfolio state. Progress was 0/11, nothing to preserve. |
| **Approval** | **Keep course-builder's syllabus gate** — propose the updated syllabus, one approval from Kyle, then author autonomously. |
| **Where it runs** | Locally on Kyle's Mac: session starts in `~/Projects/home-base`; portfolio repo at `~/Projects/portfolio`. |
| **Timing** | Only after Kyle has wrapped blind-cite + hush-gauge **and generated their research papers**. Pre-flight (below) verifies this; if the papers aren't found, stop and ask. |

## Corrections since this plan was written (verified 2026-08-05)

**Standing rule: where this plan's framing and a repo's `main` disagree, the repo's `main`
wins.** Both flagship projects moved after the plan was written; the Goal section above is
stale on both, and the portfolio *cards* are stale on both too (see the card-drift gate).

### blind-cite — the story REVERSED, and the paper is current

The "well-powered M1 null (2026-08-03)" named in the Goal is **WITHDRAWN**. The M1C extension
(PR #12, D24/D25 — **merged**) ran a pre-registered, power-sized extension to N=80 and found
DG at **both** surfaces: stark **3/80, Wilson 95% [1.3%, 10.5%]**; camouflaged **7/80,
[4.3%, 17.0%]**. The stark surface, measured 0/20 at M1, now has a lower bound above zero —
the measurement stands, the inference "DG ≈ 0" does not. On all ten DG answers the mechanical
faithfulness and citation proxies **both PASS (10/10, 10/10)**. Pre-flight item 3's "D11
does-v1-close-on-the-null" framing is superseded.

- **Paper: found, committed, and current** — `docs/paper/blind-cite-paper.md` on `main`
  (titled "…a null at N=20 did not survive a pre-registered extension to N=80"; it withdraws
  the "well-powered" claim explicitly). A plain-English rewrite and an interactive glossed
  HTML page also shipped (PR #19) and are usable as additional reading.
- **Teach the reversal as this project's centerpiece defense story** — "my own pre-registered
  escalation caught my null being underpowered" — not as a footnote.

### hush-gauge — v1 is COMPLETE; the gate ledger is final

M4 landed **2026-08-05** (PR #18) and is **the project's last measurement**: gateless by
design (D48), reports no verdict, and re-decides nothing. The Goal's "G1/G2/G3 FAIL at all
three scales" is true but no longer the whole ledger. Final state, all three scales:

| Gate | Outcome |
|---|---|
| G0 (battery dynamic range) | **PASS** ×3 |
| G1, G2 (detection, silent leak) | **FAIL** ×3 — pre-committed nulls; the probe reads the model *speaking* the secret, not holding it |
| G3 (causal ablation) | **FAIL** ×3 — and *not the same FAIL* at each scale; that difference is the finding |
| G4 (off-switch unification) | **NOT-RUN** ×3 — M3's Arm B was dropped by D38.4's own validation ladder, which is K5's pre-committed fallback and a passing outcome |

M4's own contribution: M2's non-nesting flag is answered — the edited layer set does **not**
behave like independently-acting parts, and what orders the effect is the late third's
presence, not the layer count. `docs/M0-RESULTS.md` … `docs/M4-RESULTS.md` are normative.

- **Paper: written but may be UNCOMMITTED.** As of 2026-08-05 `docs/paper/hush-gauge-paper.md`
  (plus five figures and a presenter pack) exists in the working tree as **untracked** files —
  not committed, not pushed, and with **no open PR**. `git ls-files`, GitHub, and `gh pr list`
  will all report it missing. **Before invoking pre-flight item 4's STOP, look at the working
  tree on disk.** If it is there, use it and tell Kyle it is uncommitted; only stop if the file
  is genuinely absent.

### Pre-flight additions (all three still apply)

- **(a) Pull ALL source repos** — the eight project repos and portfolio-prep, not just
  home-base and portfolio.
- **(b) Card-drift gate.** The portfolio cards for **blind-cite and hush-gauge are both known
  stale** as of 2026-08-05: blind-cite's card still says "well-powered null" (contradicting its
  own repo), and hush-gauge's card still carries M2 as a stats IOU with G4 "undecided" and no
  M3/M4 at all. Kyle has an outstanding re-carding task for exactly this. **If the cards still
  disagree with the repos when you run, do NOT propagate the cards** — pre-flight item 5's
  "cards are the source of truth" yields to the standing rule above. Note the drift, teach from
  the repos, and tell Kyle the re-carding hasn't landed.
- **(c) Verify each paper's *content*, not just its presence.** The blind-cite paper must state
  the M1C-corrected finding (if it says "well-powered null," STOP and ask). The hush-gauge paper
  must cover M0–M4 including G4 `NOT-RUN` — if it stops at M2 or M3, it predates M4 and Kyle
  should be asked whether to wait for the regenerated version.

### Mock-defense capstone additions

Drill the one-sentence AI-collaboration framing — the public `.claude/` tooling makes the
agent-driven workflow visible, so it must be Kyle's opening move ("I run an agent-driven
research loop; I make every design call and can defend every gate"). Add a cross-project
skeptic bank: why Wilson vs Newcombe and when each applies; why judge-free oracles; what would
have falsified each headline; "so what at 0.5B–3B — does any of it transfer?"; forge-gap's
injected-vs-natural gap; "mute-map and hush-gauge have no external anchor — why trust them?";
and for blind-cite specifically, "your null flipped — why should I trust the new number?"

## Pre-flight (implementer runs these checks before proposing a syllabus)

1. **Repos present locally.** `~/Projects/home-base` and `~/Projects/portfolio` exist and are
   up to date (`git pull` both). Locate the eight project repos on disk (likely
   `~/Projects/<slug>`; each portfolio card links its GitHub repo — clone any that are missing
   locally, read-only use).
2. **The fluency curriculum moved.** The original course drew on `LEARNING-ROADMAP.md`,
   `PRACTICE.md`, and the `learn/` guides — those moved to the **private
   `ksdisch/portfolio-prep`** repo on 2026-07-28 (portfolio `Decisions.md` D5). Find it locally
   (likely `~/Projects/portfolio-prep`) or clone it. Note: the learn guides cover the original
   six projects; **mute-map and hush-gauge likely have no learn guide** — author their material
   from the project cards, repos, and papers instead, and check portfolio-prep for anything
   newer.
3. **Wrap-up state is final.** Read each of `blind-cite` and `hush-gauge`'s current README +
   latest decisions to capture today's closing state (e.g. blind-cite's D11 "does v1 close on
   the null" call; hush-gauge's G4/M3 decision). The course must state the *actual* final
   status, whatever it is — including "deliberately left open".
4. **Research papers exist.** Find the generated research paper in each of the two repos (the
   `research-paper` skill opens a PR — the paper may be on an unmerged branch; check open PRs
   too). **If either paper can't be found, STOP and ask Kyle** — the whole point of today's
   refresh is to fold them in.
5. **Sweep for other drift.** Read `~/Projects/portfolio`'s `README.md`, `METHODOLOGY.md`,
   `GAPS-AND-NEXT.md`, `Decisions.md`, `docs/audit-2026-08-03.md`, and all eight
   `projects/*.md` cards. Diff mentally against the existing course (read the current
   `backend/data/courses/research-portfolio/course.json` + lessons before deleting anything) —
   every stale claim in the old course is a checklist item for the new one. Kyle flagged that
   *other* projects may have quietly moved since the course was generated; the cards +
   GAPS-AND-NEXT are the source of truth for per-project status.

## Course design constraints (the syllabus proposal must respect these; shape is otherwise the implementer's to propose)

- **Same identity:** slug `research-portfolio`, level `advanced`, interview-defense purpose —
  "defend every claim, number, and honesty caveat claim-by-claim", capped by a mock-defense
  capstone. State prerequisites explicitly (built/deeply read the eight repos; Python + basic
  probability).
- **Two-lane structure is now load-bearing.** The portfolio README frames eight repos in two
  lanes: **agent-reliability** (forge-gap, decay-pin, lossy-wall, ghost-patch, blind-cite) and
  **model-internals — the J-lens lineage** (dim-stage → mute-map → hush-gauge: build the
  instrument → map the phenomenon → run the audit). The refreshed course should teach that arc
  explicitly; the shared-spine module needs updating for it (the spine now includes the
  bit-for-bit instrument-validation discipline, not just the reproduce-and-measure loop).
- **Nulls as headlines.** Much of what's new is *null results* (dim-stage's pre-registered
  null, blind-cite's well-powered M1 null, hush-gauge's three nulls). The course's job is to
  make Kyle able to defend nulls as findings — objectives and quiz questions should target
  exactly the skeptic lines listed in `GAPS-AND-NEXT.md` per project.
- **Papers as reading.** Wire the two new research papers (and any existing per-project
  papers/reports) in as `reading` materials. Follow the course-builder guardrail: only include
  URLs that are real and stable (the public GitHub repos qualify); otherwise cite in `note`.
- **No invented facts or numbers.** Every claim, number, and date in lessons/quizzes must be
  traceable to a portfolio/repo/paper source read during pre-flight. When a source is
  ambiguous, quote its hedge rather than resolving it.
- **Size:** expect the course to grow (6 → 8 projects; old est. ~5h). Keep per-project depth
  roughly even between lanes; the capstone must cover all eight.

## Mechanics (per `.claude/skills/course-builder/SKILL.md` — read it in full before starting)

1. Run `/build-course` (or invoke the `course-builder` skill) with the topic + the constraints
   above; the interview should be near-zero since this doc pre-answers it.
2. Slug exists → the skill's `scaffold` will hit `FileExistsError`; choose **update the
   existing course in place**: skip scaffold, re-author all material files, then
   `… cli write --slug research-portfolio --from-file <manifest.json>` (validates + rolls back
   on failure). **Delete stale material files** the new manifest no longer references so the
   dir matches the manifest.
3. Syllabus gate: present the full modules → lessons → objectives → materials structure with
   objective↔assessment alignment; **wait for Kyle's approval before authoring**.
4. Author via the skill's per-module fan-out contract; validate; self-check quiz discipline
   (exactly one correct option, rationale on every option).
5. Verify live: `make dev` (or the running server), open `/courses/research-portfolio`,
   confirm the new module list renders, lesson count/progress reset, quizzes playable, and the
   "what to do next" panel points at lesson 1.

## Done criteria

- [ ] Pre-flight passed (papers found; wrap-up states captured).
- [ ] Kyle approved the new syllabus (one gate).
- [ ] `research-portfolio` course regenerated in place, `validate` clean, no stale files.
- [ ] All eight projects covered; two new papers wired in as reading.
- [ ] Live check in the hub at `/courses/research-portfolio` passes.
- [ ] `docs/MASTER_PLAN.md` updated in the same session (tick the card, changelog entry) —
      note the course content itself is gitignored user data; only the docs change is committed.

---

## Handoff prompt

Launch: `cd ~/Projects/home-base && claude --model claude-opus-5 --effort high` — a
well-specified build with one approval gate; must run locally (the course sidecar is
gitignored user data).

```text
Read docs/PORTFOLIO_COURSE_REFRESH_PLAN.md in full and execute it. You are the implementer;
the plan's decisions were confirmed with me on 2026-08-04 — don't relitigate them. Also read
its "Corrections since this plan was written" section: where the plan's framing and a repo's
main disagree, the repo wins, and the pre-flight includes the paper-currency and
blind-cite-PR-#12 checks it adds.

Summary of what it asks: fully regenerate the hub course "research-portfolio" (advanced,
interview-defense) IN PLACE to cover all eight portfolio projects — the six it has plus
mute-map and hush-gauge — using ~/Projects/portfolio, the eight project repos, the private
portfolio-prep repo, and the two research papers I generated today for blind-cite and
hush-gauge. Run the plan's pre-flight first; if either paper is missing, stop and ask me.
Then use the course-builder skill (update-in-place path), propose the new syllabus, wait for
my approval at that one gate, author everything autonomously, validate, delete stale files,
and verify the course live in the hub. Finish by updating docs/MASTER_PLAN.md per the plan's
done criteria.
```
