# M5 Plan — Chat with the brief (ask follow-ups on Today)

_Status: ✅ shipped 2026-07-16 (PR #47) · verified the same day — 340 backend tests green
and a live end-to-end question against the real 2026-07-16 brief (grounded answer in 13.1s,
$0.073 equiv on sonnet, ledger row written). Picked 2026-07-16 together with M4 (Kyle chose
both from the post-M3 menu; audio went first), then approach **A** from M5's own
`/explore-plan` fork: per-item Ask, no web tools, ephemeral answers + save-as-note._

## The decided forks (don't relitigate)

### 1. Per-item single answer — not a topic conversation panel
Each brief item gets an "Ask about this" affordance in its action row; one question → one
grounded answer. A multi-turn transcript panel (approach C) was considered and deferred:
it's most of the design surface (state, persistence, growing context per turn) for an
unproven need. If single-shot feels cramped in practice, the transcript is an upgrade on
this plumbing, not a rework.

### 2. No web tools — grounded in the served item, honestly
The chat call whitelists **no tools** (`-p` auto-denies the rest — the M3 sweep finding) and
the prompt says so: answer from the item + general knowledge, be explicit about uncertainty,
and if the question needs fresher info than the brief, say that instead of guessing. This
keeps the trust surface at **zero new un-graded prompts** during the M0 grading week and
keeps answers cheap/fast (~$0.05–0.15 equiv, 5–20s on sonnet). The web-enabled "dig deeper"
toggle (approach B, ~$0.5–1.5 and 30–90s per question) is the noted later upgrade — the same
deferral pattern as M4's radio-host pass.

### 3. Subscription lane, enforced by scrubbing — not by refusing
`app.chat._scrubbed_env()` pops `ANTHROPIC_API_KEY` from the child env, so a stray exported
key can never silently flip a question onto metered API billing. Chat scrubs rather than
refuses (sweep.sh refuses; run-scheduled.sh unsets): a background pipeline can afford to
stop loudly, an interactive button shouldn't fail because of an unrelated shell export.

### 4. Ledger under backend data — `data/sweeps` stays read-only
Every exchange (including failures) appends to `<data_dir>/brief-chat.jsonl`
(`backend/data/`, gitignored). Deliberately NOT under `data/sweeps/` — the backend is
strictly read-only there, and chat is a backend feature. Ledger writes are best-effort:
observability must never eat an answer.

### 5. Ephemeral answers + save-as-note — no new storage
Answers live in component state only. "Save as note" posts `**Q:** …\n\n**A:** …` through
the **existing** `POST /api/brief/notes`, so a keeper appends to the item's note list live,
shows on `/notes`, and outlives the regenerable sweep files — zero new tables/migrations.

### 6. The date-scoped item id is the staleness guard
Ids are `sha1(date|slug|headline)` (M2), so a question from yesterday's stale tab simply
doesn't resolve on today's served day → honest 404 ("reload"), never an answer against the
wrong morning. No extra date plumbing needed.

### 7. Test seam mirrors NlmClient
`BriefChatClient(runner=…)` + `deps.get_brief_chat_client` dependency override — tests never
spawn a real `claude`. Model/binary come from settings (`BRIEF_CHAT_MODEL`, default
`sonnet`; `CLAUDE_BIN`).

## The slice

```
backend/app/chat.py                   NEW — BriefChatClient (headless claude -p, json
                                      envelope parse, typed BriefChatError), build_prompt
                                      (honesty rules + the served item verbatim),
                                      append_chat_ledger, _scrubbed_env
backend/app/api/brief.py              POST /brief/chat — 400 empty/oversized question ·
                                      404 no sweeps / item not on the served day · 502 with
                                      an error ledger row when claude fails
backend/app/config.py                 claude_bin · brief_chat_model · brief_chat_ledger
backend/app/deps.py                   get_brief_chat_client (override point for tests)
backend/app/models.py                 BriefChatRequest / BriefChatResponse
frontend/src/api/{types,client}.ts    hand-synced request/response + api.briefChat
frontend/src/pages/Brief.tsx          "Ask about this" in the item action row: composer →
                                      thinking state (~10–20s note) → Markdown answer card →
                                      Save as note (appends live) · "no live web" caption
```

## Deliberately NOT in M5
- **No web tools** (approach B — later toggle) and **no multi-turn transcript** (approach C).
- **No streaming** — a 5–20s single answer with a thinking state is fine at this size;
  `--output-format stream-json` + SSE is the latency upgrade if it ever isn't.
- **No chat persistence table** — save-as-note is the durability story until proven thin.
- **No per-request model switching / rate caps** — single-user laptop, manually clicked;
  `BRIEF_CHAT_MODEL` env covers experimentation.

## Verification
- 10 new backend tests (340 total green): prompt actually carries the item + question +
  honesty framing (args captured off the injected runner) · success + error ledger rows ·
  400s never invoke the runner · unknown/stale-day item ids 404 (the date-scope guard,
  tested against a real rollover) · error envelope + unparseable stdout → 502 · chat writes
  nothing under the sweeps dir · env scrub drops the API key.
- `make typecheck` · frontend vitest 32/32 · `ruff check` clean.
- **Live e2e (2026-07-16):** real TestClient against the real day dir (read-only) + real
  `claude -p` on the subscription lane — asked about the Ode item, got a grounded 2-sentence
  answer in 13.1s, $0.073 equiv, correct ledger row in a temp data dir. Note: the envelope's
  raw `input_tokens` (3) excludes cache reads, same quirk as the sweep ledger —
  `total_cost_usd` is the trustworthy number.
