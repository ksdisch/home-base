# Bake-off fixtures — `reshape_requests.json`

Gold sets for the Free-Inference Rebuild bake-off (decision D8, plan in
[`docs/LOCAL_READER_BAKEOFF_PLAN.md`](../../docs/LOCAL_READER_BAKEOFF_PLAN.md)).

**These are authored by hand, by Kyle.** A fixture is a statement about what a request
*should* return — that is a judgment call, and it is the bar the model is graded against.
Generating them with a model would make the bake-off grade a model against itself.

`reshape_requests.json` is **not committed** — it references item ids from
`data/sweeps/<date>/`, which is gitignored and exists only on the Mac. Copy
`reshape_requests.example.json` and fill it in.

## Authoring

Item ids are derived at read time (`sha1(date|slug|headline)[:12]`), so list them first:

```
python3 sweeps/local_reader_bench.py --show-day 2026-07-20
```

That prints `[ordinal] id (topic) headline` for every item in the day. Write gold sets in
**ids**, not ordinals — ids are stable across re-reads, ordinals are positional.

Then check the suite loads and see how big each day is:

```
python3 sweeps/local_reader_bench.py --list-fixtures
python3 sweeps/local_reader_bench.py --dry-run     # see the exact prompts
```

## Schema

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Short stable slug; the report's row label |
| `date` | yes | A real `data/sweeps/<date>/` day |
| `request` | yes | The natural-language reshape, worded the way you'd actually ask |
| `must_include` | no | Ids that MUST appear — drives recall |
| `must_exclude` | no | Ids that must NOT appear — drives precision |
| `expect_order` | no | Relative order these ids must hold; other items may sit between them |
| `expect_empty` | no | `true` for impossible requests. A non-empty answer is a **hard fail** |

## Coverage worth having

The plan calls for ~20–30 fixtures. Spread them across the request classes, and keep the
last one — a model that never refuses is a model that pads:

- **Place / topic filters** — "just the Chicago stuff", "only the AI news"
- **Compression** — "brief me in 90 seconds", "top three only"
- **Drop-what-I've-seen** — continuations of yesterday
- **Combinations** — a filter plus a cap
- **Impossible requests** — something genuinely absent from that day, with
  `expect_empty: true`

Set the recall and precision bars once the gold sets exist and you can see what shape they
take; guessing a number before that just invents a bar.
