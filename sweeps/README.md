# Home Base — Milestone 0: the sweep quality week

**What this is.** M0 de-risks the whole Home Base project's killer assumption: *can an
autonomous sweep reliably catch what matters per topic, every morning, without hallucinated
or stale slop?* Two bad mornings and the daily-brief habit dies. So before any UI is built,
we run the sweeps by hand for ~5–7 days and grade them.

**Pipeline (since M1).** Prompts → `claude -p` with web search emitting **strict JSON** →
`render_brief.py` validates it and writes both `data/sweeps/<date>/<topic>.json` (what the
hub's `GET /api/brief` serves) and the gradeable `<topic>.md` (same shape as the M0 era —
your grading routine is unchanged). Invalid JSON never reaches the page: the raw output is
kept at `<topic>.raw.txt` and the run fails loudly for that topic. The grading week
continues exactly as before; if a topic's quality fails, we fix the source strategy before
trusting the page.

## The daily routine (~5 min)

```bash
make sweep          # runs the roster's active topics → data/sweeps/<today>/*.{json,md}
```

Then open today's folder and, for each brief, spend ~2 minutes grading it **A–F against
reality** in [`../docs/M0-sweep-grades.md`](../docs/M0-sweep-grades.md):

- **Miss?** Did it skip something that actually mattered in that topic today?
- **Slop?** Any hallucinated/broken links, fabricated numbers, or stale news dressed as new?
- **Padding?** Filler items on a quiet day instead of an honest "quiet today"?

On days you also read Morning Brew Daily, compare the market/tech brief against it and note
the overlap/gaps — that's the "better-than-generic" check.

## The topic roster (M2)

The roster lives in [`topics.json`](topics.json) — an ordered `[{slug, title, paused}]`
list that is both the sweep set (`sweep.sh` runs every unpaused topic) and the page's
titles + display order (`GET /api/brief`). To **add** a topic: add an entry + a
`prompts/<slug>.md` prompt. To **pause** one (offseason, noise, cost): flip `"paused": true`
— it stops getting swept but any already-swept day still renders. Edits apply on the next
sweep/request; no restart.

| Topic | Prompt | Notes |
|-------|--------|-------|
| AI / LLMs | [`prompts/ai-llms.md`](prompts/ai-llms.md) | M0 pilot — gates the go/no-go |
| Kansas City Chiefs | [`prompts/chiefs.md`](prompts/chiefs.md) | added in M2 |
| Boston Celtics | [`prompts/celtics.md`](prompts/celtics.md) | added in M2 |
| Indiana Hoosiers (FB + BB) | [`prompts/indiana.md`](prompts/indiana.md) | added in M2 — one brief, both programs |
| Kansas Jayhawks (BB) | [`prompts/kansas-basketball.md`](prompts/kansas-basketball.md) | added in M2 |
| St. Louis Blues | [`prompts/st-louis-blues.md`](prompts/st-louis-blues.md) | added in M2 |
| Fantasy football | [`prompts/fantasy-football.md`](prompts/fantasy-football.md) | M0 pilot — gates the go/no-go; seasonal, pause via `topics.json` |
| Market & tech news | [`prompts/market-tech-news.md`](prompts/market-tech-news.md) | M0 pilot — gates the go/no-go |

The M0 go/no-go still rides on the **3 pilot topics**; the 5 added topics don't gate it.
Heads-up on runtime: each topic takes ~4 minutes on Opus, so the full 8-topic sweep runs
~30 minutes sequentially (scheduling/parallelism is M3 territory).

Tune a prompt anytime — that's the point of the week. Note tweaks in the grades log so the
go/no-go reflects the final prompts.

## Options

```bash
TOPIC=ai-llms make sweep        # run a single topic (works even if it's paused)
SWEEP_MODEL=sonnet make sweep   # try a cheaper/faster model and compare quality
```

## Billing & auth

Sweeps run on **your Claude subscription** via `claude -p` (the lane chosen at kickoff) — no
API key, no per-run dollar charge. ⚠️ If you have `ANTHROPIC_API_KEY` exported in your shell,
Claude Code may use **API billing** instead; `unset ANTHROPIC_API_KEY` to stay on the
subscription. Default model is Opus; `SWEEP_MODEL` overrides.

## The go/no-go gate

After ~5–7 days: if the pilot topics are consistently trustworthy (mostly A/B, no recurring
hallucination), **go** → build M1 (the brief page). If there are persistent misses or slop on
a topic, **stop and rethink that topic's source strategy** before building any UI. Raw briefs
live in `data/sweeps/` (gitignored — regenerable, local-only); the durable record is your
grades log.
