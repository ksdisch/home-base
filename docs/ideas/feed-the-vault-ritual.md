# The Ritual Already Lives Elsewhere

**Status:** Idea — not committed. Added by `/brainstorm` (Premortem mode) on 2026-07-19.

_Kyle's actual daily-check-in habit consolidates in the always-reachable Cowork/vault stack (morning-briefing, daily-plan, habit-check, evening-reflection — all reading Obsidian vault + Todoist + Calendar from any device, already scheduled), and Home Base — a second app gated behind an awake Mac and the tailnet — quietly becomes the extra stop he forgets to make, abandoned months before he consciously decides it failed._

## Premise

Home Base was built as a standalone destination Kyle opens each morning, but he already runs a full, always-reachable vault ritual stack that resolves his phone-in-hand habit before Home Base ever competes for it. The strategic death isn't dramatic — it's availability: the vault works from any device, Home Base needs an awake Mac + tailnet, so attention migrates by default. The antibody concedes the destination premise and reframes Home Base as a producer: a best-effort hook, mirroring how audio_brief.py already runs without failing the sweep, that writes the morning's developing threads and topic-scout candidates into the vault daily note — so the product's intelligence reaches Kyle where his ritual already lives.

**Why now:** Both arcs are complete and M7 shipped, so Home Base is now a finished standalone destination competing head-on with a vault stack whose morning-briefing/daily-plan/habit-check/evening-reflection skills already own Kyle's daily ritual and are strictly more available. The ~08-03 v1 check measures 'opened ≥5 mornings/week' — the exact metric a more-reachable competing ritual silently erodes, with no signal when it does.

## The bet

That Home Base wins by feeding the ritual Kyle already runs rather than competing for the same morning attention slot — that injecting its swept intelligence into the vault daily note makes the value show up where he already looks, so the product survives even as a producer once it can't survive as a destination. It targets assumption 2 (Mac-local by design): the vault stack works from any device the moment Cowork is reachable, Home Base only when the Mac is awake and he's on the tailnet, and nothing in Home Base's instrumentation catches attention migrating to a different app entirely. A veteran flinches because this concedes the founding premise — a standalone destination — to a more-available incumbent ritual.

## Decisions / open questions

This partly concedes the app's own premise — does feeding the vault accelerate abandonment of the Home Base UI itself, or extend its reach? The vault daily-note path/format is external and must exist + be writable (how to configure it without hardcoding Kyle's vault layout); how much to inject before it duplicates morning-briefing; is a one-way feed the right relationship or does Home Base also need to pull vault state back (that's the tethered MO2/MO4 mirror territory).

## Credible first step

Add a best-effort post-sweep hook that appends a 3–5 line plaintext summary of the morning's developing threads + topic-scout candidates into the vault daily note. CORRECTION to the input wedge: it names 'the same post-sweep call site wired in backend/app/api/brief.py' — that is wrong. audio_brief.py is NOT invoked from brief.py (brief.py:83 only references it in a docstring); the real best-effort call site is sweep.sh line ~151, a guarded `if ! python3 "$ROOT/sweeps/audio_brief.py" ...; then` block that runs after the render and never fails the sweep. The hook belongs there, mirroring that exact guard. The vault daily-note path lives outside this repo and must be configurable.

## Dependencies

sweep.sh's post-sweep block (line ~151, the audio_brief.py guard to mirror); render_brief.py's developing-thread labels + the M7 topic-scout candidate data as the summary source; a writable vault daily-note path outside this repo (external dependency — must be configurable, not assumed); the same best-effort/never-fail-the-sweep pattern audio_brief.py established.

## Explicitly out of scope (revisit later)

Two-way sync or reading vault state back into Home Base; replacing or deprecating the Home Base UI; invoking the vault skills (morning-briefing etc.) directly; hosted/off-Mac access (parked); any change that makes the hook able to fail the sweep.

## Identity/positioning note

identity-shift: Home Base stops being the destination Kyle opens and becomes a feed into a ritual he already runs elsewhere — what changes in what-this-project-IS is its role, from a parallel morning destination to an input producer for the vault stack.
