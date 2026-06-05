# Phase 1 — Implementation Plan (Catalog + Home + Topic detail)

_Autonomous build plan. Grounded in the real `~/Projects/NotebookLMs/` data inspected on
2026-06-05. Scope is Phase 1 only; later phases (quiz player, progress, mastery, custom topics)
are designed-for but not built._

## What the real data taught us (drives the design)

Inspecting the live sidecars + one read-only `nlm studio status` call surfaced the variance the
parser must survive:

| Notebook | Frontmatter `template` | Artifact-map JSON? | README table shapes |
|---|---|---|---|
| `engineering-abstractions` | `learning-topic` | ✅ present **but `audio` only covers Eps 1–6** (7–10 live under a `wave2_audio_*` key) | `Type\|Format\|Status\|ID\|Notes`, `Ep\|Title\|Format\|Len\|Status\|Artifact ID`, `Ep\|Topic\|Study Guide ID\|Quiz ID` |
| `claude-power-user` | `learning-topic` | ❌ none | `Type\|Title\|Status\|ID`, `Ep\|Title\|Format\|Length\|Status\|ID`, `Title\|Format\|Length\|Status\|ID` |
| `steame-interview-prep` | `interview-prep` | ❌ none | `Type\|Format\|Status\|Artifact ID\|Round\|Notes`, `Ep\|Title\|Length\|Status\|Artifact ID\|File` |
| `inner-work` | `merged` | ❌ none | composition tables (no artifact IDs) |
| `stoicism` | `learning-topic` + `status: archived`, `merged_into` | ❌ none | source tables only |
| `segal` / `medix` / `clarity` -interview-prep | `interview-prep` | ❌ none | varies |

**Hard lessons baked into the parser:**

1. **Never assume column order.** Header names vary (`ID` vs `Artifact ID`, `Format` vs `Length`
   vs `Len`). Map columns by normalized header, not position.
2. **The JSON map is preferred but not complete.** `engineering-abstractions`' map omits audio
   Eps 7–10. So ingestion must **merge** JSON map + README rows (dedupe by artifact id), never
   pick one source XOR the other.
3. **A row is an artifact only if it contains a UUID.** This is the anti-fabrication guard:
   header rows, prose rows, composition tables, and malformed rows have no UUID → skipped.
4. **A single row can carry multiple artifacts.** `Ep\|Topic\|Study Guide ID\|Quiz ID` yields a
   study-guide *and* a quiz for that episode. Parser iterates every id-bearing column.
5. **`nlm studio status` has no titles.** It returns only `{id, type, status, custom_instructions}`.
   It is authoritative for *what exists* (reconciliation surfaces nlm-only artifacts) but titles
   must come from the sidecar; nlm-only artifacts render as `Untitled <type>`, never invented.

## Repo skeleton (matches the kickoff orientation)

```
backend/                  # FastAPI (Python 3.12 venv; system py is 3.9)
  app/
    main.py               # app factory, CORS for Vite origin, router includes, db init
    config.py             # NOTEBOOKLM_ROOT, data/cache paths, nlm allowlist
    models.py             # pydantic contract: Card, TopicDetail, CatalogResponse, AuthState…
    api/                  # catalog.py, topics.py, health.py, episodes.py (toggle)
    catalog/              # frontmatter.py, markdown_tables.py, sidecar.py, grouping.py, ingest.py, reconcile.py
    nlm/                  # client.py (ONLY shell-out; read-only allowlist), errors.py
    store/                # db.py (stdlib sqlite3), schema.py (future-proofed)
    quiz/                 # grading.py (offline oracle; Phase-2 contract locked now)
  data/                   # gitignored: learning-hub.sqlite + cache/
  tests/                  # parsing robustness, reconcile, read-only, auth, no-write, quiz oracle, api smoke
frontend/                 # Vite + React + TS + Tailwind + minimal PWA
  src/ api/ pages/ components/
Makefile + dev.sh         # one-command run
```

## Fork decisions (decided autonomously, with rationale)

**1. Frontend ↔ backend wiring → Vite dev-server proxy `/api` → `:8000` (Recommended).**
One origin in dev, zero env juggling, no CORS friction, a single `API_BASE = "/api"` constant.
(FastAPI still sets permissive CORS so LAN/PWA installs work.) Alternative `VITE_API_BASE` env
scatters URLs and complicates LAN access — rejected for Phase 1.

