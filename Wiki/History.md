# History — home-base

> How this project got here: a chronological narrative of eras and milestones,
> reconstructed from merged PRs, git history, wrap logs, and ADRs.
> PR numbers, merge dates, tags, and SHAs are **Fact** by construction; rationale
> lines carry explicit labels (**Fact** when quoted from a PR body/ADR, **Inference**
> when reconstructed). Decisions are anchored by ID to the project's decision
> ledger — never restated here. **Append-only:** new milestones are added at the
> bottom (above the Mining coverage footer); existing entries are never rewritten.

## Origin — 2026-06

Started as **learning-hub**: a calm, local, read-only web dashboard over Kyle's NotebookLM notebook sidecars (`~/Projects/NotebookLMs/`), with quizzes, progress, and spaced repetition layered on top. First commit `62f1815` (2026-06-05): "Scaffold learning-hub: spec, verified nlm/data docs, kickoff prompt." The founding docs are `SPEC.md` and `docs/KICKOFF_PROMPT.md`; the scaffold session is logged in `docs/session-logs/2026-06-05-lhub-scaffold-and-kickoff.md`. The two founding invariants — strictly read-only toward NotebookLM sidecars, all user progress in hub-owned SQLite — date from this era; see D2 and D3 in `Decisions.md`.

## Era: Learning Hub build-out (2026-06)

The SPEC's phased build, Phases 1–6, plus the course pipeline and a bug-hunt closeout. By the end of June the hub was a full local learning app: catalog, quiz player, progress dashboard, SM-2 spaced repetition, custom topics, and hub-native courses.

