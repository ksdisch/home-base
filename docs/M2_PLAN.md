# M2 Plan — Full Roster + Inline Notes

_Status: in progress. Kickoff M2 spec: "All topics with pause/seasonal flags via config;
inline notes on items, browsable per topic; 'Your learning' section on home." Kyle
green-lit M2 on 2026-07-14 (Day 1 of the M0 grading week) — a second deliberate override
of the "no UI until M0 passes" gate, noted in writing; grading continues in parallel.
Ships as two PRs so each half is independently shippable: **PR 1 — roster config +
prompts**, **PR 2 — item ids + notes + learning strip**._

## The fork that was decided first: where item identity comes from

Inline notes anchor to brief *items*, and M1 deliberately shipped no item ids. Options
were (a) derive ids at read time, (b) have the renderer stamp ids into `<topic>.json` at
write time, (c) anchor notes positionally with no ids. **Kyle picked (a) — read-time
derived ids** — because:

- **The trust-critical write path stays frozen.** `sweeps/render_brief.py` and the prompts
  don't change mid-grading-week; the id is `sha1("{date}|{slug}|{headline}")[:12]`,
  computed in `app/sweeps.py` when the JSON is shaped for the API.
- **It works retroactively** for every already-written JSON day (the id-less files from
  the first live sweeps), where write-time ids would need read-time derivation as a
  fallback anyway.
- **Durability lives in the durable store.** `data/sweeps/` is gitignored and regenerable;
  each note row carries a snapshot (`topic_slug`, `brief_date`, `item_headline`) so it
  stays browsable even if its brief file is re-swept or gone. A same-day re-sweep that
  rewords a headline orphans the *anchor* (the note keeps its snapshot) — rare, accepted.

## The slice

```
sweeps/topics.json       →  NEW ordered roster [{slug, title, paused}] — the config-file
                            UI for adding/pausing topics (kickoff: manual flags for v1)
sweep.sh                 →  runs every unpaused roster topic (TOPIC=<slug> still runs any
                            one topic, paused or not); roster missing → loud fail
sweeps/prompts/          →  5 new prompts: chiefs, celtics, indiana (FB+BB in one brief),
                            kansas-basketball, st-louis-blues — same JSON contract + hard
                            rules; season-aware via the runner's injected date
backend                  →  ROSTER_FILE setting (default <repo>/sweeps/topics.json);
                            app/sweeps.py: load_roster() read per request — titles +
                            display order; missing/invalid roster degrades to humanized
                            titles, never a failed brief; paused topics with files on
                            disk still render (pause gates sweeping, not display)
                            item ids derived in _structured_topic (PR 2)
                            brief_notes table, schema v5 (PR 2): item_id + snapshot
                            (topic_slug, brief_date, item_headline) + body + created_at
                            POST /api/brief/notes · GET /api/brief/notes?topic= ·
                            DELETE /api/brief/notes/{id}; today's notes joined inline
                            onto GET /api/brief items (PR 2)
frontend (PR 2)          →  per-item note composer + notes on the Today page; /notes page
                            (browsable per topic); "Your learning" strip on Today reusing
                            GET /api/review + GET /api/courses (hides on error — it never
                            blocks the morning read); types.ts/client.ts hand-sync
```

## Deliberately NOT in M2

- **No curation UI for the roster** — the config file *is* the interface (kickoff ⚠️
  assumption: "config file first, curation UI later").
- **No note editing** — add / list / delete only (flat-notes v1 assumption); PATCH is
  cheap to add when wanted.
- **No note threads/expansion, no note→notebook bridge** (deferred with auto-courses).
- **No scheduling / parallel sweeps** — the 8-topic sweep runs ~30 min sequentially; M3.
- **No ids stamped into the sweep JSON files** — revisit only if M3's dedup-vs-history
  actually needs persistent in-file identity.

## Verification

PR 1: backend pytest with a synthetic `ROSTER_FILE` (titles/order from the file, paused
topics still display, missing/invalid roster degrades without a 500) — suite 304 green;
`bash -n sweep.sh` + roster-extraction check; one live `TOPIC=chiefs` trial sweep
validating a new prompt end-to-end through the renderer. PR 2: pytest for id
stability/uniqueness + notes CRUD (inline join, per-topic browse, delete, empty-body 400);
frontend vitest for the composer, /notes page, and learning strip; `make typecheck` +
`make lint`; contract-reviewer pass on the hand-synced TS types.
