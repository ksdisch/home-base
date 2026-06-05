# Learning Hub — Product Spec

_Agreed during kickoff. Source of truth for what we're building and why._

## Vision (one line)
A personal, calm learning dashboard on top of your NotebookLM notebooks: see every topic
at once, take your quizzes *inside the hub* with real score tracking, and get nudged on
what to review next — a UI you actually like, with links back to NotebookLM where useful.

## Confirmed product decisions (from kickoff interview)
| Decision | Choice |
|---|---|
| **Quiz model** | **Take quizzes in the hub** — pull questions + correct answers from NotebookLM, render interactively, auto-grade, store every attempt. (Feasibility verified — see `docs/nlm-capabilities.md`.) |
| **Scope** | **All notebooks, grouped** (Learning / Interview prep) **+ custom topics** (non-NotebookLM interests tracked loosely). |
| **Form factor** | Local **responsive web app**, PWA-installable. Desktop-primary; phone-reachable over LAN while the Mac is running. Hosted phone access = a later phase. |
| **Tracking depth** | **Rich** — episodes ✓, quiz score history + trends, progress %, notes, streaks, decaying mastery, spaced-repetition "Review next" queue. |

## Data flow
| Layer | Source | Notes |
|---|---|---|
| Topic catalog | Sidecars (`~/Projects/NotebookLMs/<alias>/README.md` + `artifacts/*.json`) + `nlm studio status <id>` | Read-only. "Refresh" re-syncs to catch newly generated series/quizzes. |
| Quiz / study-guide content | `nlm download …` on demand, cached locally | Hub never writes to NotebookLM. |
| User progress | Hub's own **SQLite** store | Attempts, episode ✓s, notes, mastery, streaks, custom topics. Kept *out* of sidecars so they stay clean. |

## Screens
1. **Hub home** — every topic as a card, grouped Learning / Interview prep / Custom; each shows progress %, mastery signal, "🔁 due for review" badge, last-touched date.
2. **Topic detail** — audio season (each episode: ✓-listened toggle + play/link), study guides rendered inline, quizzes with a **Take** button, the standalone library.
3. **Quiz player** — interactive cards, optional hint, instant grade, per-question rationale on misses, attempt saved.
4. **Progress** — score trends per topic, repeatedly-missed questions, current streak, **"Review next"** queue.
5. **Custom topics** — add a book / YouTube series / loose interest with no NotebookLM artifacts; track with manual progress + notes.

## The "rich" tracking engine
- **Mastery that decays:** each quiz attempt feeds a per-topic (and per-question) mastery score that fades over time since last review.
- **Spaced repetition:** decayed mastery + missed questions populate the "Review next" queue.
- **Streaks:** consecutive days with any learning activity.

## NotebookLM integration
- Per-topic deep link to `https://notebooklm.google.com/notebook/<notebook_id>`; per-artifact deep links best-effort.
- Hub is **read-only** toward NotebookLM. Generating new series stays in the `audio-series` skill (possible future "generate from hub" button — not v1).

## Proposed stack (recommendation, swappable)
- **Frontend:** Vite + React + TypeScript + Tailwind; Recharts (or similar) for trends; PWA manifest for installability.
- **Backend:** thin **FastAPI (Python)** — parses sidecars, shells out to `nlm`, persists to **SQLite**, computes mastery/spaced-repetition. Python chosen because `nlm` is Python and already on PATH.
- **Repo:** `~/Projects/learning-hub/` (this repo).

## Honest limitations
- "Episode listened" is a **manual ✓** (no NotebookLM listening API).
- Quizzes taken *inside* NotebookLM aren't retrievable; the hub is the home for quiz-taking.
- Phone access needs the Mac running + same network until/unless hosted.
- `nlm` needs a valid login; surface auth errors gracefully and point the user to `nlm login`.

## Suggested build order (end state still has everything)
1. **Catalog + home + topic detail** — read the real notebooks, see all topics in one place.
2. **Quiz player + attempt storage** — the headline feature.
3. **Progress charts + streaks.**
4. **Mastery decay + spaced-repetition "Review next."**
5. **Custom non-NotebookLM topics.**