### Phase 1 — read-only hub over the sidecars — 2026-06-05
- **Landed:** FastAPI backend (lenient sidecar parser, read-only `nlm` boundary, hub-owned SQLite, offline quiz-grading oracle) + Vite/React/TS frontend, `make dev` (PR #2)
- **Why:** "a calm, PWA-installable dashboard over the user's NotebookLM notebooks" with mutating `nlm` commands raising "before any subprocess" [Fact — PR #2 body] — see D2, D3 in `Decisions.md`
- **Tradeoff:** sidecar-first with opt-in live reconcile, per `docs/PHASE1_PLAN.md` fork decisions [Fact — PR #2 body]

### Phases 2–5 — quiz player, progress, mastery decay, custom topics — 2026-06-06 → 2026-06-07
- **Landed:** in-hub quiz player (PR #7), progress dashboard with trends/streaks (PR #8), mastery decay + "Review next" queue (PR #9), custom non-NotebookLM topics (PR #10); custom-topics CLI groundwork in PR #6

### Phase 6 — Smarter SR Core (per-question SM-2) — 2026-06-07
- **Landed:** per-question SM-2 scheduler, daily study plan with a time budget + interleaving, reflection journal; first frontend test harness + FE CI job (PR #11)
- **Why:** Phase 4's topic-level queue was "honest but blunt — a concept nailed five times decays like one scraped once with a hint"; this makes "the question the unit of scheduling" [Fact — PR #11 body]
- **Tradeoff:** layered alongside the existing topic queue rather than replacing it [Fact — PR #11 body]

### Course Pipeline (Phase 7) — 2026-06-08
- **Landed:** hub-native course sidecars (`course.json` + materials on disk, progress in SQLite), Courses UI, `/build-course` + `course-builder` skill, course quizzes in the player with per-course SM-2 (PR #15)
- **Why:** mirrors "the NotebookLM catalog/episode-progress split" [Fact — PR #15 body]
- **Note:** superseded draft PR #12 (squash-rebased onto main) and renumbered its "Phase 6" to Phase 7 to avoid colliding with the SR Phase 6 [Fact — PR #15 body]

### Bug-hunt closeout — 2026-06-26
- **Landed:** 11 low-severity fixes from a bug-hunt audit, one PR each (PRs #21–#31), tracker closed in PR #32
- **Why:** systematic sweep of known lows before the project went quiet for early July [Inference — rationale not recorded]

## Era: Home Base pivot — the M0–M7 arc (2026-07-13 – 2026-07-19)

The identity pivot: learning-hub becomes **Home Base**, Kyle's self-updating daily morning brief, with the Learning Hub riding along as the learning section. Seven milestones landed in six days, most built ahead of the M0 quality verdict as deliberate gate overrides.

### RENAME: learning-hub → home-base — 2026-07-13
- **Landed:** approved kickoff brief `docs/KICKOFF-home-base.md`, README/CLAUDE.md/BACKLOG retitle (PR #33); GitHub repo rename followed the merge
- **Why:** "the Learning Hub becomes Kyle's daily home base — a self-updating morning brief across his topics … with the existing hub riding along as the learning section" [Fact — PR #33 body] — see D1 in `Decisions.md`
- **Tradeoff:** internal names (SQLite filename, MCP server name, package names) intentionally unchanged — "cosmetic only, zero functional risk" [Fact — PR #33 body]

### M0 — sweep engine (de-risk brief quality, no UI) — 2026-07-13
- **Landed:** 3 pilot-topic sweep prompts with anti-slop/anti-hallucination rules, `make sweep` via `claude -p` on the subscription lane, A–F grading log (PR #34)
- **Why:** "M0 exists solely to test the project's killer assumption (can autonomous sweeps reliably catch what matters without slop, every morning?) before any interface is built" [Fact — PR #34 body]

### M1 — the Today brief page — 2026-07-14
- **Landed:** "Today" home route rendering stored sweeps, JSON sweep emission + `render_brief.py` trust gate, visit log; old home → `/learning` (PR #36)
- **Why:** Kyle picked JSON emission over Markdown parsing — "validation moves to write time with loud failure" [Fact — PR #36 body]
- **Note:** started mid-M0 as a deliberate, eyes-open gate override [Fact — PR #36 body] — see D4 in `Decisions.md`

### M2 — roster config, item ids, inline notes — 2026-07-14
- **Landed:** config-file topic roster with pause flags (PR #38); read-time item ids, `brief_notes` store, /notes browse, "Your learning" strip (PR #39)
- **Tradeoff:** ids derived at read time so "the trust-critical write path stays frozen mid-grading-week" [Fact — PR #39 body]

### M3 — hands-off (scheduled sweeps) — 2026-07-16
- **Landed:** launchd scheduler with idempotent installer, cost/usage ledger (`.runs.jsonl`), read-time story dedup with developing/first-seen labels (PR #43)
- **Why:** the gating unknown — subscription auth under launchd — was proven first with a throwaway spike [Fact — PR #43 body]
- **Note:** third deliberate M0-gate override [Fact — PR #43 body] — see D4 in `Decisions.md`

### M4 + M5 — audio brief and chat with the brief — 2026-07-16
- **Landed:** deterministic ~650-word morning-drive script narrated by local Kokoro TTS + Today player (PR #45); per-item "Ask about this" with grounded no-tools `claude -p` answers + save-as-note (PR #47)
- **Why:** audio was "the #1 item on the kickoff's 'would be amazing' list" [Fact — PR #45 body]
- **Tradeoff:** chat ships per-item, no web tools, ephemeral answers — multi-turn and web-enabled variants deliberately deferred [Fact — PR #47 body]

### M6 — mobile reach (one-port serve, PWA, offline) — 2026-07-18
- **Landed:** one-port prod path + server LaunchAgent + PWA rename (PR #55); offline brief + responsive morning loop (PR #56); tailnet HTTPS and real-iPhone proof verified after the fact (PRs #59, #61, #64)
- **Why:** make the morning brief reachable from the phone in bed, not just the Mac [Inference — reconstructed from the M6 plan title "mobile (Tailscale reach · one-port serve + LaunchAgent · PWA w/ cached brief)"]

### M7 — news mode — 2026-07-18
- **Landed:** RSS news shell with cached Google News feeds (PR #58), news signals log (PR #60), "For You" decaying interest profile + ranked tab (PR #62), topic scout with one-click roster adds (PR #63); News promoted to the mobile tab bar (PR #65)
- **Tradeoff:** RSS sourcing over LLM sweeps — "zero new LLM surface, $0/day" [Fact — PR #58 body]

### Course epic completes (Courses M3–M5) — 2026-07-16 → 2026-07-19
- **Landed:** generation at depth (PR #48), flashcard review UI (PR #49), NotebookLM enrichment in-flow (PR #50), and the authoring loop — edit/reorder/regenerate/export with one transactional write path (PR #69)
- **Why:** "a bad model output cannot corrupt a course" — every write validates or rolls back byte-identical [Fact — PR #69 body]

### M0 closes: verdict PASS — 2026-07-19
- **Landed:** week's grades + source-verified audit, "Zero fabricated items, zero fabricated-looking sources across the entire week"; one prompt tune to the AI topic's exclusion rules (PR #68)
- **Why:** kill criteria not met — "failures cluster on one story-thread in one topic and were judgment, not fabrication" [Fact — PR #68 body] — vindicating the gate overrides; see D4 in `Decisions.md`

## Era: Hardening waves and moonshots (2026-07-19 – 2026-07-21)

Post-M7 consolidation: a replenished backlog burned down in four themed waves, then four decided moonshots in one day, then a visual-craft polish pass and the first CI governance work.

### Wave 1–4 hardening — 2026-07-19 → 2026-07-20
- **Landed:** backlog replenish + bug audit (PR #72); five P1 bug fixes (PRs #73–#77); Wave 1 trust/liveness features — didn't-run banner, sweep-trust gauge, news notes, heartbeat dead-man's switch (PRs #82–#86); Wave 2 fix batches across sweep pipeline, LLM lane, news, offline, store, notes UX (PRs #87–#94); Wave 3 quality-of-life on the brief (PRs #95–#101); Wave 4 courses correctness (PR #103)
- **Why:** roadmap locked as "four waves anchored on the ~08-03 v1 check" [Fact — PR #81 title]

### Four moonshots v0 in one day — 2026-07-20
- **Landed:** Mirror ("You this week" strip, PR #104), Readiness ("Coming up" strip, PR #105), Calibrated Doubt ("the brief that bets, then grades itself", PR #106), Overnight Chief of Staff (draft-only proposal queue, PR #107)
- **Why:** Overnight is draft-only by decided fence — "each errand type can earn real send/execute only through its own M0-style graded record + gate conversation. Nothing unlocks by default" [Fact — PR #107 body]
- **Note:** PR #107 records itself as the tenth deliberate gate override [Fact — PR #107 body] — see D4 in `Decisions.md`

### Delight/Friction polish pass — 2026-07-21
- **Landed:** two brainstorm docs (PRs #108, #109) executed as 13 small UI PRs — dusk mode, tint tokens, lead-story front page, freshness dot, nav cluster split, News state hoist, and more (PRs #110–#122, #124)

### CI becomes a merge gate — 2026-07-21
- **Landed:** gitleaks secret-scan job with a stable check-run name, groundwork for required status checks (PR #123)
- **Note:** server-side enforcement was plan-gated at the time — branch protection APIs returned 403 on the private Free-plan repo [Fact — PR #123 body]

## Era: Learning Paths and the Study Scheduler (2026-07-21 – 2026-07-22)

The M8 arc: an AI study-designer over the library, then the project's first Google-service write surface.

### M8 — Learning Paths — 2026-07-21 → 2026-07-22
- **Landed:** fixture-first vertical slice (PR #127), Paths API (PR #128), PathPlayer frontend (PR #129), on-demand ✨ Generate Designer (PR #130), Plan Continue lane (PR #132), Progress rebuilt on three axes (PR #135), frontend green gate (PR #136); Designer curation fix (PR #134); approved design doc (PR #126)
- **Tradeoff:** built against a deterministic Jacobian Lens fixture first, `claude -p` Designer swapped in last [Fact — PR #127 body]

### Study Scheduler v0 → v1 — 2026-07-22
- **Landed:** opt-in Google Calendar study blocks for a path — deterministic planner + free/busy + one-confirm batch write + removable ledger (PR #137); flexible preference-honoring scheduling (PR #140); local parser primary, claude fallback (PR #141); conflict flagging + double-book (PR #142)
- **Why:** "second acting surface (after Overnight) and its first Google-service write" [Fact — PR #137 body]; the negotiation lane sets "planner knobs only (never invents a time — keeps the M0 no-fabrication bar)" [Fact — PR #137 body] — see D5 in `Decisions.md`

### Path spine correction — 2026-07-22
- **Landed:** Jacobian learning path rebuilt on the audio overview season, not the video series, guarded by `test_paths_fixture.py` (PR #143); topics↔courses cross-link + course quizzes in the daily Plan (PR #144)
- **Why:** see D6 in `Decisions.md`

## Era: Stabilization and the wiki (2026-07-26)

### CI date bomb defused + wiki initialized — 2026-07-26
- **Landed:** news-scout test seeded events relative to the real clock instead of a fixed date, restoring green CI on every PR (PR #147); project wiki initialized (PR #146)
- **Why:** a fixed `NOW = 2026-07-18` seed decayed below the For You score floor around 07-23, failing backend pytest on every PR since [Fact — PR #147 body]

---

## Mining coverage
_Backfilled 2026-07-26 by project-wiki BACKFILL. Entries after this date are
appended live by MAINTAIN._
- PR title sweep: all 141 merged PRs — no cap (limit 300, not saturated)
- Deep reads: 20 of 141 PRs (size/label/title signal; cap 20): #1, #2, #11, #15, #33, #34, #36, #39, #43, #45, #47, #55, #58, #68, #69, #107, #123, #127, #137, #147
- Also swept: git log on origin/main (125 merges / 288 non-merges), tags (none), wrap logs (`docs/session-logs/2026-06-05-lhub-scaffold-and-kickoff.md`), kickoff briefs (`docs/KICKOFF_PROMPT.md`, `docs/KICKOFF-home-base.md`), decision ledger (`Decisions.md` D1–D6), ADRs (none)
- Not mined: closed-unmerged PRs (#12, #13, #18), issues, `docs/ideas/` vision docs beyond those cited in PR bodies
