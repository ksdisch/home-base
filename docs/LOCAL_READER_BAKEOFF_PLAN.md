# Local Reader Bake-Off — plan (awaiting approval)

_Status: **PLAN ONLY — no code written.** Produced by the `/explore-plan` step following the
2026-07-27 gate conversation that gave Free-Inference Rebuild a go (decision D8). Vision doc:
[`ideas/free-inference-rebuild.md`](ideas/free-inference-rebuild.md). Nothing in this plan is
implemented until Kyle approves an approach below._

## What this is

A graded, zero-user-facing bake-off that answers exactly one question:

> Can a small local model, given one day's sweep artifact and an open-ended natural-language
> reshape request, return a **correct selection and ordering of items** — reliably enough,
> for a full week, to earn a read-time surface?

## What this is not

Not a feature. Not a UI. Not a crossing of assumption 2. The verdict table is the entire
deliverable; `Brief.tsx` is untouched. Assumption 2 is crossed only by a *second* decision,
after a passing graded week — per the recorded scope.

## Recorded scope from the gate (not up for re-litigation)

1. **Ids-only, never prose.** The model emits no text. Fabrication is removed structurally,
   not detected after the fact.
2. **Ollama + a small instruct model** takes the first slot. Wired behind the existing
   `chat.py` `Runner` seam so MLX can take a later one without a rewrite.
3. **Lens beside the fixed brief**; default status must be earned via its own graded record
   plus a gate conversation.
4. **Offline degrades to the fixed brief**, never errors.

---

## Two corrections to the vision doc's "credible first step"

Both were found while grounding this plan, and both change the shape of the work. They are
recorded here rather than silently worked around.

### Correction 1 — the replay corpus does not exist

The vision doc proposes replaying "real questions from `backend/data/brief-chat.jsonl`."
**That file does not contain questions.** `append_chat_ledger()` in `backend/app/chat.py:208`
writes a usage row only:

```
ts · brief_date · topic · item_id · model · is_error ·
total_cost_usd · duration_ms · input_tokens · output_tokens   (+ error)
```

No `question` field, no `answer` field — by design; it is a cost/observability ledger, not a
transcript. So there is no corpus of real questions to replay, and the doc's "fallback
fixture set" is in fact the **only** available corpus.

Second-order point that matters more: even if the questions existed, **they are the wrong
task.** M5 chat questions are per-item ("tell me more about *this*"). A reshape request
operates over a whole day's brief ("just the Chicago stuff", "brief me in 90 seconds").
Grading one against the other would not have measured the thing being gated. The fixture
suite isn't a consolation prize — it's the correct instrument.

### Correction 2 — item ids are derived at read time, and are sha1 prefixes

`backend/app/sweeps.py:164` derives each id as `sha1(date|slug|headline)[:12]`, with a
`-2`/`-3` suffix for duplicate headlines. Ids are **not stored** in the sweep JSON. Two
consequences:

- The bench must obtain items via the backend's own `load_brief_topics()`, not by parsing
  raw JSON, or its ids won't match what the UI serves.
- **Asking a small model to transcribe 12-hex-char sha1 prefixes is a needless failure
  mode.** A single flipped character is an invalid id, and we would be measuring
  transcription accuracy instead of selection quality.

**Mitigation (proposed):** present the day's items to the model as **ordinal indices
`1..N`**, and map indices back to real ids deterministically in Python. This *strengthens*
the ids-only guarantee rather than weakening it — the model's output type becomes a list of
small integers, any out-of-range or duplicate integer is dropped mechanically, and there is
still no channel through which a new claim can enter. It also makes the "no invented ids"
check trivially exact.

---

## Ranked approaches

### A. Hand-authored fixture suite over real sweep days — **recommended**

Author ~20–30 reshape requests spanning the request classes that matter (filter by
place/topic, drop-what-I've-seen, compress-to-N, combinations, and deliberately impossible
requests that should return empty). For each, pair it with a real `data/sweeps/<date>/` day
and a **gold selection**: the ids that must appear, the ids that must not, and where
ordering is scored.

- **Why it wins:** it is the M0 method applied to a new question — a stated bar, real data,
  a written verdict table. It grades the actual task. It can run today; nothing has to
  accrue first. And the gold sets are reusable forever, including against MLX later.
- **Cost:** the authoring sitting is the real expense, and it's Kyle's — the gold sets encode
  *his* judgment about what a request should return. That is a feature (the bar is his), but
  it is not delegable to a cloud session.
