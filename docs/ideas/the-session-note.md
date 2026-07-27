# The Session Note — a therapist reads six months of Kyle's own notes back to him

**Status:** Idea — not committed. Added by `/replenish` (Moonshot lane) on 2026-07-26. **Wildcard** — the lane's boldest borderline survivor, kept per the counter-pressure rule.

_A monthly sweep-time (never read-time) reflective reading of the whole brief_notes + news_events + brief-chat corpus that produces one therapist-style session note: reflective reformulations, stated-vs-revealed tensions, and one gentle confrontation ('On 07-02 you wrote "…"; this week you wrote "…"'). The load-bearing safeguard is mechanical: every quoted phrase must exact-substring-match a stored brief_notes row, or the claim is deterministically dropped at render — so fabrication of Kyle's own words is detectable by string comparison, not by trust. This crosses the Mirror's explicit no-LLM-no-profile line on purpose, and moves the product's subject from 'the world' toward 'Kyle's mind'._

## Premise

Once a month Kyle gets not a summary of the news but a reading of himself — the tensions between what he says he cares about and what he actually notes, one gentle confrontation drawn from his own words, every quote provably his. The product starts holding up a mirror to Kyle's mind, not the world's.

**Why now:** The notes corpus has been accruing since M2 (brief_notes v5) and is now months deep — long enough that a longitudinal reading has something true to say. The mechanical exact-substring verifier only becomes possible because every note is a stored SQLite row; the read-time-deterministic doctrine is honored (LLM spend at sweep time, one scrubbed subscription-lane claude -p, the established M5/Designer lane).

## The bet

THE ONE THING THAT MUST BE TRUE: Home Base's accumulated notes are a longitudinal text about Kyle worth reading for meaning, not just counting — and a fabricated quote of Kyle's own words would be more trust-fatal than any fabricated news item, so the sourcing bar must extend to this new content class, where (unlike news) verification is fully mechanical against SQLite. TARGETS assumption 1 (sweep accuracy sustains the habit) by extending the M0 bar to Kyle's own words. VETERAN FLINCH — and why it is the wildcard: mirror.py explicitly stops at 'counts plus one templated framing sentence, no stored profile' (confirmed in the file's own docstring), and this deliberately blows past that self-imposed line to have the system read the MEANING of what Kyle writes and quote him back to himself. That is the most identity-bending move in the set; it is borderline precisely because 'a reflective journal companion whose subject is Kyle' is a real drift from 'a brief about the world', held recognizable only by riding the existing notes loop.

## Decisions / open questions

(1) Monthly cadence right, or quarterly to keep it scarce? (2) Does it render on Today (like Mirror) or as its own page Kyle visits deliberately? (3) Tone guardrails — how confrontational may the one gentle confrontation be? (4) Does this idea deserve to exist at all given the Mirror's deliberate no-profile line — the wildcard question.

## Credible first step

New sweeps/session_note.py as a monthly best-effort post-sweep step in the audio_brief.py pattern (confirmed 289-line best-effort module that never fails the sweep): read brief_notes via the existing store, run one scrubbed subscription-lane claude -p (tools off), emit backend/data/session-YYYY-MM.json where each claim carries the note ids it quotes; a deterministic verifier in the same file drops any claim whose quote doesn't exact-match its cited note BEFORE the file is written. Serve read-only from backend/app/api/brief.py. One sitting for generator plus verifier against Kyle's real July notes.

## Dependencies

brief_notes (+ news_events, brief-chat.jsonl) via the existing store, the M5/Designer subscription claude -p lane (scrubbed, tools off), the audio_brief.py best-effort post-sweep pattern.

## Explicitly out of scope (revisit later)

Never at read time (sweep-time only). No stored psychological profile — each note is generated fresh from the corpus and the verifier drops unverifiable quotes BEFORE the file lands. No advice/diagnosis register; reflective reformulation only.

## Identity/positioning note

identity-shift: crosses the Mirror's no-LLM-no-profile line and moves the product's subject from 'the world' toward 'Kyle himself'. What changes about what-this-project-IS: Home Base grows a reflective-journal-companion facet layered onto the news brief, with the notes corpus reread as a text about its author.
