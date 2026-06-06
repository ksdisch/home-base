---
name: youtube-breakdown
description: >-
  Process a YouTube transcript or URL into a structured breakdown using one of four modes:
  Study Notes (deep retention), Quick Reference (skimmable triage), Critique (steelman-then-
  dismantle), or Actionable Insights (operator's takeaways). Always asks which mode to run
  before processing. Accepts pasted transcript text, a YouTube URL, or a file path. Customized
  for the Learning Hub: displays inline, offers to save the breakdown as a local note, can
  register the video as a hub custom topic, and can optionally add the URL to a NotebookLM
  notebook as a source. Trigger on: "youtube breakdown", "break down this video", "analyze
  this video", "summarize this transcript", "study notes for this video", "critique this
  video", "what should I do with this video", or any request to process YouTube content into
  structured notes for the hub.
---

# YouTube Breakdown — Learning Hub edition

Process a YouTube transcript into one of four structured breakdowns, then wire the result into
the **Learning Hub** instead of an external vault. Always ask which mode before generating —
don't auto-pick. The four modes are genuinely different tools, not reshuffled versions of the
same thing.

> **Customized for this repo.** This is the hub-native fork of a personal `youtube-breakdown`
> skill. The four mode prompts are kept intact (they're the value); the input/output handling,
> save location, frontmatter, and hand-offs are repointed at the hub: a local note, the
> `custom_topics` store, and (optionally) NotebookLM as a source — never an external Obsidian
> vault or Todoist.

---

## Mode Selection

When invoked, **always ask which mode to use** before processing. Present the four options:

```
Which mode?
1. Study Notes — deep, hierarchical, for videos worth retaining long-term
2. Quick Reference — ruthless distillation, for triage or recall-at-a-glance
3. Critique — steelman then dismantle, for skeptical engagement
4. Actionable Insights — actions + frameworks separated, for tactical content
```

If the trigger phrase clearly implies a mode (e.g., "critique this video" → Mode 3, "study
notes for this" → Mode 1), still confirm before running. Never auto-pick silently — the mode
choice shapes the entire output and is worth the one extra turn.

---

## Input Handling

| Input type | How to handle |
|---|---|
| **Pasted transcript text** | Use directly. No fetching needed. |
| **YouTube URL** | Fetch the transcript (a transcript service via `WebFetch`, or the YouTube Transcript API if available). If fetching fails, ask the user to paste the transcript. |
| **File path** | Read the file directly with the Read tool. |

If the input is ambiguous (a non-YouTube URL, or text too short to be a transcript), ask one
clarifying question before proceeding. Don't guess. For very long transcripts (>30k words),
warn that fidelity may drop and offer to chunk-process (run the mode against sections and
stitch).

---

## Output Handling (hub-native)

After generating the breakdown:

1. **Display it inline** — full output, properly formatted. This always happens and works in
   any session (cloud or local).
2. **Offer to save it as a local note.** Default location is the hub's gitignored data dir so
   personal notes stay out of git and out of the NotebookLM sidecars:

   ```
   Save to backend/data/youtube-notes/{slug}.md ?
   ```

   - **Slug:** `YYYY-MM-DD-{kebab-case-video-title}-{mode}.md`
     (e.g., `2026-06-06-andrej-karpathy-on-llms-study-notes.md`). If the title is unknown, use
     `YYYY-MM-DD-youtube-breakdown-{mode}.md` and offer to rename.
   - **Frontmatter:**

     ```yaml
     ---
     title: [video title]
     source: [URL if available, else "pasted transcript"]
     speaker: [if identifiable, else "unknown"]
     date_processed: [today's date, YYYY-MM-DD]
     mode: study-notes | quick-reference | critique | actionable-insights
     tags: [youtube, learning-hub, {mode}]
     notebook_id: [set only if added as a NotebookLM source below, else omit]
     custom_topic_id: [set only if registered as a custom topic below, else omit]
     ---
     ```

     The `mode` field uses the kebab-case forms exactly (`study-notes`, `quick-reference`,
     `critique`, `actionable-insights`) — don't capitalize or pluralize.
   - `backend/data/` may not exist until the backend has run once; create the
     `youtube-notes/` subdir if needed (it's under the gitignored data dir, so this is safe).

3. **Offer to register it as a hub custom topic** (the hub's home for non-NotebookLM
   interests — a book, a YouTube series, a loose thread):

   ```
   Register "[title]" as a custom topic in the hub so it shows on the home screen?
   ```

   > **Status — needs a small backend writer.** The `custom_topics` table exists
   > (`backend/app/store/schema.py`) but has **no writer yet** (Phase 5). When the
   > `custom_topics` CLI lands (see BACKLOG.md → "custom_topics writer"), this step will run:
   >
   > ```
   > cd backend && .venv/bin/python -m app.topics.custom add \
   >   --title "<title>" --notes-file backend/data/youtube-notes/<slug>.md \
   >   --progress 0
   > ```
   >
   > It should follow the `app.quiz.session` convention exactly: run from `backend/` via the
   > project venv, print JSON, write through `app.store.db`. Until it exists, **don't fake it**
   > — save the local note (step 2) and tell the user registration is a pending follow-up.

4. **Optional bridge → NotebookLM (gated).** If the user wants this video to become a tracked
   NotebookLM topic (so `audio-series` / `episode-review` can build on it), offer to add the
   URL as a source — **only with explicit confirmation each time**:

   ```
   Add this URL as a source to a NotebookLM notebook via nlm? (writes to NotebookLM)
   ```

   This is an authoring action toward NotebookLM (like the `audio-series` skill), distinct from
   the hub's read-only-toward-sidecars rule. Use the `nlm-skill` for the exact command. Record
   the resulting `notebook_id` in the note's frontmatter. If `nlm` auth has lapsed, tell the
   user to run `nlm login` — don't retry blindly.

5. **If the user declines everything**, leave the output inline. Don't push.

---

## Mode 1: Study Notes

**For:** videos worth retaining long-term — technical lectures, deep educational content,
frameworks to reference later. Run this prompt against the transcript:

````text
You are an expert study-notes generator. Internalize the transcript deeply enough to teach it,
then produce a hierarchical outline optimized for learning and retention.

# PHASE 1: COMPREHENSION (internal, do not output)
1. Identify the domain, the speaker's expertise, and the core thesis.
2. Map the logical structure: claims, supporting evidence, how ideas connect.
3. Flag where the speaker glosses over nuance, makes unsupported claims, or omits counterpoints.

# PHASE 2: OUTPUT (strict H1 → H2 → H3 → bullets; concise but thorough)
## 1. Snapshot
- Title/Topic, Speaker & credibility signals, Core thesis (1 sentence), Who this is for.
## 2. Key Arguments & Claims  (for each of 3–7)
- Claim → supporting evidence/reasoning → illustrative quote/example → Strength [Strong/Moderate/Weak] and why.
## 3. Mental Model / Framework
- Render any framework as a clean hierarchy with definitions, or "No explicit framework."
## 4. Counterpoints & Gaps
- Unstated assumptions, missing counterarguments, oversimplifications, claims I'd verify.
## 5. Action Items & Takeaways
- Top 3 insights to retain (ranked), things to actually do, connections to adjacent domains.
## 6. Further Reading & Next Steps
- Sources cited, natural next rabbit holes (3–5 with one-line why), single highest-leverage next step.

# RULES
- Never invent citations, quotes, or facts not in the transcript. Flag unclear points; don't guess.
- Prioritize clarity over comprehensiveness. Plain language; define jargon on first use.
````

**After this mode**, append a hub hand-off to the inline output (not the saved file):

```
💡 The "Further Reading" above is good seed material — want me to add this video to a
NotebookLM notebook as a source (→ /notebook-assist), or register it as a hub custom topic?
```

---

## Mode 2: Quick Reference

**For:** triaging videos, deciding what deserves deeper attention, recall-at-a-glance.

````text
You are a transcript distiller. Produce a scannable reference the reader could re-read in under
60 seconds and recall the video's contents.

# PHASE 1: COMPREHENSION (internal)
1. Identify the thesis and the 2–5 ideas that actually matter.
2. Cut throat-clearing, payoff-free anecdote, elaboration of already-clear points.

# PHASE 2: OUTPUT (scale length to density; err shorter)
## Snapshot — Topic (one line); Thesis (one sentence); Verdict [Worth it / Skim / Skip] + why in one line.
## The Core Ideas — bullet list, one idea each, fewest words that preserve meaning.
## Memorable Specifics — only if genuinely memorable (stat, phrase, example); 3–5 max; skip if none.
## If You Remember Only One Thing — one sentence.

# RULES
- No filler, no "the speaker discusses…" framing — state the content. No invention. Short, active sentences.
````

---

## Mode 3: Critique

**For:** bold/contrarian claims, frameworks under consideration, advice to pressure-test.

````text
You are a rigorous intellectual critic. Engage seriously — strengthen the argument first, then
dismantle it where warranted.

# PHASE 1: COMPREHENSION (internal)
1. Identify the thesis and argument structure (premises → reasoning → conclusion).
2. Separate what is claimed from what is supported. Note credibility signals, incentives, rhetorical moves.

# PHASE 2: OUTPUT
## 1. The Argument, Charitably Reconstructed — steelman in 3–6 bullets, including implied premises.
## 2. What They Got Right — claims that hold up, genuine contributions, non-obvious strengths.
## 3. Where the Argument Breaks Down — for each weakness: the problem, why it matters, the stronger counter-position.
## 4. Unexamined Assumptions — 3–5 a thoughtful skeptic would question.
## 5. The Verdict — is the core thesis correct? [Yes/Partially/No/Can't tell] + reasoning; what it does well; what to distrust; who should watch anyway.
## 6. Deeper Reading — sources that challenge it, sources that defend it better, adjacent thinkers.

# RULES
- Steelman before critiquing (non-negotiable). Distinguish "I disagree" from "this argument is weak."
- No manufactured disagreement; if it's good, say so. No invented sources — recommended books must exist.
````

**After this mode**, append:

```
💡 The "Deeper Reading" above is good seed material — want me to add this video to a NotebookLM
notebook as a source (→ /notebook-assist), or register it as a hub custom topic?
```

---

## Mode 4: Actionable Insights

**For:** how-to / productivity / business / tactical content — when the user wants a plan.

````text
You are an implementation-focused analyst. Extract what the user can actually use — separated
into individual actions and adoptable frameworks.

# PHASE 1: COMPREHENSION (internal)
1. Identify every claim, technique, heuristic, framework.
2. For each: actionable or merely interesting? Discard the merely interesting.
3. Distinguish one-time actions from repeatable systems.

# PHASE 2: OUTPUT
## Snapshot — Topic; Core premise (one sentence); Implementation difficulty [Low/Medium/High] + why.
## 1. Personal Action Items — ranked by leverage. Each: **[Action]** — [why it matters] — [first step]. Specific, doable this week, tied to an outcome.
## 2. Frameworks & Systems to Adopt — for each: Name; the framework (clean hierarchy); when to use; when it fails (infer if unstated).
## 3. Heuristics Worth Internalizing — 3–7 one-sentence rules of thumb.
## 4. What to Skip — claims that sound actionable but aren't (too vague / context-dependent).
## 5. Implementation Sequence — if adopting everything worth adopting, in what order (numbered, one-line rationale).
## 6. Further Resources — to go deeper, tools/templates mentioned, single highest-leverage next step.

# RULES
- Separate actions from frameworks cleanly. No vague advice. If nothing's actionable, say so. Rank ruthlessly.
````

**After this mode**, append:

```
💡 Want me to capture this video as a hub custom topic with these action items as its notes?
(Once the custom_topics writer lands — see BACKLOG.md — this becomes a one-step save.)
```

---

## Workflow Summary

1. **Confirm or ask the mode** (never auto-pick silently).
2. **Receive the transcript** (paste / URL / file path).
3. **Run the appropriate mode prompt.**
4. **Display the breakdown inline** — full output.
5. **Append the mode's hub hand-off line.**
6. **Offer to save** the local note (`backend/data/youtube-notes/{slug}.md`) with frontmatter.
7. **Offer the hub integrations** — custom-topic registration (when the writer exists) and the
   optional, gated NotebookLM source-add.

---

## Key Guardrails

- **Always ask which mode** before running, even when the trigger implies one.
- **Never invent content.** Every mode prompt has a no-invention rule — honor it.
- **Don't auto-save and don't auto-write to NotebookLM.** Every save / source-add is offered,
  then waits for an explicit yes.
- **One mode per run.** For multiple modes on the same transcript, run sequentially with
  separate save prompts. Don't batch outputs into one file.
- **Frontmatter precision** — kebab-case `mode` values exactly; only set `notebook_id` /
  `custom_topic_id` when those integrations actually ran.
- **Stay out of the sidecars.** Saved notes go to `backend/data/youtube-notes/` (gitignored),
  never to `~/Projects/NotebookLMs/`. The hub is read-only toward NotebookLM sidecars.
- **Cloud vs local:** the breakdown + inline output work anywhere; saving a note and the `nlm`
  source-add need the local machine (filesystem + `nlm` auth).
