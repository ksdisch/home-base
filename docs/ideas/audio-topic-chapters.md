# Audio topic chapters

**Status:** Idea — not committed. Added by `/brainstorm` (Friction mode) on 2026-07-19.

_The ~5-min brief is one linear Kokoro MP3 built topic-by-topic in roster order behind a bare <audio controls> with zero seek metadata, so skipping an out-of-season or already-read topic on a walk means blind-scrubbing a featureless bar with the phone in a pocket._

## Premise

The audio brief is the walk mode M6 made real, but it's a single 5-minute Kokoro track with no chapters, so skipping a dead-season sport means blind-scrubbing. build_script already assembles the script topic-by-topic and already trusts a words-per-minute estimate for its own duration line — the same math yields per-topic start offsets essentially for free. Ship them as chapter data and render seek chips, landing each chip just before its segment so the spoken 'Next up:' lead confirms the jump — turning the estimate's drift into a feature rather than a failure.

**Why now:** M6 made audio-on-a-walk a real phone-in-pocket mode, and the roster carries seasonal sports (fantasy-football, celtics, st-louis-blues) that are dead weight half the year — so the skip tax is paid on those topics every single walk.

## The bet

That deterministic word-count offsets are close enough to be useful despite drifting from real Kokoro timing — the objection's real teeth. The steelman: seek each chip a few seconds BEFORE its segment so the audible 'First up:/Next up:' lead confirms Kyle landed on the right topic, turning the estimate's imprecision into a landmark instead of a mid-sentence surprise. Targets no load-bearing assumption; it adds no spoken content and no LLM call, staying squarely inside assumption 4.

## Decisions / open questions

How much lead-in to subtract per chip to absorb WORDS_PER_MINUTE drift? Should chips also highlight the now-playing topic (needs a timeupdate listener, overlapping QU3's resume handler)? Confirm trim-ladder-zeroed late topics still get a chapter (they should — the intro line always survives).

## Credible first step

In sweeps/audio_brief.py build_script (lines 138-172, where segments are assembled per topic in order), accumulate each segment's cumulative word count at its boundary and convert to a start-offset via the same WORDS_PER_MINUTE=155 (line 41) the pipeline already trusts for its duration line, writing data/sweeps/<date>/brief.chapters.json as [{slug,title,start_seconds}]; surface it on BriefResponse (get_brief, brief.py line 55) and render tappable seek chips in the Brief.tsx audio block (lines 395-402) that set the <audio> currentTime. Correction to the input wedge: it proposed a separate route 'same family as briefAudioUrl()'; folding chapters onto the existing BriefResponse the page already fetches (where audio_available already rides) is the lighter seam. Repo-verified: build_script assembles per-topic segments deterministically and the trim ladder only zeroes a late topic's `extra` (its intro line always survives, so every topic keeps a real offset).

## Dependencies

sweeps/audio_brief.py (build_script + the render/main write path), backend/app/api/brief.py BriefResponse, frontend/src/pages/Brief.tsx audio block, and the api types for the new field.

## Explicitly out of scope (revisit later)

No re-timing against the actual mp3 duration (no forced-alignment/ffprobe pass) in v1 — estimate only; not audio resume-from-position (that is QU3, same walk, different move); no change to the spoken script content.

## Identity/positioning note

none — tethered.
