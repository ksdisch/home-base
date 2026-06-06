---
name: review-next
description: >-
  Suggest what to review next in the Learning Hub by reading the local progress store (attempts,
  per-question and per-topic mastery, reflections) and ranking the shakiest material. A
  lightweight, read-only "Review next" planner that works today; the Phase-4 mastery-decay
  engine will eventually supersede its ranking heuristic. Use when the user asks "what should I
  review", "what's due", "what am I weak on", "where should I focus", or runs /review-next.
---

# Review next — study planner (read-only)

Produce a ranked "what to review next" list from the hub's own SQLite store. This is the
lightweight version of the deferred study-planner in BACKLOG.md — it ranks from the latest
logged signal rather than a decay model. **It only reads. Never write to the store here.**

## Where the data lives

The store is local SQLite at `backend/data/learning-hub.sqlite` (override: `LEARNING_HUB_DATA`).
Relevant tables (see `backend/app/store/schema.py`):

- `attempts` / `attempt_answers` — graded quiz attempts.
- `question_mastery` — per-question `score`, `miss_count`, `last_review_at`.
- `topic_mastery` — per-notebook `score`, `last_review_at`.
- `reflections` — post-episode reflections with optional `grasp_rating` (1–5).
- `episode_progress` — which episodes are marked listened.

## How to read it (two ways, prefer whichever is available)

1. **SQLite MCP (preferred when present).** This repo ships a `learning-hub-db` MCP server
   (`.mcp.json`) pointed at the store. Use its read/query tools to run the SELECTs below. If the
   server isn't connected (e.g., a cloud session, or the DB hasn't been created yet), fall back.

2. **Read-only via the project venv** (fallback). Run a SELECT-only snippet from `backend/`:

   ```
   cd backend && .venv/bin/python -c "
   import json; from app.store.db import connect
   c = connect()
   rows = [dict(r) for r in c.execute('''<SELECT ...>''').fetchall()]
   print(json.dumps(rows))
   "
   ```

   `app.store.db.connect()` resolves the configured path and returns `sqlite3.Row`s. **Only
   SELECTs** — no INSERT/UPDATE/DELETE from this skill.

If the DB file doesn't exist yet, there's nothing logged — say so and suggest running an
`/episode-review` quiz first.

## Ranking heuristic (until Phase 4)

Pull these signals and weave them into one ranked list (highest priority first):

1. **Most-missed questions** — the sharpest signal:
   `SELECT notebook_id, quiz_artifact_id, question_key, score, miss_count, last_review_at
    FROM question_mastery WHERE miss_count > 0
    ORDER BY miss_count DESC, score ASC, last_review_at ASC LIMIT 15`
2. **Stalest / weakest topics** — overdue or low-scoring notebooks:
   `SELECT notebook_id, score, last_review_at FROM topic_mastery
    ORDER BY (last_review_at IS NULL) DESC, last_review_at ASC, score ASC`
3. **Self-flagged shaky spots** — recent low-grasp reflections:
   `SELECT notebook_id, episode_artifact_id, grasp_rating, body, created_at FROM reflections
    WHERE grasp_rating IS NOT NULL AND grasp_rating <= 2 ORDER BY created_at DESC LIMIT 10`

Resolve `notebook_id` to a human title where you can (GET `localhost:8000/api/topics/<id>` if
the backend is running, else show the id). `question_key` is the stable per-question identity;
if you can map it to question text via cached quiz JSON, do — otherwise report the key.

## Output

A short, calm, prioritized list — not a data dump. For each item:

- **What** to review (topic title + episode/quiz, or specific question theme).
- **Why** it surfaced (e.g., "missed 3×, last seen 9 days ago", "you rated your grasp 2/5").
- **A concrete next step** (e.g., "re-take the Ep 4 quiz", "re-listen to Ep 2, then /episode-review").

End by offering to kick off the highest-leverage item via `/episode-review`.

## Guardrails

- **Read-only.** This skill never mutates the store — SELECTs only.
- Don't invent progress. If a table is empty, say there isn't enough history yet.
- This is a personal learning loop — keep it encouraging, not a scoreboard.
- **Local-only in practice:** the store lives on the user's machine, so this won't return data
  in a cloud session without the DB present.
- When the Phase-4 mastery-decay scoring function exists, prefer it over this heuristic.
