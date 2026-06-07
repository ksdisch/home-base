# 📚 Learning Hub

A personal, calm learning dashboard that sits on top of your **NotebookLM** notebooks.
See every topic you're learning in one place, take your NotebookLM-generated quizzes
*inside the hub* with real score tracking, and get nudged on what to review next — a UI
you actually enjoy, with links back to NotebookLM where useful.

> **Status:** ✅ **Phases 1–5 shipped (the full SPEC build order) + Phase 6 "Smarter SR Core."**
> Catalog + hub home + topic detail (Phase 1), the in-hub quiz player with auto-grading + attempt
> storage (Phase 2), the progress dashboard with per-topic score trends, an activity streak, and
> "shaky spots" (Phase 3), the mastery-decay engine + spaced-repetition **"Review next"** queue —
> with a "🔁 due for review" badge + decayed-mastery chip on the home cards (Phase 4), **custom
> (non-NotebookLM) topics** on the home screen (Phase 5), and a **per-question SM-2 scheduler** +
> a **daily, time-boxed "Today's plan"** that interleaves due questions across topics, plus the
> **reflection journal** (Phase 6). All runnable with one command. See
> [`docs/PHASE1_PLAN.md`](docs/PHASE1_PLAN.md), [`docs/PHASE2_PLAN.md`](docs/PHASE2_PLAN.md),
> [`docs/PHASE3_PLAN.md`](docs/PHASE3_PLAN.md), [`docs/PHASE4_PLAN.md`](docs/PHASE4_PLAN.md),
> [`docs/PHASE5_PLAN.md`](docs/PHASE5_PLAN.md), and [`docs/PHASE6_PLAN.md`](docs/PHASE6_PLAN.md).

---

## Run it locally

One command boots both processes:

```bash
make dev          # or: ./dev.sh
```

It bootstraps a Python 3.12 backend venv + frontend deps on first run, then starts:

| Process | URL | Notes |
|---|---|---|
| **Frontend (Vite)** | **http://localhost:5173** | ← open this |
| Backend (FastAPI) | http://localhost:8000 | API under `/api`; the Vite dev server proxies `/api` → here |

Then open **http://localhost:5173**. The home screen lists your real notebooks (read live from
`~/Projects/NotebookLMs/`), grouped Learning / Interview prep. Click a card to see its episodes,
study guides, and quizzes.

```bash
make test         # backend test suite (parsing robustness, read-only, auth, quiz oracle)
make build        # production frontend build
make setup        # bootstrap deps without running
```

**Requirements:** Python 3.12 (falls back to system `python3`), Node 18+, and the `nlm` CLI on
your PATH (only needed for the optional "Refresh (live)" reconcile — the catalog works offline
without it). If `nlm` auth lapses, the hub shows a calm "run `nlm login`" banner, never a crash.

---

## Why this exists

NotebookLM generates great audio series, study guides, and quizzes — but it gives you
**no score history, no cross-topic view, and a UI that's hard to love.** The quizzes are
taken inside NotebookLM and your performance vanishes. This hub becomes the *home* for
taking quizzes and tracking learning across all your topics.

## What it does (target end state)

- **One view of every topic** — all your NotebookLM notebooks as cards, grouped
  *Learning / Interview prep / Custom*, each with progress %, a decaying mastery signal,
  a "🔁 due for review" badge, and last-touched date.
- **Take quizzes in the hub** — pulls quiz questions + correct answers + rationales from
  NotebookLM (verified — see [`docs/nlm-capabilities.md`](docs/nlm-capabilities.md)),
  renders them interactively, auto-grades, and stores every attempt.
- **Rich tracking** — score trends, repeatedly-missed questions, streaks, spaced-repetition
  "Review next" queue, mastery that decays over time.
- **Custom topics** — track non-NotebookLM interests (a book, a YouTube series, an idea)
  loosely, with manual progress + notes.
- **Read-only toward NotebookLM** — the hub never writes to your notebooks; generating new
  series stays in the `audio-series` skill.

## Architecture at a glance

| Layer | Source of truth |
|---|---|
| Topic catalog | NotebookLM **sidecars** (`~/Projects/NotebookLMs/<alias>/`) + `nlm studio status` |
| Quiz / study-guide content | `nlm download …` on demand, cached locally |
| Your progress (attempts, ✓s, mastery, streaks, notes, custom topics) | The hub's **own** local SQLite store — kept *out* of the sidecars |

**Proposed stack (swappable):** Vite + React + TypeScript + Tailwind frontend; thin
FastAPI (Python) backend that parses sidecars, shells out to `nlm`, and persists to SQLite.
Python because `nlm` is Python and already on PATH. Delivered as a local, responsive,
PWA-installable web app.

## Docs

- [`SPEC.md`](SPEC.md) — the agreed product spec.
- [`docs/nlm-capabilities.md`](docs/nlm-capabilities.md) — **verified** `nlm` capabilities + quiz JSON shape.
- [`docs/data-sources.md`](docs/data-sources.md) — where the catalog data lives, with examples.
- [`docs/fixtures/sample-quiz.json`](docs/fixtures/sample-quiz.json) — a real downloaded quiz to build the player against offline.
- [`docs/PHASE1_PLAN.md`](docs/PHASE1_PLAN.md) — the Phase 1 implementation plan + fork decisions.
- [`docs/KICKOFF_PROMPT.md`](docs/KICKOFF_PROMPT.md) — the original build kickoff prompt.

## Honest limitations

- "Episode listened" is a **manual ✓** — NotebookLM has no listening API.
- Quizzes taken *inside* NotebookLM aren't retrievable; the hub becomes the home for quiz-taking.
- Phone access needs the Mac running + same network until/unless the app is hosted.
- `nlm` requires a valid login (`nlm login`); the hub surfaces auth errors gracefully.
