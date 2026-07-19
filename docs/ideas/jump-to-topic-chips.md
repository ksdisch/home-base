# Jump straight to the topic you came for

**Status:** Idea — not committed. Added by `/brainstorm` (QuickWin mode) on 2026-07-19.

_A thin sticky row of topic-name chips atop the Today brief that scrollIntoView() to each TopicSection's anchor, so the fixed sweeps/topics.json order stops being the only way through the page._

## Premise

Brief.tsx renders all 8 roster topics top-to-bottom in sweeps/topics.json order every morning with no way to skip. Giving each TopicSection an id and adding a sticky chip bar that scrolls to anchors is a client-side nav aid — no new data, no new endpoint. Same move independently surfaced in the Friction lane's jump-to-topic-chips candidate (credit both lanes); this is not a pre-existing backlog or shipped item.

**Why now:** The roster hit its full 8 topics at M2 and the order has been frozen in sweeps/topics.json ever since; post-M7 the daily brief is the stable core loop the ~08-03 '≥5 mornings/week' check measures. The tax is paid every morning forever, and it compounds most in summer when half the sports roster is off-season — exactly now.

## The bet

No load-bearing assumption targeted — recurring-tax relief on the core surface. The one thing that must be true: that the fixed roster order is a real friction every morning, not just occasionally — that off-season sports (st-louis-blues in July, kansas-basketball, fantasy-football) and slow-news sections are dead weight Kyle scrolls past to reach the one topic he opened the app for. A veteran's flinch is low (it's a nav aid) but pointed: 8 topics render top-to-bottom in config order every single morning with no skip, and this is the first crack in the tyranny of that order — the seam where a future 'dim off-season' or 'reorder by relevance' eventually lands.

## Decisions / open questions

Show all 8 chips always, or dim/omit chips for topics that produced no items or an off-season/empty section? Should a chip reflect a topic.error state (unvalidated sweep)? How tall can the chip row be before it competes with the header for vertical space on a phone — single-line horizontal scroll vs wrap?

## Credible first step

frontend/src/pages/Brief.tsx: add id={topic.slug} to the <section> in TopicSection (line 267, verified no id today), and a sticky chip row above brief.topics.map (line 455) that scrollIntoView()s each section on click. Pure client-side, no new data or API. Note the existing sticky header (App.tsx:86, top-0 z-10) — the chip bar must sit below it and the section anchors need scroll-margin-top so a jumped-to heading isn't hidden under both sticky bars.

## Dependencies

brief.topics already rendered in roster order (Brief.tsx:455), the sticky header at App.tsx:86 (scroll-margin coordination so anchors clear it), and topic.slug already present on each BriefTopic.

## Explicitly out of scope (revisit later)

No reordering of topics, no relevance ranking, no hiding off-season topics, no persisting a preferred order — just anchor navigation over the existing fixed order. Reorder/relevance is a later, larger move this chip bar merely makes room for.

## Identity/positioning note

none — tethered.