**2. Phase-1 catalog source → sidecar-first, with opt-in live `nlm studio status` reconcile (Recommended).**
Default `GET /api/catalog` and `/api/topics/{id}` parse sidecars only → fast, fully offline,
test-deterministic, no auth dependency on the hot path. `?live=true` triggers reconciliation
against `nlm studio status`, surfacing nlm-only artifacts and turning auth failure into a
friendly "run `nlm login`" banner (never a 500). `reconcile()` is a **pure function** tested with
fixtures — no network in tests. Alternative "always reconcile live" makes home depend on auth +
network and breaks offline tests — rejected.

**3. DB layer → stdlib `sqlite3` + hand-rolled schema/migration (Recommended).**
No SQLAlchemy weight for Phase 1. Schema is future-proofed for the mastery/spaced-rep engine
(attempts, per-question answers, episode progress, notes, custom topics, topic/question mastery,
activity for streaks). Phase 1 only writes `episode_progress` (the ✓ toggle) + an `activity`
row — enough to prove the hub-owned store and the zero-sidecar-write invariant.

## Backend ↔ frontend contract (the catalog JSON)

`GET /api/catalog` → `{ generated_at, auth:{ok,message?}, warnings:[], groups:[ {key,label,notebooks:[Card]} ] }`
- **Card**: `notebook_id, alias, title, group, template, tags[], archived, notebooklm_url,
  topic_url, counts:{audio,quizzes,study_guides,…}, progress_pct:null, mastery:null,
  due_for_review:false, last_touched:null` (the deferred fields are explicit `null` placeholders).

`GET /api/topics/{notebook_id}?live=false` → `TopicDetail`:
- `notebook_id, alias, title, group, template, tags[], archived, notebooklm_url, source_count?,
  episodes:[{n,title,artifact_id,format,length,listened}],
  study_guides:[{n?,title,artifact_id}],
  quizzes:[{n?,title,artifact_id,takeable:false}],   // player is Phase 2
  standalones:[{title,artifact_id,format,kind}],
  other_artifacts:[{type,title,artifact_id}],
  auth:{ok,message?}, warnings:[] }`

`POST /api/topics/{notebook_id}/episodes/{artifact_id}/listened` `{listened:bool}` → writes
SQLite only. `GET /api/health` → `{ok, nlm_version?}`.

## SQLite schema (future-proofed, Phase 1 lightly used)

`schema_migrations`, `episode_progress(notebook_id, artifact_id, listened, updated_at)`,
`attempts(id, notebook_id, quiz_artifact_id, started_at, finished_at, score, total)`,
`attempt_answers(attempt_id, question_index, chosen_index, correct, used_hint)`,
`notes(notebook_id, body, updated_at)`, `custom_topics(id, title, notes, progress_pct, …)`,
`topic_mastery(notebook_id, score, last_review_at)`,
`question_mastery(notebook_id, quiz_artifact_id, question_key, score, last_review_at)`,
`activity(day, notebook_id, kind)`.
Mastery decay + "Review next" will be a **pure, clock-injected scoring function** over these —
no `now()` inline — so it's unit-testable. Not built in Phase 1; schema leaves it a home.

## Read-only invariant (enforced boundary)

`app/nlm/client.py` is the only module that shells out. It runs through an allowlist:
first token ∈ `{studio, download, doctor, --version}`, and for `studio` the second token **must**
be `status`. Anything else raises `DisallowedCommandError` before any subprocess starts. Tested.
No code path opens a path under `NOTEBOOKLM_ROOT` for writing; an mtime-snapshot test proves a
full catalog refresh leaves the sidecar tree byte-for-byte unchanged.

## One-command run story

`make dev` (or `./dev.sh`):
1. create `backend/.venv` with `python3.12` (fallback `python3`) + install `requirements.txt` if missing,
2. `npm install` in `frontend/` if `node_modules` missing,
3. run `uvicorn app.main:app --port 8000` and `vite --port 5173` together (trap-kill both on exit).

Open **http://localhost:5173**. Backend on **:8000** (`/api/*`), proxied by Vite. `make test`
runs the backend pytest suite. Documented in the README.

## Phase-1 acceptance mapping

Every acceptance bullet from the kickoff maps to: live sidecar parse (not fixtures) → grouped
cards with both link types → topic detail with real episodes/study-guides/quizzes → graceful
degradation proven by tests (broken sidecar still renders; auth failure → friendly banner) →
SQLite initialized, zero sidecar writes (asserted) → backend smoke + offline quiz-oracle tests
green. Verified end-to-end by booting the app and driving the real UI.
