# Item-level anchors — every pointer that already carries an item_id can finally land on it

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-08-12.
**Note:** Convergence: two blind lenses (force-multiplier · almost-done's email deep-link, folded in as the first consumer).

_Give each brief item a DOM id (`item-<item.id>`) plus one `useHashTarget` hook shared by Today and the archive, then turn the four existing surfaces that already hold an item id — and throw it away — into one-tap landings on the exact story._

## Premise

Home Base already computes a stable, date-scoped id for every brief item (`sha1(date|slug|headline)[:12]`, derived at read time in `backend/app/sweeps.py:176`). That id is the anchor inline notes attach to, the anchor brief-chat attaches to, the anchor archive search returns per hit, and the anchor the readiness strip keys its list on. It is threaded through the models, through the API, into the TypeScript types, and onto the page — and then nothing on the page can be reached by it, because no item ever renders a DOM id. So four surfaces that know precisely which story they mean can only say "that morning" and leave Kyle to hunt down a page of eight topics. `backend/app/sweeps.py:895` states the ambition in its own docstring — "finding the item is only useful if it opens the morning it belongs to" — and `backend/app/models.py:875` calls `item_id` "the served item's read-time anchor" for a strip that cannot reach it. The last mile is one `id=` attribute and one hook; everything upstream is already built and tested.

**Why now:** The delivered email/iMessage is now the FIRST surface of every morning (#181 / #183, shipped 08-11 and 08-12), so "open the app and hunt" is the default path, not an edge case. Meanwhile the extended attribution window (08-03 → 08-16) is running toward the ~08-19 v1 verdict, which certifies on ≥5 phone mornings + ≥3 notes/week — and a note you can't get back to is a note not worth writing. The in-app half of this is metric-neutral (see decisions) so it can land inside the window without touching the instrument; the email half is exactly what the verdict is measuring, so it waits.

## The bet

The ONE thing that must be true: item ids are already carried end-to-end to every surface that would deep-link, so the whole feature is an `id=` attribute plus a scroll hook — no new state, no schema, no API change, no LLM. Verified true at HEAD d447174: `BriefNote.item_id` (models.py:752) reaches `Notes.tsx:133`, archive-search hits carry `item_id` (sweeps.py:929) and reach `BriefIndex.tsx:113`, and `BriefReadinessItem.item_id` (models.py:879) reaches `Brief.tsx:791` — all three render a day-link or plain text and discard the id. A veteran of this project reacts to two things the original framing missed: (1) the readiness "Coming up" strip is an on-page pointer at an on-page item, holding that item's id, that cannot scroll to it — the purest case of a finished mechanism missing its last attribute; (2) the archive search that made the record searchable currently half-works — it finds your item and then drops you at the top of the day to find it again.

## Decisions / open questions

- **The email deep-link needs the hash duplicated into the sweeps lane — and that duplication is forced, not sloppy.** Critic A is right that the delivery lane has no ids: `sweeps/deliver_brief.py` builds its bullets from `audio_brief.load_topics` (`sweeps/audio_brief.py:111-136`), which reads the raw `<slug>.json` and never derives ids. And it CANNOT import the backend's derivation — `sweep.sh:220` runs `python3 sweeps/deliver_brief.py` under bare system python3, while `backend/app/sweeps.py` sits inside a pydantic-dependent package. Recommendation: duplicate the six lines (including the `-2`/`-3` collision suffix) into `audio_brief.load_topics`, cross-comment both sides, and add ONE parity test in `backend/tests/` that feeds a synthetic day dir to both derivations and asserts identical id lists. That test IS the anti-drift device, and it's ~20 lines.
- **Stage the email link after the ~08-19 verdict.** `Brief.tsx:459` is the only caller of `logBriefVisit`; `BriefArchive.tsx` never logs one. So all three sitting-1 consumers are metric-neutral — they improve navigation inside a visit that was already counted — while an email link into `/` creates new counted `phone` visits (`visit_source.py` files a tailnet peer as `phone`). Shipping that mid-window changes the instrument the extended attribution period is measuring. Recommendation: sitting 1 now, sitting 2 after 08-19 — or ship sitting 2 sooner only with the instrument change written into the verdict record.
- **Email: keep the source link, or take the headline?** Today each bullet's headline links to `sources[0].url` (`deliver_brief.py:171`). Recommendation for sitting 2: headline → `<base_url>/#item-<id>` — the live Today page, where Ask is enabled, NOT `/brief/<today>`, which is the read-only archive with Ask hidden — plus a small trailing `· source` link so the direct-out is preserved rather than stolen.
- **Empty `item_id` on note-kind search hits.** `sweeps.py:945` emits `note.get("item_id") or ""`; the link must fall back to the plain day URL rather than emitting a bare `#item-`.
- **Deferred-anchor edge:** an id present in the hash but absent from the rendered day (regenerated sweep, changed headline → changed hash) should silently no-op at the top of the page. Do NOT add a "that item is gone" banner — that's a claim the code can't verify, and this repo's trust rule (#182, open bug #19) says don't state a guarantee the code doesn't keep.

## Credible first step

Sitting 1 — the three metric-neutral in-app consumers, one branch, frontend only:
1. `frontend/src/pages/Brief.tsx:334` — `<article key={item.id || i}>` gains `id={item.id ? \`item-${item.id}\` : undefined}` and `scroll-mt-24`, matching what the topic `<section id={topic.slug}>` at line 310 already uses to clear the sticky header (53px) + sticky chip row.
2. New `useHashTarget` hook, mirroring the scroll pattern already shipped twice — the jump chips' `getElementById(...).scrollIntoView` at `Brief.tsx:892` and `CourseDetail.tsx:213-215`'s `requestAnimationFrame` wrapper. It must fire AFTER the async brief loads, so key it on the loaded payload, not on mount. Call it from `Brief.tsx` and `BriefArchive.tsx` (which reuses the exported `TopicSection` verbatim, so anchors exist there for free).
3. Three call sites: `frontend/src/pages/Notes.tsx:133` `to={\`/brief/${n.brief_date}\`}` → `...#item-${n.item_id}`; `frontend/src/pages/BriefIndex.tsx:113` `to={\`/brief/${hit.date}\`}` → `...#item-${hit.item_id}`, guarding the empty-string case (note-kind hits emit `""` per `sweeps.py:945`); `frontend/src/pages/Brief.tsx:791` — the readiness `<li key={r.item_id}>` headline becomes a button calling the same scroll helper (same page, no navigation).
4. Tests beside the existing `Notes.test.tsx` / `BriefIndex.test.tsx` / `Brief.test.tsx`; close with `make typecheck` + `make test-frontend`. Backend untouched.

## Dependencies

None. Every input exists at HEAD d447174: item ids (`backend/app/sweeps.py:167-186`), `BriefNote.item_id` (models.py:752), archive-search `item_id` (sweeps.py:929/945), `BriefReadinessItem.item_id` (models.py:879), the scroll-to-anchor pattern (Brief.tsx:892, CourseDetail.tsx:213-215), and the `/brief/:date` route (App.tsx:222). Sitting 2 additionally needs `base_url` set in `sweeps/delivery.json` — already required and used by the shipped tap-to-play audio link (`deliver_brief.py:146-152`).

## Explicitly out of scope (revisit later)

Not the jump-to-topic chips (shipped QU4) — those move you within an already-open page; this makes an individual item addressable from outside it. No new store tables, no migration, no backend endpoint, no LLM call, and no change to the id derivation itself or to the on-disk sweep format (ids stay derived, never stored — `sweeps.py:167-170`). No iMessage deep-link (the text is a caption plus one audio link by design, #183). No "jump to your unread" and no per-item read state. No user-agent sniffing or any change to `visit_source.py` bucketing.

## Identity/positioning note

none — tethered. Pure core-loop friction on existing morning-brief surfaces; adds no new capability, no new acting surface, and no new trust claim.

## What it changes

Four dead-end pointers become landings. Tapping a note's date in `/notes` lands on the item the note is about; an archive-search hit lands on the story it matched instead of the top of that morning; the "Coming up" readiness item scrolls to the story it's projecting. In sitting 2, the morning email's headline becomes a tap that opens that exact story in the app on the phone. Nothing else moves: no backend change, no schema, no new API, no LLM surface, no new writes.
