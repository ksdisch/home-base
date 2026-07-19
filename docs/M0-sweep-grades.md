# M0 — Sweep quality week: grades

The go/no-go log for [Milestone 0](KICKOFF-home-base.md). Each morning after `make sweep`,
spend ~2 minutes grading each topic's brief **A–F against reality**. This log — not the raw
briefs (which are gitignored) — is the durable evidence for the go/no-go decision. See
[`../sweeps/README.md`](../sweeps/README.md) for the routine.

**Grade key:** **A** = caught everything that mattered, zero slop · **B** = solid, minor
gap · **C** = usable but missed something real or padded · **D** = mostly noise/misses ·
**F** = hallucinated, stale, or useless. A **quiet day honestly reported** is an **A**, not a
low grade.

**Kill criteria:** persistent misses or slop on a pilot topic → stop and rethink that topic's
source strategy before building any UI.

## Log

Copy the three-row block each morning and fill it in. `Miss?` = what it failed to catch ·
`Slop?` = hallucinated / broken / stale · `Notes` = anything to tune in the prompt.

> **2026-07-13 = Claude Day-0 audit** (source-verified first pass, _not_ a human grade): each
> item's cited URLs were fetched or independently cross-searched. Across ~12 items / ~24 sources —
> **zero hallucinated events, zero dead/fabricated links** (CNBC/IG/Bloomberg returned 403 to direct
> fetch, but every story was confirmed via independent search). Verification was thorough but not
> exhaustive; a few secondary stats and the oldest fantasy item weren't independently re-confirmed.
> Your own morning grades are the real signal — this is a sanity-check baseline.

