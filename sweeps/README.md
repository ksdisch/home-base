# Home Base — Milestone 0: the sweep quality week

**What this is.** M0 de-risks the whole Home Base project's killer assumption: *can an
autonomous sweep reliably catch what matters per topic, every morning, without hallucinated
or stale slop?* Two bad mornings and the daily-brief habit dies. So before any UI is built,
we run the sweeps by hand for ~5–7 days and grade them.

**No UI, no backend, no ingest yet.** Just prompts → `claude -p` with web search → markdown
briefs in a folder → your 2-minute grade. If quality passes, M1 builds the brief page on top
of these exact (by then, tuned) prompts. If it fails, we fix the source strategy cheaply
before investing in an interface.

## The daily routine (~5 min)

```bash
make sweep          # runs all 3 pilot topics → data/sweeps/<today>/*.md
```

Then open today's folder and, for each brief, spend ~2 minutes grading it **A–F against
reality** in [`../docs/M0-sweep-grades.md`](../docs/M0-sweep-grades.md):

- **Miss?** Did it skip something that actually mattered in that topic today?
- **Slop?** Any hallucinated/broken links, fabricated numbers, or stale news dressed as new?
- **Padding?** Filler items on a quiet day instead of an honest "quiet today"?

On days you also read Morning Brew Daily, compare the market/tech brief against it and note
the overlap/gaps — that's the "better-than-generic" check.

## Pilot topics (fixed for M0)

| Topic | Prompt |
|-------|--------|
| AI / LLMs | [`prompts/ai-llms.md`](prompts/ai-llms.md) |
| Fantasy football | [`prompts/fantasy-football.md`](prompts/fantasy-football.md) |
| Market & tech news | [`prompts/market-tech-news.md`](prompts/market-tech-news.md) |

Tune a prompt anytime — that's the point of the week. Note tweaks in the grades log so the
go/no-go reflects the final prompts.

## Options

```bash
TOPIC=ai-llms make sweep        # run a single topic
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
