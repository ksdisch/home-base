# Notes reach the surface Kyle actually grazes

**Status:** Idea — not committed. Added by `/brainstorm` (QuickWin mode) on 2026-07-19.

_A 'Note' button on every News and For-You card that writes through the exact same POST /brief/notes path the Brief page uses, so a news item becomes a durable note interleaved into /notes alongside brief notes._

## Premise

The M2 inline-notes feature was deliberately built with self-contained snapshot columns (item_id, topic_slug, brief_date, item_headline) so a note outlives the sweep file it points at. A NewsItem already carries a stable sha1(link) id and maps cleanly onto every one of those columns. Adding one button that reuses POST /brief/notes lets a News or For-You card get the identical inline note a Brief item gets, browsable in the same /notes page — no new note system, just the existing one reaching a second, larger surface for the cost of one button and an id-mapping shim.

**Why now:** Post-M7, News/For-You (~7 categories) is the second real loop surface and it is now the larger one; the v1 success check (~08-03) grades notes/week, and today every note can only originate on Mode-A items. This is the cheapest way to widen the funnel before that check.

## The bet

Targets the >=3 notes/week v1 criterion by pointing the note verb at the highest-frequency surface. The one thing that must be true: news grazing, not the 8-topic brief, is where Kyle most often hits something worth keeping — so the notes metric gets met on the surface built for volume, not the one built for depth. A veteran flinches because brief_notes was designed to snapshot brief_date/item_headline to outlive a sweep FILE — and a news item has no sweep file at all; the steelman is that this is exactly why the snapshot columns exist, so a note on transient RSS is more coherent here than on the brief, not less.

## Decisions / open questions

(1) /notes now interleaves brief-topic slugs and news-category slugs in the same topic_slug column — do they share a namespace cleanly, or does a category need a visible source tag so Kyle can tell a news note from a brief note? (2) topic_title() resolves topic_slug against the Mode-A roster; a news category slug won't be in that roster, so the browse view needs a graceful title fallback. (3) Should a news note deep-link back to the article URL (news items are transient and the RSS item will age out), and is that stored anywhere today?

## Credible first step

frontend/src/pages/News.tsx — add a Note control to the feedback-button row (verified at lines 283–305, next to the liked/'Not interested' buttons; the input's '~294' is inside this row), wired to api.addBriefNote (client.ts:187) with item.id (NewsItem.id = sha1(link)[:12], types.ts:660) as item_id, the category slug as topic_slug, item.headline as item_headline, and today's date as brief_date — all four map 1:1 onto the existing BriefNoteCreate schema (item_id at types.ts:572). No new endpoint, table, or component.

## Dependencies

Existing POST /brief/notes endpoint + add_brief_note store helper; the addBriefNote client method (client.ts:187); NewsItem.id already populated and used in News.tsx's liked/hidden sets. No backend change required.

## Explicitly out of scope (revisit later)

No new notes table or endpoint; no separate news-notes UI or browse page; no backfill of past news items; no change to the For-You ranker or signal log; not persisting the full article body — only the existing snapshot columns.

## Identity/positioning note

none — tethered.
