# Learning Hub — Build Kickoff

> Paste everything below the line into a fresh Claude Code session opened at this repo's root
> (`/Users/kyledisch/Projects/learning-hub`). It's written to that session.

---

You are picking up a scaffolded, **docs-only (no code yet)** repo at `/Users/kyledisch/Projects/learning-hub` and building it into a working local web app. This session is where the app gets built — using **ultracode multi-agent workflows** to implement and adversarially verify. The product is fully specified and the headline feature is already feasibility-verified. Your job is to build it, not redesign it.

## Read these first (do not restate them back to me)
Read IN FULL before proposing anything:
- `SPEC.md` — the agreed product spec, screens, tracking engine, build order.
- `README.md` — what this is and why; architecture at a glance; honest limitations.
- `docs/nlm-capabilities.md` — **VERIFIED** `nlm` CLI behavior + the exact quiz JSON shape. Build on it; don't re-derive.
- `docs/data-sources.md` — on-disk shape of the NotebookLM sidecars (the catalog source) and how to parse them.
- `docs/fixtures/sample-quiz.json` — a real 10-question downloaded quiz. This is your **offline test oracle** for the quiz player (Phase 2). Build/test against it with zero network calls.

These were settled during a kickoff interview. Treat them as decided — don't re-litigate the product, the feasibility, or the data shapes.

## What you're building (one line)
A personal, calm, local, PWA-installable dashboard over my NotebookLM notebooks: see every topic in one place, take my NotebookLM quizzes **in the hub** with real score tracking, and get nudged on what to review next.

## Verified core capability (already confirmed — build on it)
`nlm download quiz <notebook_id> --id <artifact_id> -f json` returns clean JSON: `questions[]`, each with `answerOptions[{text, isCorrect, rationale}]` and a per-question `hint`. **Exactly one** option per question is `isCorrect`; **every** option has a `rationale`; option counts **vary** (the sample has a 2-option question — do NOT hardcode 4). This is a complete feed for an in-hub quiz engine: render, let the user pick, auto-grade against `isCorrect`, reveal `rationale` on misses, offer `hint` on demand, save the attempt.

## The five screens (north star — target end state)
1. **Hub home** — every notebook as a card, grouped **Learning / Interview prep / Custom**; each shows progress %, a mastery signal, a "🔁 due for review" badge, last-touched date, and links to both its NotebookLM URL and its topic-detail page.
2. **Topic detail** — audio season (per episode: ✓-listened toggle + play/link), study guides rendered inline, quizzes each with a **Take** button, the standalone library.
3. **Quiz player** — interactive cards, optional hint, instant auto-grade, per-question rationale on misses, attempt saved.
4. **Progress** — score trends per topic, repeatedly-missed questions, current streak, a **"Review next"** queue.
5. **Custom topics** — non-NotebookLM interests tracked loosely with manual progress + notes.

## Agreed stack (swappable only with a better-justified case you raise BEFORE building)
- **Frontend:** Vite + React + TypeScript + Tailwind; Recharts (or similar) for trends later; PWA manifest for installability.
- **Backend:** thin **FastAPI (Python)** — parses sidecars, shells out to `nlm`, persists to **SQLite**, later computes mastery/spaced-repetition. (Python because `nlm` is Python and already on PATH.)
- Local, responsive, one-command run. If you genuinely think a piece is wrong, say so with a concrete reason in the plan step — don't silently swap it.

## Architecture orientation (get the wiring clean and boring before any features)
Two-process local app:

```
learning-hub/
  backend/                  # FastAPI app
    app/
      main.py               # app factory, CORS for the Vite origin, router includes
      api/                  # routers: /catalog, /topics/{id}, (later) /quizzes, /attempts
      catalog/              # sidecar ingestion: enumerate ~/Projects/NotebookLMs/*, parse frontmatter + artifact-map JSON, README-table fallback
      nlm/                  # the ONLY place that shells out to `nlm`; wraps subprocess, maps exit/stderr -> typed errors (incl. auth-needed)
      store/                # SQLite: engine, schema/migrations, models. Hub-owned data ONLY.
      cache/                # on-disk cache for downloaded artifact JSON (quizzes etc.)
    data/                   # gitignored: learning-hub.sqlite + cached downloads
  frontend/                 # Vite + React + TS + Tailwind
    src/
      api/                  # typed client; ONE base-URL constant
      pages/                # Home, TopicDetail (Quiz/Progress later)
      components/
  docs/                     # already here — source of truth, leave alone
  Makefile / dev script     # one-command run
```

