# Study Scheduler — opt-in Calendar time-blocks for a course or path

**Status:** Backlog idea — captured 2026-07-22 (direct capture at Kyle's request, **not** via
`/brainstorm`; no divergence run, no critic gate). Not scheduled; **no build authorized** — this
is a parking-lot write-up. Two framing decisions were settled with Kyle at capture time
(opt-in surface · write-gating); the rest are open questions below. _Revised 2026-07-22: the
calendar-write gate was loosened from approve-each-block to **approve-the-plan-once, then
batch-write** — Kyle's call that a self-only, non-communicating, trivially-reversible calendar
block does not need the Overnight email-send bar._

_On a specific course or learning path, Kyle can opt into a scheduling assistant that (with his OK) reads his Google Calendar free/busy, works out how long study sessions should be, proposes concrete time-blocks for the next steps — going over a study guide, listening to an audio overview, taking a quiz, or several at once — and, once he reviews and confirms the proposed set in one pass, writes the whole batch into his calendar so the study plan has real time defended on it._

## Premise

Home Base's learning arc is converging on one shape: an **ordered sequence of steps you complete
in order.** A **Course** (`app.courses`, human/`build-course`-authored — lessons · diagrams ·
flashcards · quizzes · reading) already is this. **Learning Paths (M8, in flight** —
`docs/ideas/learning-paths.md`, PRs #129/#130) makes the Learning tab this too: an AI-composed
path of steps — 🎧 audio → 📖 read → 🃏 flashcards → ❓ quiz → ✨ bridge-check → ✍️ reflect — over
a NotebookLM topic, with a `path.json` sidecar and a two-lane "Continue / Review" Plan. The M8
doc is explicit that Paths and Courses "share the engine underneath."

What that engine has never had is **time.** The app knows *what's next* (`courses/next_actions.py`,
the Path's Continue lane) and *what's due* (the SM-2 Review lane, `study_plan.py`). It does not
know *when Kyle will actually do it* — the study plan lives entirely inside the app, competing
for attention with a calendar it can't see and can't touch. The gap between "I have a designed
path" and "I finished it" is unprotected time. This idea closes that gap by giving one opted-in
track the ability to defend real blocks on the calendar Kyle already runs his day from.

**Why now (as a captured idea):** M8 makes "a track = an ordered list of steps" a first-class,
durable object with a sidecar. The moment steps are enumerable and (roughly) estimable in
minutes, "schedule the next N steps against my free/busy" becomes a small, well-defined reader
on top — not a new subsystem. Capturing it now keeps it in view while the Courses/Learning work
is warm, without pulling build focus off M8.

## The bet

That for the **one or two** tracks Kyle is actively serious about at a time, the thing that
converts a good study plan into finished lessons is **defended calendar time he agreed to**, not
another in-app to-do list. And that Home Base can cross from "reads the world / reports on Kyle"
into "writes on Kyle's real calendar" with a **light, honest** gate: propose a set of blocks →
Kyle reviews and confirms the plan once → it writes the batch. The opt-in-per-track scope is
load-bearing: this is deliberately *not* a global always-on scheduler, because the honest use is a
small number of tracks, and a narrow surface is a safer place to first hand the app a write key to
an external account.

Crucially, this write is **not** the Overnight email-send seam and does not need its bar. A
calendar block lands only on Kyle's **own** calendar, **communicates with no one**, and is
**trivially reversible** (delete the event). That reversibility + self-only nature is what lets the
gate be a single plan-level confirm rather than a per-block tap — Kyle's explicit call
(2026-07-22) that the earlier approve-each framing over-taxed a low-stakes action. (Contrast
Overnight Chief of Staff, whose draft-only/graded-earn gate is calibrated to *outbound,
hard-to-reverse* actions like sending mail.)

## Decisions settled at capture (2026-07-22)

1. **Opt-in per track, not global.** The scheduling assistant is an explicit toggle Kyle turns on
   for a specific track — expected to be live on ~1–2 tracks at once, off everywhere else. Kyle's
   chosen **primary opt-in surface is a Course** (per-course toggle on `CourseDetail`).
   **Extension recorded at capture:** because Learning Paths (M8) are the same ordered-step shape
   on the shared engine, the toggle should also live on a Path — the scheduler reads *steps +
   estimated minutes* from either a `course.json` or a `path.json`, so build it against that
   shared abstraction rather than Courses alone. (Kyle picked "Courses" before the M8 Learning
   Paths feature surfaced in this session; this line reconciles the pick with that discovery — if
   he wants Paths-first or Paths-only, it's a one-line change here.)
2. **Calendar WRITE is approve-the-plan-once, then batch-write** _(revised 2026-07-22 from
   approve-each-block)._ The assistant negotiates session length and suggests slots from
   free/busy, then surfaces the **proposed set** of blocks; Kyle reviews and confirms it in **one
   pass**, and the whole batch is written to Google Calendar — no per-block tapping. He can still
   drop or tweak individual blocks in that review, but the default gesture is one confirm for the
   plan. Why lighter than Overnight: a calendar block is self-only, communicates with no one, and
   is trivially reversible (delete the event), so it doesn't warrant the email-send bar — Kyle's
   explicit call that approve-each over-taxed it. **Going fully unattended/recurring later** (the
   scheduler maintaining blocks each week without a confirm) is a plain later upgrade Kyle can flip
   on, **not** something a track must *earn* through an M0-style graded week. The one hard rule
   that stays: every written block must be cleanly removable, so nothing it does is stuck.

## Open questions (settle at build time)

1. **Google auth + secrets.** This repo has **no** Google OAuth today. Reading free/busy and
   writing events needs an OAuth client + token storage + scope handling (`calendar.events` +
   free/busy) — a genuinely new external integration and a new secret to manage, on a project
   whose whole stack is currently local + subscription-lane. Which calendar (primary vs a
   dedicated "Study" calendar Kyle can mute/hide)? Dedicated calendar is the safer default.
2. **Where do step durations come from?** To block time you need per-step minutes. Some are
   knowable (an audio overview has an MP3 length; a quiz ≈ N questions × a per-question estimate;
   a study guide ≈ word count / reading rate); others need a default or a Kyle-set estimate. The
   "work with me on how long sessions should be" negotiation is partly *this* — pick a session
   length, then pack whole steps into it. Does the scheduler pack multiple short steps into one
   block ("audio + quiz" in a 45-min session), and how does it avoid splitting a step across two
   blocks?
3. **One-off vs recurring.** A fixed weekly "Tues/Thurs 7–8pm study" recurring block, vs
   freshly-proposed one-off blocks each week from live free/busy, vs a hybrid (recurring skeleton,
   contents re-picked). Recurring is calmer; one-off adapts to a changing calendar.
4. **Missed / moved blocks.** If Kyle blows past a block or the step's already done, what happens —
   does the assistant notice completion (the step store already knows) and reclaim/re-propose the
   time, or is it fire-and-forget once written? Closing this loop (block ↔ actual step completion)
   is what separates a real study-adherence tool from a dumb calendar-stuffer.
5. **How much LLM, if any.** Slot-finding against free/busy and packing steps into a session are
   **deterministic** and want no model. The only genuinely LLM-shaped part is conversational
   negotiation phrasing ("does Thursday 7pm work, or is that too close to dinner?"), which could be
   the M5 grounded `claude -p` lane or just a plain chooser UI. Default to deterministic; add the
   `claude -p` lane only if the negotiation feels worth it.
6. **Timezone / DST** correctness on writes (Kyle is CT) — small but a classic footgun for
   calendar-event writers.

## Credible first step (when/if built)

Anchor on a Course (Kyle's chosen surface) that already has completable steps. (a) Add a persisted
**opt-in flag + block ledger** in `learning-hub.sqlite` — a new small table keyed by track id, in
the style of `custom_topics` / `brief_notes`, never in a sidecar (sidecars stay read-only per the
`guard-sidecars` invariant). (b) Behind that flag, a deterministic **session planner** that reads
the track's next incomplete steps + a first-cut duration model, plus a **read-only** Google
free/busy pull, and produces a *proposed set* of blocks. (c) Surface the set in a **review-and-
confirm** view (individual blocks droppable/tweakable) — one confirm writes the whole batch via
the Calendar API; nothing writes before that confirm. Prove the read + the batch-confirmed write
end-to-end on one course before touching recurrence, Learning-Path parity, or completion-reclaim.
Route via `/explore-plan` (the OAuth + external-write surface wants an approved plan before code).

## Dependencies

- **Ordered-step source (read):** `backend/app/courses/manifest.py` + `next_actions.py` +
  `course.json` sidecars + lesson-completion store (`backend/app/store/db.py`); and — for Path
  parity — M8's `path.json` + its step/Continue-lane model (`docs/ideas/learning-paths.md`, PRs
  #129/#130). **M8 should land first** if this is built against Paths.
- **"What's due / session budgeting":** `study_plan.py` + `planner.py` (the minutes-budget +
  interleaving already exist and are reusable for session packing).
- **Batch-confirm write pattern:** Overnight Chief of Staff's approve/discard queue
  (`docs/ideas/overnight-chief-of-staff.md`, PR #107) and the `create_brief_note` write path in
  `backend/app/api/brief.py` as the review/write model; the `Brief.tsx` Overnight strip as the UI
  precedent (here it's one confirm for the batch, not per-item).
- **NEW, not in repo today:** a Google OAuth client + token store + Calendar/free-busy API
  wiring, and a new persisted opt-in/block table in `learning-hub.sqlite`. A new external secret
  to manage.

## Explicitly out of scope (revisit later)

**Unattended / automatic** calendar writing in **v0** — v0 writes only after Kyle confirms the
proposed plan; the scheduler maintaining blocks each week with no confirm is a plain later upgrade
he can flip on (not a graded-gate earn). No write to any
account other than the chosen Google Calendar. No global "schedule everything" mode — opt-in per
track only. No rescheduling/notifying integrations (Todoist, the vault stack) — this is
Calendar-only; the vault ecosystem already reads Calendar separately and is not this repo's job.
Not a general calendar manager — it only ever proposes/writes *study* blocks for an opted-in
track.

## Identity/positioning note

identity-shift: Home Base's learning section stops living **only inside the app** and starts
**defending time on the calendar Kyle runs his life from** — the learning verb gains a "when,"
not just a "what next." It's also the project's **second** deliberate step from *reporting* into
*acting on an external account* (after Overnight Chief of Staff), and the first that writes to a
Google service — kept honest by a light one-pass plan-confirm plus the fact that a study block is
self-only, non-communicating, and trivially reversible (a deliberately lighter gate than
Overnight's, because the action is far lower-stakes). Distinct from the vault/Cowork stack
(which *reads* Calendar for briefing): this *writes* study blocks, scoped to one opted-in track.
