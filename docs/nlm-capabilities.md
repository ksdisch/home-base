# `nlm` capabilities — VERIFIED

Everything here was confirmed live against real data during kickoff (engineering-abstractions
notebook). Do **not** re-derive — build on it. `nlm` is the NotebookLM CLI; it's also exposed
as an MCP server (`mcp__notebooklm-mcp__*`). Prefer the CLI for downloads; either works.

- **Installed:** `nlm` v0.5.15 at `/Users/kyledisch/.local/bin/nlm` (on PATH).
- **Auth:** uses cached Google tokens. On auth errors the user runs `nlm login` (only they can —
  it's an interactive browser flow). `refresh_auth` only reloads cached tokens. The hub must
  detect auth failures from `nlm` exit codes/stderr and surface a clear "run `nlm login`" message.

## The headline capability — quizzes download WITH answers ✅

```bash
nlm download quiz <NOTEBOOK_ID> --id <ARTIFACT_ID> -f json -o out.json
```

Returns clean JSON. Verified shape (a real 10-question quiz — see `fixtures/sample-quiz.json`):

```jsonc
{
  "title": "Ep 1 — Quiz",
  "questions": [
    {
      "question": "…",
      "answerOptions": [
        { "text": "…", "isCorrect": true,  "rationale": "why this is right…" },
        { "text": "…", "isCorrect": false, "rationale": "why this is wrong…" }
      ],
      "hint": "…"
    }
    // …
  ]
}
```

Verified invariants on the sample:
- 10 questions; every question has `question` + `answerOptions`.
- **Exactly one** option per question has `isCorrect: true`.
- **Every** option has a `rationale` (use it for the post-answer explanation screen).
- **Every** question has a `hint` (offer on demand in the player).
- Option counts vary (mostly 4, one was 2) — don't hardcode 4.

This is a complete feed for an in-hub quiz engine: render questions, let the user pick,
auto-grade against `isCorrect`, show `rationale` on review, store the attempt.
`-f json|markdown|html` supported; use `json`.

## Other downloads (same pattern, `nlm download <type>`)
| Type | Command | Output | Hub use |
|---|---|---|---|
| Quiz | `nlm download quiz <nb> --id <id> -f json` | JSON (above) | Quiz player |
| Report (study guide) | `nlm download report <nb> --id <id>` | Markdown | Render study guides inline |
| Flashcards | `nlm download flashcards <nb> --id <id>` | JSON | Future flashcard review |
| Mind map | `nlm download mind-map <nb> --id <id>` | JSON | Optional topic map view |
| Audio | `nlm download audio <nb> --id <id>` | audio file | Optional offline playback |
| Slide deck / infographic / data-table | `nlm download <type> …` | PDF/PNG/CSV | Optional |

`--id` targets a specific artifact; without it, defaults to a type's artifact in the notebook.

## Discovery — list artifacts per notebook
```bash
nlm studio status <NOTEBOOK_ID>
```
Lists all studio artifacts and their status/type/ID. Use it to discover new episodes/quizzes
beyond what the sidecar records. Note (from the audio-series skill): the MCP `studio_status`
returns the **whole notebook** and gets large — filter with `jq` on a persisted file.

## What is NOT possible (don't design around it)
- **No "did I listen" signal** for audio — episode-listened must be a manual ✓ in the hub.
- **Quiz attempts taken inside NotebookLM are not retrievable** — the hub is the home for quiz-taking.
- The hub should treat NotebookLM as **read-only**; never mutate notebooks from the hub.

## Top-level `nlm` command surface (for reference)
`login · notebook · note · source · chat · studio · research · alias · config · download ·
share · export · tag · audio · report · quiz · flashcards · batch · cross · pipeline · doctor`