- **Honest risk:** ~25 fixtures is a small sample. Mitigated by the hard gate below being
  absolute rather than statistical.

### B. Add question capture to the chat ledger, accrue, then replay

Extend `append_chat_ledger` with the question text, wait for real usage, then replay.

- **Why not:** it does not fix the task mismatch — it would accrue *per-item* questions, not
  reshape requests. It delays any verdict by weeks. And it turns a cost ledger into a
  content log, which is a privacy-surface change that deserves its own conversation rather
  than riding in as bake-off scaffolding.

### C. LLM-as-judge over unlabeled real days

Skip gold sets; have a judge model score each selection for relevance.

- **Why not:** it replaces a mechanical bar with a judgment call, at the exact moment the
  project is trying to earn a doctrine change *by being mechanical*. M0's authority came
  from source-verified grading, not from a model's opinion. This is the approach that would
  make a veteran right to reach for the kill switch.

---

## Proposed design (approach A)

**New file: `sweeps/local_reader_bench.py`** — a standalone script, no backend changes.

1. **Corpus loader** — reads the fixture suite (`sweeps/fixtures/reshape_requests.json`) and
   resolves each fixture's day via the backend's `load_brief_topics()`, so ids match the
   served brief exactly.
2. **Prompt builder** — one self-contained prompt in `chat.py:build_prompt`'s house style:
   the day's items rendered as an indexed list (index, headline, attribution, digest), the
   request, and a hard instruction to return **only** a JSON array of integers.
3. **Runner** — an Ollama HTTP runner conforming to the existing `Runner` shape
   (`Callable[[Sequence[str]], ChatResult]`, `chat.py:49`), injectable so tests never touch
   a real model.
4. **Deterministic decoder** — parses the integer array; drops out-of-range, duplicate, and
   non-integer entries; records each drop as a defect. This is the ids-only enforcement
   point, and it is pure Python.
5. **Grader** — scores the surviving selection against the fixture's gold set.
6. **Reporter** — writes `docs/local-reader-grades.md` in the `docs/M0-sweep-grades.md`
   house style: dated heading, per-fixture rows, a running verdict.

### Grading rubric

| Dimension | Measure | Gate |
|---|---|---|
| **Schema discipline** | Parseable integer array, every entry in range, no duplicates | **Hard gate** |
| **Recall** | Fraction of gold-required ids present | Bar set at authoring |
| **Precision** | Gold-forbidden ids absent | Bar set at authoring |
| **Refusal honesty** | Impossible requests return empty, not a plausible-looking guess | **Hard gate** |
| **Ordering** | Scored only where the fixture declares an expected order | Advisory in week 1 |

### Pass bar

- **Hard gates are absolute**: a single unparseable response, out-of-range index, or
  confabulated non-empty answer to an impossible request **fails the day**. This is the
  M0 zero-fabrication bar transposed onto structured output.
- **A pass = 7 consecutive daily runs** over real sweep days, all hard gates clean, recall
  and precision at or above the authored bars.
- A failing week is a real outcome and gets written up as one. The doctrine holding is a
  legitimate verdict, not a wasted sitting.

### Tests (cloud-authorable, per the `test-writer` house style)

The runner is injected, so the decoder, grader, and reporter are all testable with a fake
runner and synthetic fixtures — no Ollama, no real sweep dirs, no network. Specifically
worth adversarial coverage: malformed model output, indices off by one at both ends,
duplicate indices, an empty array, and a response with prose wrapped around the JSON.

### What a cloud session can and cannot do

Authorable here: the bench, the decoder, the grader, the reporter, the tests, the fixture
*schema*. **Not runnable here:** anything producing a verdict — `backend/data/` and
`/data/sweeps/` are gitignored (`.gitignore:40,43`), so the real corpus exists only on
Kyle's Mac. The graded week is his to run, and the gold sets are his to author.

---

## Open items for Kyle (not blocking approval of the approach)

1. **Model choice within Ollama.** "Small instruct" was the recorded answer; the specific
   model can be picked at install time, and the bench should take it as a flag so a second
   model is a re-run rather than an edit.
2. **Fixture authoring session.** ~20–30 requests with gold sets. Worth doing against a
   real recent sweep day so the requests are ones actually wanted that morning.
3. **Recall/precision bars.** Proposed to set them when the fixtures are authored, from what
   the gold sets look like, rather than guessing a number now.
