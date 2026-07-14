# M1 Plan — The Brief Page ("Today")

_Status: in progress on `feat/m1-brief-page`. Kickoff M1 spec: "New home route rendering
stored sweeps: topic sections, digests, sources, as-of stamp; manual refresh command; visit
log. Existing hub home → 'Learning' tab." Kyle explicitly chose to start M1 mid-M0 (only
Day-0 grades exist) — deliberate override, noted in writing._

## The fork that was decided first

M0 deliberately emitted **human-gradeable Markdown**; a React page needs machine-readable
data. Options were (a) prompts emit JSON, (b) backend parses the Markdown, (c) render raw
Markdown and defer structure. **Kyle picked (a) — JSON emission** — because:

- **Validation moves to write time and fails loudly.** A Markdown parser fails at *read*
  time, silently mis-rendering the page whose entire job is being trustworthy. Day-0 output
  already drifted from the spec (interstitial "Note on the window" paragraph, multi-publisher
  headings, date ranges) — and `sweeps/README.md` explicitly encourages prompt tuning all
  week, so a parser's target never stops moving.
- **The grading loop is untouched in substance.** The routine is "open
  `data/sweeps/<date>/*.md`, grade in `docs/M0-sweep-grades.md`". A deterministic renderer
  keeps writing those exact `.md` files from the validated JSON — same filenames, same
  shape. The format switch is noted in the grades log per the README's tuning convention.
- **M2 needs item structure anyway** (inline notes attach to brief *items*), and the kickoff
  scope already names "structured JSON → hub ingest".

## The slice

```
sweeps/prompts/*.md      →  emit ONE strict JSON object (top_line, context_note?, items[])
sweep.sh                 →  claude -p → sweeps/render_brief.py (stdlib) validates + writes
                            <topic>.json (hub ingest) AND <topic>.md (gradeable view);
                            invalid JSON → <topic>.raw.txt + loud per-topic failure
backend                  →  SWEEPS_DIR setting (default <repo>/data/sweeps, env-overridable)
                            app/sweeps.py ingest: latest date dir; JSON topics; md-only or
                            invalid-JSON days degrade to raw_markdown fallback (never a
                            silent drop)
                            GET /api/brief · POST /api/brief/visit
                            brief_visits table (schema v4) — NOT the activity table, which
                            feeds learning streaks
frontend                 →  pages/Brief.tsx = "Today" at "/" (topic sections · item cards ·
                            as-of stamps · stale hint · raw-Markdown fallback via the
                            existing dep-free Markdown component); logs a visit on mount
                            pages/Home.tsx → "/learning" as the "Learning" tab; brand →
                            "Home Base"; 4 internal links that assumed "/" = catalog fixed
                            types.ts + client.ts hand-sync (contract-reviewer pass at end)
```

## Item JSON contract (what the model emits)

```json
{
  "top_line": "One-sentence summary of the day for this topic.",
  "context_note": "Optional short honesty paragraph (news-window caveats) or null.",
  "items": [
    {
      "headline": "…",
      "attribution": "Publisher(s), publish date — free string, exactly as the old heading",
      "digest": "2–4 sentences.",
      "why_it_matters": "1–2 sentences, specific to Kyle.",
      "sources": [{ "title": "short title", "url": "https://…" }]
    }
  ]
}
```

The runner wraps it with `topic`, `date`, `as_of` before writing `<topic>.json`. Every item
must carry ≥1 real source URL (the M0 hard rule) — the renderer *enforces* this and fails the
topic loudly rather than letting an unsourced item reach the page.

## Deliberately NOT in M1

- **No refresh button / no scheduling** — `make sweep` (shipped in M0) *is* the manual
  refresh command; the page shows an honest as-of stamp and a "run `make sweep`" hint when
  stale. Scheduling is M3.
- **No topic roster config** — title map hardcoded for the 3 pilots (+ humanize fallback);
  the config-file roster is M2.
- **No visit-log read UI** — M1 writes visits (the habit metric); reading happens via
  sqlite / the `learning-hub-db` MCP until a later milestone surfaces it.
- **No item ids** — M2 adds stable item identity when notes need anchors.

## Verification

Backend pytest against synthetic `SWEEPS_DIR` dirs (JSON day, md-only legacy day, malformed
JSON fallback, latest-date pick, visit insert) + renderer tests (valid, fenced, invalid →
raw). Frontend vitest for the Today page. `make test` · `make test-frontend` ·
`make typecheck` · `make lint` all green before merge. First *live* JSON sweep happens with
the next `make sweep` — watch the renderer's per-topic failure output that morning.
