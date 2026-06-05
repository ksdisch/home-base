# 📚 Learning Hub

A personal, calm learning dashboard that sits on top of your **NotebookLM** notebooks.
See every topic you're learning in one place, take your NotebookLM-generated quizzes
*inside the hub* with real score tracking, and get nudged on what to review next — a UI
you actually enjoy, with links back to NotebookLM where useful.

> **Status:** 🌱 Scaffold only. No application code yet. This repo currently holds the
> spec, the verified capability/data notes, and a kickoff prompt for the build.
> Start the build from [`docs/KICKOFF_PROMPT.md`](docs/KICKOFF_PROMPT.md).

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
- [`docs/KICKOFF_PROMPT.md`](docs/KICKOFF_PROMPT.md) — paste this into a fresh Claude Code session to begin the build.

## Honest limitations

- "Episode listened" is a **manual ✓** — NotebookLM has no listening API.
- Quizzes taken *inside* NotebookLM aren't retrievable; the hub becomes the home for quiz-taking.
- Phone access needs the Mac running + same network until/unless the app is hosted.
- `nlm` requires a valid login (`nlm login`); the hub surfaces auth errors gracefully.
