# The untrusted fence is a habit, not an object — make it forgery-proof and un-forgettable

**Status:** Idea — not committed. Added by `/replenish` (Harden lane) on 2026-08-12.
**Note:** This card IS open bug #18's fix — do not fix #18 separately first, or the refactor lands on a seventh hand-typed fence.

_One shared `untrusted_block()` that builds every data-not-instructions fence — and neutralizes any closing delimiter hiding inside the payload — plus a repo-invariant test that fails when a new `claude -p` lane appears without it._

## Premise

Load-bearing assumption 4 says every LLM lane is grounded and scrubbed with untrusted-data framing. I read all six lanes: five carry it (`chat.py`, `paths/grader.py`, `studycal/negotiate.py`, `courses/regen.py`, `sweeps/actions_queue.py`) and `paths/designer.py` does not — open bug #18 — because the framing is a literal string retyped per lane, so the guard decays with every lane added. Worse, in all five compliant lanes the fence is forgeable: `chat.build_prompt` interpolates a swept digest with no escaping, so an item whose text contains the literal `</untrusted-item>` closes its own fence and the rest reads as prompt. The existing HA4 test (`test_brief_chat.py::test_build_prompt_frames_the_item_as_untrusted_data`) pins a payload *inside* the delimiters but never one that *is* a delimiter, so nothing catches it. This card makes the boundary a real object rather than a habit: one helper whose fence can't be forged, six lanes on it, and a discovery test that refuses to pass when lane seven shows up unregistered.

**Why now:** The moonshot lane is frozen until the ~08-19 verdict, so solidification is exactly what this window is for. Bug #18 is open and would otherwise be hand-fixed as a seventh copy of the same string, spending the fix without buying the mechanism. And #173 just landed `video`/`mindmap` step kinds with frontend-only validation (the sibling open bug #17), which is the same failure shape one layer up: new content shapes arriving faster than the guards that were written for the old ones.

## The bet

The bet: lane seven gets written, and a test that fails on an unregistered lane is cheaper than remembering — the parked study-planner subagent, the YouTube-breakdown writer, the Free-Inference rebuild, and #173's two new step kinds are all lane-seven candidates already in flight, and designer.py is the proof the habit already failed once. A veteran of this project reacts two ways. First: "we shipped `untrusted-item-framing` in PR #89, this is done" — no: that card fixed *one prompt*, and the fence it installed is escapable in every lane that copied it. Second, the sharper one: "import-presence is theater" — agreed, which is why the substance here is the forgery test and the payload table run through the real `build_*_prompt` functions, not the import check.

## Decisions / open questions

- Enforcement point: registry-in-test vs. a runtime decorator on each lane. **Recommend registry-in-test** — no runtime cost, and no import across the backend-venv / stdlib-sweeps boundary.
- Neutralization strategy for a payload containing its own closing tag: strip it, replace it with a visible marker, or use nonce-suffixed delimiters (`<untrusted-item-a7f3>`). **Recommend visible marker** so prompts stay deterministic and diffable in the chat/overnight ledgers; fall back to nonce delimiters if a payload defeats the marker in testing.
- Does the invariant cover `sweeps/prompts/*.md` — the ingestion lane where the model itself has web tools and reads pages directly? **Recommend no**: different shape, and `sweeps/render_brief.py` is already its write-time trust gate. State it as the honest ceiling in the doc rather than quietly omitting it.
- Do the five existing per-lane framing tests get subsumed by the new payload table? **Recommend keep both** — the per-lane tests document each lane's intent; the table enforces the invariant.
- Should the discovery scan also flag a lane that builds a prompt from swept text but calls no CLI (e.g. a future template renderer)? Probably out of reach for an AST scan; note the limit rather than pretend coverage.

## Credible first step

Write `backend/tests/test_untrusted_lanes.py` RED first, modelled on the repo-invariant style of `backend/tests/test_no_sidecar_writes.py` and using the importlib-from-`sweeps/` loader already in `backend/tests/test_render_brief.py`. Three assertions: (1) `designer.build_designer_prompt` (`backend/app/paths/designer.py:62`) fences its artifact block — RED today, closes #18; (2) a payload containing the literal closing tag cannot escape any of the six fences — RED today in all five "compliant" lanes; (3) a synthetic module that spawns the claude CLI without the helper fails a discovery scan. Then add `backend/app/untrusted.py` with `untrusted_block(tag, framing, fields) -> str` (the exact wording already in `chat.py:119-131`) plus a stdlib-only sibling `sweeps/untrusted.py` — `sweeps/*.py` is system-python/no-venv and can only import siblings, the precedent being `import envelope` at `sweeps/actions_queue.py:42` — with the test asserting the two copies produce byte-identical output. Refactor the five hand-typed fences onto it: `chat.py:102-131` (both `<untrusted-item>` and `<untrusted-prior-item>`), `paths/grader.py:38-40`, `studycal/negotiate.py:74-76`, `courses/regen.py:203-210`, `sweeps/actions_queue.py:186-198`. Discovery scan walks `backend/app/**/*.py` + `sweeps/*.py` for `.ask(` callers of `BriefChatClient`/`CourseRegenClient` and direct `subprocess.run([<claude_bin>, "-p", ...])`, diffs against the registry in the test, and fails with "add your lane and its payload fixture".

## Dependencies

None blocking. Collides with open bug #18 (`paths/designer.py`) — this card *is* #18's fix, so #18 must not be fixed separately first or the refactor lands on top of a seventh hand-typed fence. Adjacent to open bug #17 (unrecognized step kinds escape the no-fabrication bar) on the same "new shapes outrun old guards" theme, but independent — no shared files. Needs the existing fake-runner seams (`backend/tests/conftest.py`, the `runner=` injection on `BriefChatClient`/`CourseRegenClient`); all present.

## Explicitly out of scope (revisit later)

The sweep prompts themselves (`sweeps/prompts/*.md`) and the model's own web fetching — a different lane shape with `render_brief.py` as its gate. Bug #17's step-kind fabrication bar. Any runtime rejection or blocking of prompts — this is a build-time invariant, not a filter. The news/RSS path (no LLM). And explicitly: immunity to prompt injection. This makes the mitigation present, shared, and unforgeable; it does not make a determined payload harmless.

## Identity/positioning note

none — tethered. Assumption 4 is already a stated load-bearing assumption of the project; this converts it from a claim into a check.

## What it changes

Assumption 4 stops being author discipline and becomes a failing test. Six prompt-builders change behavior, not just structure: a swept digest, artifact title, or prior material containing a closing delimiter can no longer break out of its fence. `paths/designer.py` gains the framing it never had (bug #18 closes as a side effect, not as the point). The next lane cannot ship silently — the discovery scan fails until its author registers it and supplies a payload fixture, which is the moment they learn the fence exists.