**Wiring rules:**
- **One command** (e.g. `make dev` or `dev.sh`) boots FastAPI + Vite together; document the command and the two ports in the README. Pin ports (suggest backend `:8000`, frontend `:5173`).
- Frontend talks to the backend via **one configurable base URL** — either a Vite dev-server proxy (`/api` → `:8000`) or a single `VITE_API_BASE` env constant. Pick one, write it down, don't scatter URLs.
- **`nlm` shell-out is isolated** in `backend/app/nlm/` and nowhere else. It returns typed results/errors so the API turns an auth failure into a clean "run `nlm login`" response the UI renders as a friendly banner — never a 500 stack trace.

## Invariants (non-negotiable — violating these is a defect)
1. **Read-only toward NotebookLM.** Never run any `nlm`/MCP call that mutates a notebook. The hub only reads (`nlm studio status`, `nlm download …`). No create/delete/revise/share/source/note writes. Ever.
2. **User progress lives ONLY in the hub's own SQLite** (attempts, episode ✓s, notes, mastery, streaks, custom topics) — never written back to the `~/Projects/NotebookLMs/` sidecars; they stay clean.
3. **Sidecars are someone else's human-authored markdown — parse leniently.** Never assume a table column order, a heading's existence, or a well-formed row. Prefer `artifacts/audio-series-artifact-map.json` when present; fall back to README tables; treat malformed/missing rows as skippable, not fatal.
4. **"Episode listened" is a manual checkbox** — there is no listening API.
5. **`nlm` auth can fail at any call.** Detect it from exit code/stderr and surface a clear, non-scary **"run `nlm login`"** message (only the user can re-auth — it's an interactive browser flow). Degrade gracefully; don't crash.
6. **Always re-read the live roster** from `~/Projects/NotebookLMs/INDEX.md` / the `<alias>/` dirs at runtime — the notebook set changes. Don't hardcode the snapshot from `data-sources.md`.

## Build order — Phase 1 FIRST, ship before moving on
1. **Catalog + home + topic-detail** ← build this now.
2. Quiz player + attempt storage (the headline feature).
3. Progress charts + streaks.
4. Mastery decay + spaced-repetition "Review next."
5. Custom topics.

Don't build ahead — but make Phase-1 choices that don't box later phases in.

## Execution mode per phase — gate the foundations, automate the rest
"Execution mode" here means *how much you stop for my approval* — not the `nlm batch` CLI or any docs-batch tool, which are unrelated to building this app.

- **Phases 1–2 — GATED.** Run these through the full **explore → plan → confirm-with-me → build → verify** rhythm. They set the architecture (repo wiring, catalog model, SQLite schema) and the **quiz-grading contract** — costly to reverse, so I want eyes on the plan before large code generation.
- **Phases 3–5 — may run more autonomously.** Once Phase 1 locks the structure and schema, progress charts/streaks, the mastery-decay + spaced-repetition engine, and custom topics are largely mechanical. You may run them with fewer gates (e.g. "do Phase 3 end-to-end, then show me") — but **always still end each phase with adversarial verification against its acceptance criteria**, and **still branch + never push to `main` without my per-commit go-ahead.** If I want a hands-off build of these, I'll hand them to the `autonomous-milestone` skill explicitly.
- **Default when unsure:** gate it. Ask before generating a large amount of code around a decision I haven't seen.

## How to proceed — explore → plan → confirm, THEN build

**1. Explore (no app code).** Read the five docs. Then ground your plan in the real data:
- List `~/Projects/NotebookLMs/`; read 2–3 real sidecar `README.md`s + their `artifacts/audio-series-artifact-map.json` (one full-season Learning notebook, e.g. `engineering-abstractions`; one `*-interview-prep`); skim `INDEX.md`. Note the variance you'll parse around (sparse sidecars, an archived/merged notebook like `stoicism`, missing artifact-map).
- Confirm `nlm` is reachable (`nlm --version`); optionally one read-only `nlm studio status <id>` to see the live artifact shape. If auth fails, that's expected signal — note it and move on; do NOT attempt to fix auth.
- Confirm parse targets match `data-sources.md`.

**2. Plan (no app code).** Scope **Phase 1 only**. Propose: the repo skeleton (above or a better-justified variant), the catalog data model + sidecar→catalog ingestion (JSON map → README-table fallback → reconcile with `nlm studio status`), the backend↔frontend contract (the catalog JSON shape), the SQLite schema (even if Phase 1 only lightly touches it), and the one-command run story. Offer **2–3 ranked options where there's a real fork** (e.g. Vite proxy vs `VITE_API_BASE`; sidecar-only vs reconcile-against-live-`nlm` for Phase 1), each with a one-line tradeoff and your **(Recommended)** pick.

**3. Confirm with me.** Present the plan and **wait for my go-ahead before any large code generation.**

**4. Build with ultracode**, then adversarially verify against the acceptance criteria.

## Phase 1 — concrete deliverable + acceptance criteria
**Deliverable:** Catalog + Hub home + Topic detail (read-only), runnable locally with one command.

**Done when ALL hold:**
- **One documented command** boots backend + frontend; I open one localhost URL and the app loads. README updated with the run steps and both ports.
- **Home lists my REAL notebooks** — parsed live from `~/Projects/NotebookLMs/` sidecars (frontmatter + artifact-map JSON, README-table fallback) — not fixtures, not the snapshot table.
- **Cards are grouped Learning / Interview prep** (via `template`/tags/dir-name suffix per `data-sources.md`); a **Custom** group may render empty/placeholder for now.
- **Each card** shows title + group and has **two working links**: out to `https://notebooklm.google.com/notebook/<notebook_id>`, and in to that notebook's **topic-detail page**.
- **Topic detail renders the real artifact inventory** for a notebook — audio season (episodes with a ✓-listened checkbox stub), study guides, and quizzes listed with a **Take** button placeholder (present, disabled-with-tooltip is fine; player is Phase 2) — each with a stable artifact ID, read from the JSON map where present, README-table fallback otherwise.
- **Graceful degradation, proven by a test:** a sparse/malformed/missing sidecar field still renders a valid card + detail page (bad rows skipped, no crash, no fabricated artifacts); an `nlm` auth/exec failure during any refresh shows the "run `nlm login`" message, not a stack trace.
- **SQLite is initialized but the hub performs ZERO writes to any sidecar** (assert this).
- Backend smoke test passes (catalog parse against the real dir or a fixture), and `docs/fixtures/sample-quiz.json` parses cleanly so Phase 2 can build the player offline.

**Acceptance = a person who has never seen the repo runs the one command, lands on home, sees their actual notebooks correctly grouped, clicks into one, sees its real episodes/quizzes — with no console errors and both link types working.**

Progress %, mastery, streaks, and real auto-grading are **explicitly deferred** — stubs/placeholders on the cards are fine now.

## Where adversarial verification earns its keep (focus the budget here, not on CRUD glue)
- **Sidecar parsing robustness.** Feed it the real sidecars *and* deliberately broken ones (missing frontmatter key, reordered/short table rows, absent artifact-map, duplicate IDs, an archived/merged notebook). Verify: no crash, correct grouping, no fabricated artifacts, sane fallback when the JSON map is missing.
- **Reconciliation logic** (artifact-map ↔ README tables ↔ `nlm studio status`). Check the merge: artifacts in `nlm` but not the sidecar appear (or are flagged); nothing invented or silently dropped.
- **Read-only invariant as an enforced boundary.** Prove in tests that the only `nlm` subcommands any code path can invoke are read-only (`studio status`, `download`), and that no code path writes under `~/Projects/NotebookLMs/`.
- **Auth-failure handling.** Mock `nlm` returning an auth error; verify the graceful "run `nlm login`" path end-to-end.
- **Quiz oracle (Phase 2 prep — lock the contract now):** any grading code auto-grades against `isCorrect`, handles **variable option counts**, assumes **exactly one** correct option, surfaces `rationale` on misses + `hint` on demand, and runs fully offline against `docs/fixtures/sample-quiz.json`. Tests must run with no network/`nlm` calls.

## Future-proofing (design for, don't build)
When you shape the SQLite schema + attempt model in Phase 1, leave a concrete, testable home for the later **mastery-decay + spaced-repetition** engine: per-topic and per-question mastery scores that fade with time-since-last-review, feeding a deterministic "Review next" queue via a pure, side-effect-free scoring function (**clock injected, not `now()` inline**, so it's unit-testable). Don't implement it now — just don't make Phase-1 schema choices that block it.

## Git workflow (honor exactly)
- **Branch first.** Create a `feat/…` branch before touching code. (The repo is already git-initialized with `main` pushed to GitHub.)
- Commit frequently with descriptive messages.
- **Never push to `main` without my explicit, per-commit authorization.** A blanket "go build it" is not push approval — each push needs its own green light.

## Start now
Begin with **Explore** (step 1): read the in-repo docs, inspect the real sidecar data, confirm `nlm` reachability — then come back with your **Phase-1 plan**, ranked option forks, and the one-command run story for my approval. Do not write application code until I approve the plan.
