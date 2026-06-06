# Session log — learning-hub: scaffold + kickoff prompt

**Date:** 2026-06-05 · **Repo:** `ksdisch/learning-hub` (private) · **Branch:** `main`

> Scope note: this session was the **kickoff + scaffold + handoff** for a new project. The
> Phase 1 *implementation* (`e3f4662`…`27ea3eb`), the `/episode-review` skill + quiz-session CLI
> (`c0a030b`), and CI (`bb723dc`) landed **in a parallel session** while this one ran — they're
> noted as context, not claimed as this session's output.

---

## 1. What we did
- Ran a kickoff interview (product discovery) and locked four decisions: in-hub auto-graded quizzes; scope = all notebooks grouped + custom topics; rich tracking; form factor = local responsive web app.
- **Verified the headline feature is feasible before committing** — ran `nlm download quiz <nb> --id <id> -f json` live against a real notebook; confirmed it returns questions + `isCorrect` + per-option `rationale` + `hint`.
- Scaffolded the repo (`62f1815`): `README.md`, `SPEC.md`, `docs/nlm-capabilities.md`, `docs/data-sources.md`, `.gitignore`, and a real quiz saved as `docs/fixtures/sample-quiz.json` (offline test oracle).
- Authored `docs/KICKOFF_PROMPT.md` via a 3-lens multi-agent workflow (architecture / feature / risk drafters → one synthesizing editor).
- Created the private GitHub repo and pushed `main`.
- Added a per-phase **execution-mode note** to the kickoff prompt (`4730dce`, PR #1) — gate Phases 1–2, automate 3–5.
- Routed that change through a feature branch + PR #1 + squash-merge after a **hook blocked direct push to `main`**.
- Saved a `project` memory; reconciled cleanly with the parallel session's Phase 1 merge (my docs PR landed first, so Phase 1 built on top of it conflict-free).

## 2. The why
- **Feasibility probe before design.** The whole product hinges on extracting quiz Q&A from NotebookLM. Rather than promise it, we tested it live. Pattern: *spike the load-bearing assumption first* — if `isCorrect` hadn't been in the payload, the entire "take quizzes in the hub" mechanic was dead and we'd have pivoted to manual score logging.
- **Sidecars as catalog source, hub-owned SQLite for progress.** Read the existing `~/Projects/NotebookLMs/<alias>/` sidecars for the topic catalog, but keep all user state (attempts, ✓s, mastery) in the hub's own store. Pattern: *separate upstream source-of-truth from your own mutable state*; keeps the sidecars clean and the integration **read-only toward NotebookLM**.
- **Kickoff prompt as a handoff artifact.** The build happens in a fresh context window, so the prompt has to be self-contained: point at the in-repo docs, state the verified capability, define a concrete Phase-1 acceptance bar, and encode the invariants. Alternative rejected: just "start building" inline — would have lost the verified facts and the gating discipline on context reset.
- **Branch + PR over direct push to main.** A `PreToolUse` hook blocked `git push origin main` even with verbal permission. We didn't fight it — created `docs/kickoff-execution-mode`, opened PR #1, and used a **server-side squash-merge** (which bypasses the local-push guard). Pattern: *let the harness enforce policy; route around guards the sanctioned way.*
- **Execution-mode-per-phase ("gate the foundations, automate the rest").** Prompted by your question about a "batch" command. Phases 1–2 set architecture + the quiz-grading contract (costly to reverse → human approval gate); Phases 3–5 are mechanical (→ can run more autonomously). Tradeoff: autonomy is matched to *reversibility*, not to how tedious the work is.
- **Didn't touch the branch I didn't create.** Found `feat/phase1-…` mid-session; flagged it and left it alone rather than assume/delete. Pattern: *surface unknown state, don't mutate it.*

## 3. Concepts and vocabulary
- **Sidecar (file)** — a local per-notebook `README.md` + `artifacts/*.json` mirroring NotebookLM state. Today: the catalog data source the hub parses.
- **Feasibility spike / probe** — a throwaway check to de-risk an assumption before building on it. Today: the live `nlm download quiz` test.
- **Test oracle / fixture** — a known-good reference a test asserts against. Today: `docs/fixtures/sample-quiz.json`, so the quiz player can be built/tested with zero network calls.
- **Artifact map** — the JSON mapping `Ep N → artifact IDs`; authoritative over the human-authored README tables. Today: the preferred parse target in `data-sources.md`.
- **PreToolUse hook** — a harness guard that intercepts a tool call before it runs and can block it. Today: blocked `git push … main`.
- **Squash merge** — collapses a branch's commits into a single commit on the base. Today: PR #1's merge into `main`.
- **Lenient / defensive parsing** — tolerate missing fields, reordered columns, malformed rows without crashing. Today: the mandated invariant for sidecar ingestion.
- **Read-only invariant** — never issue a call that mutates the upstream system. Today: the hub may only `nlm studio status` / `download`, never create/delete/revise.
- **Fan-out + synthesis (multi-agent workflow)** — parallel drafters from different angles, then one editor merges. Industry-ish name: map-reduce over agents. Today: authoring the kickoff prompt.
- **Spaced repetition / decaying mastery** — schedule reviews as recall strength fades over time. Today: the Phase 4 design (deferred), with **clock injection** (pass `now` as a param) flagged to keep it unit-testable.

## 4. Takeaways
- **Probe the risky assumption before you design around it.** Ex: confirmed the quiz JSON carries `isCorrect`+`rationale` before speccing the whole in-hub quiz engine — one CLI call decided the product's core mechanic.
- **Keep your own state out of someone else's source of truth.** Ex: catalog reads from sidecars; progress writes only to the hub's SQLite — the integration stays read-only and the sidecars stay clean.
- **Match autonomy to reversibility, not tedium.** Ex: gate Phases 1–2 (architecture/grading contract), let Phases 3–5 run hands-off.
- **When a guard blocks you, take the sanctioned path instead of forcing it.** Ex: hook blocked a main push → branch + PR + squash-merge landed the same change cleanly.

## 5. Suggested next moves
1. **Phase 2 — in-hub quiz player + attempt storage (Recommended).** The headline feature; it's unblocked (grading oracle + fixture already built, schema in place from Phase 1) and it's the next *gated* phase. Everything in Phases 3–5 depends on the attempt data it produces, so it's the correct dependency-order pick. Effort: **medium**. *Caveat below.*
2. **Reconcile the new `/episode-review` skill + quiz-session CLI with the planned web player.** A parallel commit (`c0a030b`) already added a CLI/skill path for quiz sessions. Decide whether the web quiz player and the CLI converge on one attempt store or stay separate — answer this *before* building Phase 2 so you don't fork the data model. Effort: **small** (a decision), then folds into #1.
3. **Phase 3 — progress charts + streaks.** Naturally follows once attempts exist; low blast radius, mostly read-side. Effort: **small–medium**.
4. **Hosting for phone access.** Strategically valuable (you listen on the phone) but explicitly deferred in the spec; not urgent and adds auth/`nlm`-token complexity. Effort: **medium**.

## 6. 30-second elevator version
I'm building a Learning Hub — a personal web dashboard that sits on top of my NotebookLM notebooks so I can see every topic I'm studying in one place and actually take the quizzes in-app with real score tracking, which NotebookLM doesn't give you. Today was the kickoff: I ran a discovery interview to pin down the product, then de-risked the core feature by confirming live that NotebookLM's CLI exports quizzes with the correct-answer flags and rationales — so auto-grading is genuinely possible, not a guess. I scaffolded the repo with the spec and verified-capability docs, including a real quiz saved as an offline test fixture, and wrote a self-contained kickoff prompt to drive the build in a fresh session. I also added a rule for which phases need my sign-off versus which can run autonomously, and I had to land one change via a pull request because a guard blocks direct pushes to main. Phase 1 — the catalog and topic browsing — shipped in parallel, so the quiz player is up next.

## 7. Active recall

1. Walk me through how the hub takes a quiz that "lives" in NotebookLM and auto-grades it. Where does the data come from and what's in it?
2. Why does user progress live in the hub's own database instead of being written back to the NotebookLM sidecars? What does that buy you?
3. You couldn't push to `main` directly even with permission. What stopped you, and how did the change still land on `main`?
4. What's the "gate the foundations, automate the rest" rule, and what's the actual criterion deciding which phases get gated?
5. What would break if the sidecar parser assumed every notebook had a well-formed artifact table?

---
*Try to answer each aloud before scrolling. Answer key below.*

### Answer key
1. The hub shells out to `nlm download quiz <notebook_id> --id <artifact_id> -f json`, which returns JSON: a `questions[]` array where each question has `answerOptions[{text, isCorrect, rationale}]` plus a `hint`. The hub renders the options, the user picks, and it grades against the `isCorrect` flag (exactly one true per question), showing the `rationale` on misses. It's read-only — NotebookLM is never mutated.
2. Two reasons: (a) **read-only invariant** — the sidecars are NotebookLM's mirror and the hub must not mutate upstream state; (b) **separation of concerns** — attempts, streaks, and mastery are the hub's own data with their own schema and lifecycle. Writing them into the sidecars would pollute a source of truth the `audio-series` skill also owns and would couple the hub to a markdown format. Keeping them in the hub's SQLite keeps both clean and independently evolvable.
3. A `PreToolUse` hook intercepted `git push origin main` and blocked it ("use feature branches, not direct push to main"). The change landed by creating a `docs/…` branch, pushing *that*, opening PR #1, and doing a **server-side squash-merge** via `gh pr merge` — a GitHub-side merge, not a local push, so it doesn't trip the guard. Local `main` was then fast-forwarded to match.
4. Phases 1–2 run *gated* (explore → plan → confirm before large codegen); Phases 3–5 may run more autonomously. The criterion is **reversibility/blast radius**, not difficulty: Phases 1–2 set the architecture and the quiz-grading contract — expensive to undo — so they get a human approval gate; Phases 3–5 are mechanical build-out on a locked schema, so they don't.
5. It would crash or silently drop notebooks on real data. The sidecars are human-authored markdown with sparse entries, an archived/merged notebook (`stoicism`), reordered or short table rows, and sometimes a missing artifact-map JSON. The mandated fix: parse leniently — prefer the JSON artifact-map, fall back to README tables, skip malformed rows instead of failing, and never fabricate artifacts. (This is exactly what the Phase 1 "harden parser against adversarial review" commit, `a01b529`, addressed.)
