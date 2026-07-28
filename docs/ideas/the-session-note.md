# The Session Note — a therapist reads six months of Kyle's own notes back to him

**Status:** Idea — PARKED at the 2026-07-27 gate conversation (decision D9) until the notes
corpus has real depth (~6 months of accrual, so roughly 2027-01). Added by `/replenish`
(Moonshot lane) on 2026-07-26. **Wildcard** — the lane's boldest borderline survivor, kept
per the counter-pressure rule.

_A monthly sweep-time (never read-time) reflective reading of the whole brief_notes + news_events + brief-chat corpus that produces one therapist-style session note: reflective reformulations, stated-vs-revealed tensions, and one gentle confrontation ('On 07-02 you wrote "…"; this week you wrote "…"'). The load-bearing safeguard is mechanical: every quoted phrase must exact-substring-match a stored brief_notes row, or the claim is deterministically dropped at render — so fabrication of Kyle's own words is detectable by string comparison, not by trust. This crosses the Mirror's explicit no-LLM-no-profile line on purpose, and moves the product's subject from 'the world' toward 'Kyle's mind'._

## Premise

Once a month Kyle gets not a summary of the news but a reading of himself — the tensions between what he says he cares about and what he actually notes, one gentle confrontation drawn from his own words, every quote provably his. The product starts holding up a mirror to Kyle's mind, not the world's.

**Why now:** ~~The notes corpus has been accruing since M2 (brief_notes v5) and is now months deep — long enough that a longitudinal reading has something true to say.~~ **Struck 2026-07-27 at the gate conversation — this claim was false.** M2 shipped **2026-07-14** (`docs/MASTER_PLAN.md`, PRs #38 + #39), so at the gate the corpus was **13 days** old, not months; at the v1 target rate of ≥3 notes/week that is roughly five or six notes total. The title's "six months" was aspirational, not descriptive. The idea's "why now" is therefore **not yet true** — it becomes true with time and nothing else, which is what the park is waiting on. The rest of the paragraph stands: the mechanical exact-substring verifier only becomes possible because every note is a stored SQLite row; the read-time-deterministic doctrine is honored (LLM spend at sweep time, one scrubbed subscription-lane claude -p, the established M5/Designer lane).

## The bet

THE ONE THING THAT MUST BE TRUE: Home Base's accumulated notes are a longitudinal text about Kyle worth reading for meaning, not just counting — and a fabricated quote of Kyle's own words would be more trust-fatal than any fabricated news item, so the sourcing bar must extend to this new content class, where (unlike news) verification is fully mechanical against SQLite. TARGETS assumption 1 (sweep accuracy sustains the habit) by extending the M0 bar to Kyle's own words. VETERAN FLINCH — and why it is the wildcard: mirror.py explicitly stops at 'counts plus one templated framing sentence, no stored profile' (confirmed in the file's own docstring), and this deliberately blows past that self-imposed line to have the system read the MEANING of what Kyle writes and quote him back to himself. That is the most identity-bending move in the set; it is borderline precisely because 'a reflective journal companion whose subject is Kyle' is a real drift from 'a brief about the world', held recognizable only by riding the existing notes loop.

## Decisions / open questions

(1) Monthly cadence right, or quarterly to keep it scarce? (2) Does it render on Today (like Mirror) or as its own page Kyle visits deliberately? (3) Tone guardrails — how confrontational may the one gentle confrontation be? (4) Does this idea deserve to exist at all given the Mirror's deliberate no-profile line — the wildcard question.

**PARKED at the 2026-07-27 gate conversation (Kyle's call, recorded outcome):**

The gate went straight at question 4, the wildcard, because a "no" there moots the other
three. The answer was **not** a no — it was "not yet, and for a concrete reason."

1. **Parked until the corpus is real.** The trigger is mechanical, not a date on a
   calendar: revisit when `brief_notes` has roughly six months of accrual behind it —
   M2 shipped 2026-07-14, so approximately **2027-01**. A longitudinal reading needs
   something longitudinal to read. Killing the idea outright and building it anyway on a
   quarterly cadence were both offered and declined; so was a deterministic all-time
   Mirror-window substitute.
2. **Two findings recorded so the revisit starts from them, not from scratch:**
   - **The project already wrote the counter-argument, in code.** `backend/app/mirror.py`
     sets `MIN_SIGNAL = 5` with the comment "Below this many total logged signals the week
     has no honest shape yet — render the insufficient state rather than a lean invented
     from three data points." Mirror deliberately refuses to describe Kyle from a handful
     of rows. Shipping an LLM that finds "stated-vs-revealed tensions" in a corpus sitting
     near that same floor would contradict the product's own stated standard, not merely
     cross the no-profile line. **At the revisit, the Session Note should be held to an
     explicit signal floor of its own** — the Mirror precedent, applied to a longer window.
   - **The verifier guards the safer half.** Exact-substring matching against `brief_notes`
     proves Kyle *wrote the words*. It cannot establish that the *tension is real* or that
     the *confrontation is fair* — and those interpretive claims, not the quotes, are what
     would actually damage trust. The safeguard is genuinely good and genuinely partial;
     the revisit needs an answer for the interpretive half before this can ship.
3. **Questions 1–3 remain deliberately unanswered** — cadence, surface, and tone guardrails
   are the revisit conversation's agenda, per the answers-become-recorded-scope pattern the
   Overnight v0 gate set and the Agent Gate park followed.

## Credible first step

New sweeps/session_note.py as a monthly best-effort post-sweep step in the audio_brief.py pattern (confirmed 289-line best-effort module that never fails the sweep): read brief_notes via the existing store, run one scrubbed subscription-lane claude -p (tools off), emit backend/data/session-YYYY-MM.json where each claim carries the note ids it quotes; a deterministic verifier in the same file drops any claim whose quote doesn't exact-match its cited note BEFORE the file is written. Serve read-only from backend/app/api/brief.py. One sitting for generator plus verifier against Kyle's real July notes.

## Dependencies

brief_notes (+ news_events, brief-chat.jsonl) via the existing store, the M5/Designer subscription claude -p lane (scrubbed, tools off), the audio_brief.py best-effort post-sweep pattern.

## Explicitly out of scope (revisit later)

Never at read time (sweep-time only). No stored psychological profile — each note is generated fresh from the corpus and the verifier drops unverifiable quotes BEFORE the file lands. No advice/diagnosis register; reflective reformulation only.

## Identity/positioning note

identity-shift: crosses the Mirror's no-LLM-no-profile line and moves the product's subject from 'the world' toward 'Kyle himself'. What changes about what-this-project-IS: Home Base grows a reflective-journal-companion facet layered onto the news brief, with the notes corpus reread as a text about its author.