| Date | Topic | Grade | Miss? | Slop? | Notes / prompt tweaks |
|------|-------|:-----:|-------|-------|-----------------------|
| 2026-07-13 | AI / LLMs | A− | None fresh — GPT-5.6 Sol & Meta Muse Spark 1.1 both launched Jul 9, outside the 24h window (correctly excluded) | None — 3/3 items verified real; Gemini specs correctly labeled "leak-grade until Google posts it" | Zero hallucination + exemplary epistemic honesty. Backdrop slot went to the 3-day-old Apple suit; could've flagged Meta Muse Spark 1.1 (Jul 9 coding API) for a builder. Tune: on quiet days, prefer recent builder-relevant releases as backdrop. |
| 2026-07-13 | Fantasy football | A | None — verified genuinely quiet (no hard transactions/injuries broke in 24h) | None — JT quotes + stats exact (323 carries · 46% of touches · 80%+ snaps); Skattebo & Helm confirmed | Honest quiet-day handling, no padding. Items skew 1–6 days old but transparently dated; item 4 (Cook, Jul 7) sourced but not re-verified. Watch: prioritize fresh breaks on busy days. |
| 2026-07-13 | Market / tech news | A | None — independent search surfaced the same lead stories | 2 soft numeric slips (SK Hynix ADR premium ~37% vs ~25.6% found; Micron/Sandisk %s unconfirmed) | Index closes + oil %s exact; SK Hynix crash, Apple-OpenAI suit, June-CPI/bank previews all confirmed. Watch secondary-stat precision. |
| 2026-07-15 | AI / LLMs | B+ | None flagged | None flagged | Kyle's first grade on the full 8-topic roster — blanket **B+ across all 8** ("everything from today looks great; B+ because there's always room for improvement"). No specific miss/slop called out on any topic; no prompt tweaks requested. |
| 2026-07-15 | Fantasy football | B+ | None flagged | None flagged | (blanket B+ — see AI/LLMs row) |
| 2026-07-15 | Market / tech news | B+ | None flagged | None flagged | (blanket B+ — see AI/LLMs row) |
| 2026-07-15 | Chiefs | B+ | None flagged | None flagged | (blanket B+ — non-gating) |
| 2026-07-15 | Celtics | B+ | None flagged | None flagged | (blanket B+ — non-gating) |
| 2026-07-15 | Indiana (FB+BB) | B+ | None flagged | None flagged | (blanket B+ — non-gating) |
| 2026-07-15 | Kansas basketball | B+ | None flagged | None flagged | (blanket B+ — non-gating; honest 1-item quiet day) |
| 2026-07-15 | St. Louis Blues | B+ | None flagged | None flagged | (blanket B+ — non-gating) |
| 2026-07-16 | AI / LLMs | B+ | **Thinking Machines' Inkling** (Murati's first model, 975B open-weight, launched Jul 15 — in-window) despite the brief claiming "no net-new flagship models"; S. Korea's $880B national AI plan + Apple's Siri AI beta were arguable skips | None — Ode JV, Emergent round, Bonsai 27B all verified exact | Items 100% accurate; the gap is inclusion judgment, not fabrication. The sweep itself dated Inkling to Jul 15 when it finally covered it on 07-18. |
| 2026-07-16 | Fantasy football | A− | Kamara restructure agreement (broke Jul 15; covered well the next day) | None — Pickens tag details + ESPN WR poll order/placements all exact | Honest quiet-day handling continues. |
| 2026-07-16 | Market / tech news | A− | None | One soft slip: "JPMorgan profit +41% YoY" vs the reported +17.2% EPS growth | Closes, June CPI, Goldman $20.98 EPS, oil settles all exact — the Day-0 "secondary-stat precision" watch item again. |
| 2026-07-17 | AI / LLMs | B+ | **Bloomberg's Jul 16 Gemini-delay exclusive** (GOOGL −4.4%, ~$200B erased) — ran the stale Jul-13 "launching today" rumor as its watch item instead, while the same morning's market brief carried the real story 23 minutes later | None — Kimi K3 verified in full (2.8T MoE, KDA, $3/$15 pricing, weights Jul 27) | Cross-topic incoherence: per-topic sweeps share no context, and the market prompt out-sourced the AI prompt on AI-lab news. |
| 2026-07-17 | Fantasy football | A | None | None — Kamara numbers exact ($6M base / $8.5M max / $5.5M cap savings) | Exemplary honest dating throughout (Taylor + Dell threads explicitly marked "earlier this week, not today"). |
| 2026-07-17 | Market / tech news | A | None | None | Six items, every number verified (Netflix guidance to the decimal, PayPal $60.50 bid, Hormuz transit −62%, TSMC $100B Arizona) — strongest single sweep of the week. |
| 2026-07-18 | AI / LLMs | B− | — | **Deliberately dropped the Gemini-delay story with a false rationale** ("traces only to low-quality blogs recycling a month-old talent exodus" — it was a Bloomberg exclusive echoed by CNBC/Seeking Alpha/US News); "behind only Claude Fable 5" dropped GPT-5.6; unverifiable "732-point Elo jump" | Worst epistemic moment of the week — confidently dismissing a true, market-moving story is more corrosive to trust than missing one. Prompt tune applied same day (see verdict). |
| 2026-07-18 | Fantasy football | B+ | — | **Aiyuk mischaracterized as injury murkiness** when the live story is a contract walkout (fired agent, reserve/left-squad list, refuses reinstatement, wants Washington) | Camp report dates, the Chiefs Demercado-vs-Emmett-Johnson battle, and Pickens' 93/1,429/9 line all verified exact. |
| 2026-07-18 | Market / tech news | A | None | Trivial: "~2.7T params" for Kimi K3 (it's 2.8T) | SOX −5.7% intraday / 20.2% below the Jun-22 record / $3.3T erased / 105% prior rally, oil $88.10 / $82.49, Netflix guidance — all exact. |

> **Prompt/format tweak — 2026-07-13 (post-Day-0, M1):** sweep output switched from direct
> Markdown to **strict JSON + deterministic renderer** (`sweeps/render_brief.py`) so the M1
> brief page can ingest it (see `docs/M1_PLAN.md`). The gradeable `.md` files keep the same
> shape and filenames; grades from 2026-07-14 onward reflect the JSON-emitting prompts.

> **Roster expansion — 2026-07-14 (M2):** the roster grew from the 3 pilots to the full
> 8 topics via `sweeps/topics.json` + 5 new prompts (Chiefs · Celtics · Indiana ·
> Kansas BB · Blues). **The M0 go/no-go still rides on the 3 pilot topics only** — grade
> the new ones too if useful, but they don't gate. Full-roster sweeps take ~30 min.

> **First full-roster sweep — 2026-07-15 (Claude-run, source-verified first pass — _not_ a
> human grade):** the M2 roster's first production run swept all 8 topics end-to-end
> (`./sweep.sh`, opus, ~25 min wall-clock). **Result: 8/8 topics wrote valid `.json` + `.md`,
> zero `.raw.txt` validation failures, runner exit 0** — the config-file roster + JSON→renderer
> pipeline works across the whole lineup, and it ran cleanly from a cloud session (nested
> `claude -p` with web search). Sanity scan (source-appropriateness + internal consistency;
> lighter than Day-0's fetch/cross-search audit): every item carries ≥1 real `http(s)` source,
> all domains are topic-appropriate beat/major outlets (CelticsBlog, Inside the Hall / The Daily
> Hoosier, Through the Phog, Arrowhead Pride, The Hockey News, NHL/NBA/NFL.com, CNBC,
> federalreserve.gov …) — no fabricated-looking or non-http URLs. Mid-July is deep offseason for
> the 5 sports topics and each brief handled it honestly: 2–4 items apiece, no padding, fresh
> items dated and explicitly separated from recent-week context. Indiana correctly delivered
> **one** brief covering FB + BB with program-led headlines. The 4 first-time-live prompts
> (Celtics · Indiana · Kansas BB · Blues; Chiefs was trialed once on 7-14) all ran clean —
> **no prompt tuning was needed this run.** A–F grades below are Kyle's; the go/no-go still rides
> on the 3 pilots (today's `ai-llms` / `fantasy-football` / `market-tech-news` briefs are ready
> to grade in `data/sweeps/2026-07-15/`).

> **2026-07-16 → 07-18 = Claude source-verified audit (run 2026-07-19), grades adopted by
> Kyle:** every load-bearing claim in the 9 pilot briefs was independently cross-searched
> (~30 targeted searches). **Zero fabricated items, zero fabricated-looking sources across
> the entire week** — every included story was real, and the market topic was repeatedly
> exact to the decimal. The misses/slop above are judgment failures (inclusion, sourcing
> assessment, framing), not hallucination. Kyle reviewed the evidence and adopted the
> suggested grades unchanged on 2026-07-19.

## Final verdict — 2026-07-19: **PASS** (go), with one AI prompt tune

The go/no-go rode on the 3 pilot topics. Kill criteria were "persistent misses or slop."

- **Market / tech news: PASS, outstanding** (A / A− / A / A / B+ blanket). Hard numbers
  verified exact day after day; honest context notes about window freshness. The only
  recurring watch item is secondary-stat precision (SK Hynix premium Day 0, JPM profit
  07-16) — no action needed.
- **Fantasy football: PASS, strong** (A / B+ / A− / A / B+). Honest quiet-day handling
  through the dead offseason, transparent dating of older threads, exact contract/stat
  numbers. One framing slip (Aiyuk, 07-18). No prompt change.
- **AI / LLMs: PASS with a tune** (A− / B+ / B+ / B+ / B−). Accurate on everything it
  *includes* (zero fabrication all week) but the weak leg on **editorial judgment**: missed
  the in-window Inkling launch (07-16), ran a stale rumor over Bloomberg's Gemini-delay
  exclusive (07-17), then dismissed that same true story with a false "low-quality blogs"
  rationale (07-18) — while the *market* sweep handled the identical story perfectly.
  **Tune applied 2026-07-19** (`sweeps/prompts/ai-llms.md`): before *dismissing* a trending
  story on sourcing grounds, the sweep must check top-tier wires (Bloomberg/Reuters/CNBC/AP)
  for an original report, and must prefer include-with-caveats over silent/justified drops
  for market-moving lab news. Exclusion now carries the same sourcing bar as inclusion.

**Not persistent-miss/slop territory:** the failures cluster on one story-thread in one
topic and were judgment, not fabrication; the morning-habit trust contract (never lie to
Kyle at breakfast) held all week. **M0 is closed. The sweeps are trustworthy enough to
carry the habit.** Watch item going forward: the per-topic sweeps share no context — the
market prompt out-covered the AI prompt on AI-lab news twice; if that repeats post-tune,
consider a cross-topic coherence pass (backlog idea, not committed work).
