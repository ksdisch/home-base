# Master Plan — Home Base

_The **one document** that shows the whole plan and where it stands. The detailed per-phase/
per-milestone plans stay where they are (linked below); this page is the unified progress view
so nobody has to click through a dozen docs to see the state of the project._

> ## 🔄 This is a LIVING document — the maintenance contract
> **Any session that starts, finishes, or reshapes a piece of the plan MUST update this file
> in the same commit/PR as the work**: tick the checkbox, adjust the status column, move the
> card on the Kanban board below, and touch the "Last updated" line. Adding a brand-new
> plan/milestone doc? Add it to the checklist, the board, and the doc map here.
> The rule that enforces this lives in `CLAUDE.md` → "Master plan upkeep".

**Last updated:** 2026-07-20 (seventeenth entry) · **W3 item 2/7 — QU4 jump-to-topic chips ✅ shipped** (PR #96, RED→green + a single-topic pin): anchor nav over the frozen `sweeps/topics.json` order ([jump-to-topic-chips](ideas/jump-to-topic-chips.md)) — each TopicSection gains `id={topic.slug}` + `scroll-mt-24`, and a sticky chip row (one chip per rendered topic, single horizontally-scrolling line, tucked under the app header) scrollIntoView-smooths the tapped section. Open questions decided: every served topic gets a chip uniformly (no dimming — reorder/relevance stays the later, larger move), the row hides for a single-topic brief (nothing to skip), horizontal scroll over wrap (one line of phone vertical space). Pure client-side; no data, API, or order change. Frontend 89 → **91**, typecheck clean, backend 555 untouched. Next: W3 item 3 — FR15 Today-survives-navigation. · **W3 item 1/7 — QU3 audio resume ✅ shipped, WAVE 3 STARTED** (PR #95, 3 RED→green): the bare M4 `<audio>` on Today gains position memory ([audio-resume](ideas/audio-resume.md)) — onTimeUpdate writes currentTime to localStorage keyed `audio-pos-<brief.date>`, onLoadedMetadata seeks back to any saved spot before first play, onEnded clears the key (the idea doc's open question decided: a finished brief starts fresh next open). Date-keyed storage self-invalidates when tomorrow's brief lands; the handlers sit on the element itself so the FR15 hoist can carry them unchanged (no double-managed position); #15 onError→hide untouched; zero backend/API surface. Frontend 86 → **89**, typecheck clean, backend 555 untouched. Next: W3 item 2 — QU4 topic chips. · **W2 batch 6/6 — notes UX ✅ shipped, WAVE 2 COMPLETE** (PR #93, 7 RED→green under fake timers; two prior immediate-commit tests rewritten to the deferred contract): **FR10** ([destructive-tap-undo](ideas/destructive-tap-undo.md)) one shared hold-then-fire primitive (`components/undo.tsx`: `useUndoable` + `UndoToast`, 5s window) wraps all three thumb-reach destructive taps — News "Not interested" (the −8 signal defers), /notes Delete, Today's inline ✕: the UI change stays optimistic, **Undo restores and the API is never called**, timeout/second-tap/unmount commits so a route change can't lose the tap; no ranker/weight/layout change, only the timing · **#14** `/notes` derives `effectiveTopic` (filter falls back to All when its topic no longer exists) for both visibility and the select — deleting the filtered topic's last note can't strand a false 'No notes yet' · **#17** a failed delete gets its own state + accurate "Couldn't delete the note" banner (row restores) — never again under the load-failure heading over a loaded list. Frontend 81 → **86**, typecheck clean, backend 555 untouched. **Wave 2 (correctness sweep) is COMPLETE — 6 test-first batches in one day: #87 sweep/brief pipeline · #89 LLM-lane · #90 news resilience · #91 offline/PWA honesty · #92 store safety · #93 notes UX; all 14 non-courses bug lows + HA2/HA4/HA8/HA11 + FR10 closed; backend 524 → 555, frontend 76 → 86 across the wave.** Next per the roadmap: Wave 3 (walk & phone) — or the standing open items (M6 phone trio · ~08-03 v1 check). · **W2 batch 5/6 — store safety ✅ shipped** (PR #92, 5 RED→green + a fresh-store pin): **HA11** ([pre-migration-snapshot](ideas/pre-migration-snapshot.md)) `init_db` copies the store's bytes to a timestamped `.bak-<utc>` sibling **before** the migration loop — unconditional, deliberately NOT gated on the schema_migrations ledger (the 2026-07-16 drift incident is where the ledger lies), fresh/empty store skips, failed copy never blocks startup, newest **5** kept; a failing-migration test proves the restorable .bak sits beside the damage · **#9** `compute_streaks` parses `activity.day` per row and skips unreadable ones — a poisoned row from the out-of-app sqlite surface can no longer permanently 500 `GET /api/progress` (pure + end-to-end tests). Backend 549 → **555**, ruff clean, frontend untouched. Next: W2 batch 6 (last) — notes UX (FR10 undo toast · #14 stranded filter · #17 wrong error banner). · **W2 batch 4/6 — offline/PWA honesty ✅ shipped** (PR #91, 4 RED→green + pins; the real `public/sw.js` now executed in tests via a `?raw` harness — injected self/caches/fetch, hand-driven fetch events): **#15** sw.js pairs cached audio with its brief date (synthetic `/__cached-brief-date` entry) and **evicts the audio when a different-dated brief caches** — offline Saturday can't play Tuesday's narration; Brief.tsx hides the player on a media error, so the iPhone's never-cached (Range→206) and evicted cases get *no player* instead of a broken one · **#16** the per-note ✕ delete finally honors offline: `disabled={readOnly}` + the composers' title treatment — the one write that escaped the M6 pass · **#8** the SPA catch-all registers unconditionally and checks `frontend_dist` **per request** — 404 before the build, index.html the moment `make build` lands, making the installer/README no-restart promise true under the KeepAlive agent (assets served by the catch-all until the /assets mount exists at next start; no-dist behavior unchanged). Backend 548 → **549**, frontend 76 → **81**, typecheck + ruff clean. Next: W2 batch 5 — store safety (HA11 pre-migration snapshot · #9 progress 500 on a bad row). · **W2 batch 3/6 — news resilience ✅ shipped** (PR #90, 3 RED→green + a no-cache pin): **HA8** ([empty-feed-drift-guard](ideas/empty-feed-drift-guard.md)) `get_category_items` refuses to overwrite a non-empty cache with a parsed-empty result — serves last-good marked `stale` + logs the drift, extending the serve-last-good philosophy from fetch failure (P1 #3) to the parse-that-looks-like-success case, so a Google-News markup reshape can't blank a category invisibly (no cache to protect → an empty parse stays an honest empty page) · **#12** `append_roster_topic` serializes its read→dupe-check→write→replace behind a module lock + mkstemp unique tempfile — two scout Adds can't silently drop the loser's roster entry (regression test parks two racers deterministically via a timeout-barrier) · **#13** the scout's ≥3-distinct-days gate buckets on **America/Chicago** days via `_local_day()` (attach-UTC-then-convert, mirroring `_decay`) — two evening sittings straddling UTC midnight stay one reading streak (same root cause as P1 #4). Backend 544 → **548**, ruff clean, frontend untouched. Next: W2 batch 4 — offline/PWA honesty (#15 audio-date pairing · #16 offline delete · #8 per-request dist). · **W2 batch 2/6 — LLM-lane containment ✅ shipped** (PR #89, 9 RED→green regression tests, existing lane tests untouched): **#10** `_scrubbed_env` in chat.py + regen.py and the launchd wrapper's `unset` now drop the full lane-switching set (`ANTHROPIC_API_KEY` · `ANTHROPIC_AUTH_TOKEN` · `ANTHROPIC_BASE_URL` · `CLAUDE_CODE_USE_BEDROCK` · `CLAUDE_CODE_USE_VERTEX`) — the documented subscription-lane guarantee now enforced for every var the claude CLI actually reads · **#23** both `claude -p` lanes pass `--tools ""` (the CLI's documented disable-all-tools switch — enforced, not assumed from -p auto-deny defaults) and run from an empty TemporaryDirectory cwd, so the child can no longer load this repo's CLAUDE.md/.claude settings or default-read the repo · **HA4** ([untrusted-item-framing](ideas/untrusted-item-framing.md)): both `build_prompt`s wrap the spliced text in explicit delimiters (`<untrusted-item>` for the brief item, `<untrusted-current-material>` for regen) + a data-not-instructions framing sentence, adversarial payload-inside-delimiters tests pinning it — #23 bounds the blast radius, HA4 guards the input side, independent and both wanted. Backend 535 → **544**, ruff clean, frontend untouched. Next: W2 batch 3 — news resilience (HA8 parsed-empty guard · #12 roster write lock · #13 scout UTC gate). · **W2 batch 1/6 — sweep/brief pipeline ✅ shipped** (PR #87, 6 RED→green regression tests + 6 pins, sweep.sh tested as a real subprocess from a sandbox tree — stub `claude`, no-op audio, real envelope.py/renderer): **#7** an unreadable sweep file degrades one topic instead of 500ing Today (`OSError` joins the json fallback tuple; `_fallback_topic`'s md read → the honest 'no readable brief' card) · **#6** dedup URL identity keeps the query string — watch?v=AAA ≠ watch?v=ZZZ; only fragment, trailing slash, and tracking params (utm_*, fbclid) are noise, so false 'developing' labels off query-keyed URLs are gone · **#22** sweep.sh renders into a mktemp stage dir inside `$OUT_DIR` and mv-renames artifacts into place (.md first, then the .json it backs; same-fs atomic rename, server ignores subdirs, failures still land .raw.txt) — the always-on server can never read a half-written `<topic>.json`, and **render_brief.py stays frozen** · **#19** sweep plist `RunAtLoad=true` + honest comment (launchd replays missed calendar fires only after *sleep* — a reboot morning got no sweep all day); safe because run-scheduled.sh's `SWEEP_SKIP_DONE=1` no-ops an on-load fire on swept days (pinned by its own test); **live-verified post-merge**: `install-schedule.sh` re-run from the main checkout (manages both agents); the RunAtLoad on-load fire ran the wrapper — 8/8 topics skipped (`SWEEP_SKIP_DONE`), audio skipped itself, `rc=0` in seconds (19:18 CT entry in `data/sweeps/logs/2026-07-19.log`) — reboot coverage proven with zero re-sweep, and the heartbeat's own on-load fire stayed quiet (ledger 12h old, no Desktop flag) · **HA2** same-day re-sweep note-detach guard in sweep.sh ([resweep-note-detach-guard](ideas/resweep-note-detach-guard.md)): dependency-free stdlib-sqlite count of notes attached to (topic, today) before overwrite → loud warning naming the count, tty confirm, non-tty refuses without `SWEEP_FORCE=1`; scheduled lane unreachable by design. Backend 524 → **535**, ruff clean, frontend untouched. Roadmap wording corrected: W2 = the **14 non-courses** bug lows (the 4 courses lows #11/#18/#20/#21 are W4's batch). Next: W2 batch 2 — LLM-lane containment (HA4 untrusted-item framing · #23 tools/cwd · #10 env-scrub set). · **W1 PR12 — heartbeat dead-man's switch ✅ shipped, WAVE 1 COMPLETE** (PR #85, 5 subprocess tests RED→green against the real script): new `com.homebase.heartbeat` LaunchAgent (09:00 + RunAtLoad — login coverage closes the watcher's own post-reboot blind spot) runs `sweeps/schedule/heartbeat.sh` — newest ledger `ts` (mtime fallback for a mangled row) → **>36h silent** plants `~/Desktop/HOMEBASE-STACK-SILENT.txt` (what to check + kickstart command; auto-removed on recovery) then a macOS notification best-effort; missing ledger alerts, never passes. Deliberately dependency-free (bash + system tools, no venv/node/claude, BSD/GNU fallbacks) so it can't die the pipeline's way. `install-schedule.sh` manages both agents. Backend 519 → **524**. **Mac install + live verify ✅ same session**: both agents bootstrapped into gui/501 (plists present, loaded); the RunAtLoad fire read the *real* ledger — `heartbeat ok — newest ledger row 12h old (threshold 36h)` in `data/sweeps/logs/heartbeat.log`, no Desktop flag; a forced-stale run (`HEARTBEAT_THRESHOLD_HOURS=0`, flag → /tmp) exited 1, wrote the full SILENT flag, and fired the real macOS notification — both alert channels proven on the machine, test flag cleaned up. **Wave 1 (QU12 · PR5 · QU5 · PR12) done — Wave 2 (correctness sweep) promoted to Planned.** · **W1 QU5 — notes on News/For-You cards ✅ shipped** (PR #84, frontend RED→green + a backend contract pin, zero backend code changes): every News/For-You card gains a Note button + inline composer writing through the *existing* `POST /brief/notes` — `item.id` (sha1-link) as `item_id`, the **origin category slug** as `topic_slug` (For You credits the real section, mirroring `signal()`), local today as `brief_date`, headline snapshot; "✓ Saved" ack; interleaves on `/notes` via the humanized-title fallback; news notes count toward the ≥3 notes/week criterion automatically (`brief_habit_weeks` has no slug filter). Frontend 73 → **76**, backend 518 → **519**. Wave 1 remaining: PR12 heartbeat (local install). · **W1 PR5 — sweep-trust gauge ✅ shipped** (PR #83, regression tests first RED→green): `GET /brief/habit` gains `last_graded` — the newest `## YYYY-MM-DD` heading in the new **`docs/sweep-trust-log.md`** (env `TRUST_LOG`; missing/mangled log → None, never a 500), seeded with the M0 PASS baseline + the ~15-min monthly re-grade recipe on the M0 rubric. The habit strip renders a "Sweep trust:" line — muted while fresh, amber **"re-grade due"** past 30 days, loud "no accuracy grade on record" when the log is empty. No automated grading (assumption-4 gate respected) — the instrument makes neglect visible, the judgment stays Kyle's. Backend 515 → **518**, frontend 70 → **73**. Wave 1 next: QU5 notes-on-News. · **W1 QU12 — didn't-run banner ✅ shipped** (PR #82, regression tests first RED→green): `GET /api/brief` diffs the active (non-paused) roster against the slugs that produced a renderable file for the served day → new `BriefResponse.missing_topics` (roster order/titles; `.raw.txt`-only failures count as missing, fallback-`.md` topics don't — they render error cards; empty when there's no served day) + one warning Banner on Today naming the topics (suppressed offline like the stale hint, tolerant of pre-QU12 SW-cached payloads). Backend suite 510 → **515**, frontend 66 → **70**, typecheck + ruff clean. Wave 1 next: PR5 sweep-trust gauge. · **Backlog roadmap locked — wave order** (prioritization session, docs-only): the 2026-07-19 replenish (21 ideas + 18 low bugs) sequenced into four waves anchored on the ~08-03 v1 check — **W1** trust + liveness + notes funnel (QU12 → PR5 → QU5 → PR12-local; the standing Planned picks, order confirmed) · **W2** correctness sweep (all 18 bug lows + HA2/HA4/HA8/HA11 + FR10 in ~6 test-first subsystem batches) · **W3** walk-and-phone experience (QU3 → QU4 → FR15 → FR4 → FR13 → FR2 → QU1) · **W4** post-check decision points (moonshot pick — Mirror v0 recommended first · vault feed PR10 only if the habit wobbles · courses bug batch #11/#18/#20/#21). Kanban Later column re-cut from per-lane rollups to wave rollups; full order + rationale in the new "Roadmap" section below; `BACKLOG.md ## Open` stays the item-level record. · **Kanban Later column expanded** into per-lane replenish rollup cards (4 Moonshot · 3 QuickWin · 1 Premortem · 4 Harden · 5 Friction · 18 bug lows) so the board shows the pipeline depth — board polish only, no scope change; `BACKLOG.md ## Open` stays the item-level record. · **P1 bug fixes ✅ COMPLETE — all 5 medium 07-19 hunt findings fixed, one PR each, regression test first (RED→green):** **#1 blank-brief wake window** (PR #73 — `latest_sweep_date` skips contentless day dirs; brief/audio/chat all serve the newest renderable day) · **#2 promptless scout add** (PR #74 — the add stamps `prompts/<slug>.md` from the new checked-in `sweeps/prompts/_template.md` before the roster append; fails closed without a template; hand-tuned prompts never overwritten) · **#3 frozen news category** (PR #75 — per-feed error handling in `get_category_items`; healthy feeds serve + cache fresh, stale/502 only when every feed fails) · **#4 UTC streak days** (PR #76 — `activity.day` bucketed on the local calendar across all six raw-SQL writers + the injected-now writers + the `/api/progress` reader; SM-2/attempt timestamps stay UTC; far-TZ test fixture closes the audit's 12:00-UTC blind spot) · **#5 dev-vs-prod port clash** (PR #77 — dev.sh port guard refuses loudly naming `com.homebase.server` with the bootout/reinstall commands). Backend suite 493 → **510 tests**. Next planned: the trust + liveness cluster (QU12 + PR5 + PR12), then QU5 notes-on-News. · **Backlog replenish 2026-07-19 — docs-only:** post-M7 `bug-hunt` fan-out (27 raw → **23 verified findings**, 0 critical / 5 medium — [full report](bug-hunt/2026-07-19-post-m7.md), triage-only, nothing auto-fixed) + a five-lane `/brainstorm` (Moonshot long-leash · QuickWin · Premortem · Harden · Friction; 30 blind lenses → two-sided critic gates → 21 refined survivors, all captured by Kyle) → **21 vision docs in [`docs/ideas/`](ideas/)** + a new **`BACKLOG.md` `## Open` section** (21 idea stubs + 23 bug stubs, the 5 mediums tagged **[P1]** fix-first) + the Planned/Later Kanban refilled below. · **Courses M5 — the authoring loop in the hub: ✅ shipped** ([PHASE7_M5_PLAN](PHASE7_M5_PLAN.md) · PR #69) — **the course epic (M1–M5) is COMPLETE**: `app/courses/writer.py` becomes the ONE transactional write path (the CLI delegates; bundled examples + NotebookLM sidecars stay untouchable), `PUT` objectives + `PUT` order (complete-bijection reorder with fallback-id pinning so `course_lesson_progress` can never re-key), `POST` regenerate on the headless claude lane (per-type output contracts, validate-or-rollback so bad model output can't corrupt a course, `course-regen.jsonl` ledger), `GET` export zip + an `editable` flag, and an edit-mode Course UI (objectives editor · ↑/↓ reorder · Regenerate panel w/ stats-reset warning · Export). 493 backend (+37) & 66 frontend (+4) tests green. · Same-day context: **HB M0 — sweep quality week: ✅ CLOSED, verdict PASS** ([grades + audit](M0-sweep-grades.md)): full week graded (Day-0 audit + Kyle's 07-15 blanket B+ + a source-verified 07-16→18 audit, grades adopted by Kyle 07-19). Zero fabricated items across the week; market/fantasy excellent; AI passed **with a prompt tune** (`sweeps/prompts/ai-llms.md`: exclusion now carries the same sourcing bar as inclusion, after the Gemini-delay story was first missed then falsely dismissed as "low-quality blogs"). The five M0-gate overrides are all retroactively vindicated. · **PR #52 landed** (drafted 07-17): **migration ledger hardening** (`init_db` trusts the store's actual table shape over the `schema_migrations` ledger — re-runs forward migrations idempotently so a poisoned/orphaned ledger row can't silently skip one; poisoned-ledger + unknown-version regression tests) and **habit-metrics instrumentation for the v1 check** (`GET /api/brief/habit` + a self-hiding "Habit check" strip on Today: mornings vs 5 · notes vs 3 per local Monday-start week). · **HB M7 — news mode: ✅ shipped** (`docs/M7_PLAN.md` · PRs #58 RSS shell · #60 signals · #62 For You · #63 topic scout, + post-ship polish **#65** News in the mobile tab bar · **#66** Uplifting category · **#67** headline dedup). · **HB M6 — mobile: ✅ shipped** (`docs/M6_PLAN.md` #54 · PRs #55 + #56). Mac-side live verify clean 2026-07-18 (headless LaunchAgent, one-port serve, audio Range → 206, Tailscale up) and **real-iPhone reach verified 2026-07-18 (PR #64)**: full load over the ts.net HTTPS URL from the phone's tailnet IP, SW registered on the phone, first phone `POST /api/brief/visit` logged. **Remaining M6 evidence — Kyle's eyes-on trio**: home-screen standalone display, airplane-mode "Offline copy" banner, iOS audio scrub (+ reboot survival at next login).

---

## Where we are, in one paragraph

The repo has two arcs. **Arc 1 — Learning Hub** (the original SPEC build order, Phases 1–5,
plus extension Phases 6–7): **fully shipped**, including the SM-2 spaced-repetition core and
the **complete five-milestone Course pipeline** (M1 read+track · M2 quizzes+SM-2 · M3
generation at depth · M4 NotebookLM enrichment · M5 in-hub authoring loop, shipped 2026-07-19
— the epic's last line). **Arc 2 — Home Base** (kickoff 2026-07-13: the
morning-brief evolution): **M1, M2, and M3 are shipped** — M3 (hands-off automation, PR #43)
was built 2026-07-15 under Kyle's third deliberate override of the "wait for the M0 verdict"
gate, and its **first unattended 06:00 fire ran clean on 2026-07-16** (8/8 topics, rc=0,
fresh briefs + ledger rows). The kickoff's phased plan (M0–M3) is fully built, and Kyle
picked the encore on 2026-07-16 — **both halves shipped the same day**: **M4 — the audio
brief** (PR #45: a ~5-minute Kokoro-narrated MP3 rendered after every sweep, 🎧 player on
Today) and **M5 — chat with the brief** (PR #47: "Ask about this" on every brief item — one
grounded answer per question on the subscription lane, no web tools, keepers saved as
notes). **M0's sweep-quality grading week closed 2026-07-19 with a PASS verdict** (zero
fabricated items all week; one prompt tune to the AI sweep) — the Home Base kickoff plan
(M0–M3) plus its four encores (M4–M7) are now fully built *and* fully gated. The open
items are M6's phone-side eyes-on evidence (Kyle) and the ~08-03 v1 success-criteria check.

---

## Kanban

```mermaid
---
config:
  kanban:
    sectionWidth: 300
---
kanban
  done["✅ Done"]
    lh15["LH Phases 1–5 — SPEC<br/>build order: catalog ·<br/>quiz player · progress<br/>· review queue ·<br/>custom topics"]
    lh6["LH Phase 6 — SM-2 SR<br/>core + daily study<br/>plan + reflections<br/>journal"]
    lh7["Courses M1 — course<br/>sidecars, read+track<br/>API, Courses UI,<br/>/build-course"]
    lh7m2["Courses M2 — course<br/>quizzes in the quiz<br/>player + per-course<br/>SM-2"]
    lh7m3["Courses M3 —<br/>generation at depth:<br/>project/capstone +<br/>tracked rubrics ·<br/>course what-to-do-next<br/>· skill fan-out at<br/>depth"]
    lh7fc["Courses M2 remainder —<br/>flashcard review UI:<br/>dedicated session page<br/>+ per-card SM-2 + due<br/>chips"]
    lh7m4["Courses M4 —<br/>NotebookLM enrichment<br/>in-flow: catalog<br/>cross-link cards on<br/>course pages + gated<br/>link-or-generate skill<br/>flow"]
    hbm1["HB M1 — the brief<br/>page: Today route,<br/>/api/brief, visit log<br/>· PR 36"]
    hbm2["HB M2 — full 8-topic<br/>roster + inline notes<br/>+ Your-learning strip<br/>· PRs 38-39"]
    hbm3["HB M3 — hands-off:<br/>launchd 06:00 schedule<br/>+ dedup labels + cost<br/>ledger · PR 43 · first<br/>unattended fire<br/>verified 2026-07-16"]
    hbm4["HB M4 — audio brief:<br/>5-min Kokoro MP3 after<br/>every sweep + Today<br/>player · PR 45"]
    hbm5["HB M5 — chat with the<br/>brief: per-item Ask ·<br/>grounded answers,<br/>subscription lane, no<br/>web · save-as-note ·<br/>PR 47"]
    hbm6["HB M6 — mobile:<br/>one-port serve +<br/>LaunchAgent · sw.js v2<br/>cached last brief ·<br/>bottom tab bar +<br/>Today/Notes pass · PRs<br/>55-56 · Mac-side live<br/>verify clean 07-18,<br/>phone proof pending<br/>Kyle"]
    hbm7["HB M7 — news mode: RSS<br/>category shell ·<br/>news_events signal log<br/>+ card feedback · For<br/>You decaying-profile<br/>ranker w/ search-feed<br/>reach · topic scout →<br/>one-click roster adds<br/>· PRs 58/60/62/63 +<br/>polish 65-67 · live<br/>e2e proof clean 07-18"]
    hbm0["HB M0 — sweep-quality<br/>week: CLOSED 07-19,<br/>verdict PASS · zero<br/>fabrications all week<br/>· AI sweep prompt<br/>tuned · grades + audit<br/>in M0-sweep-grades.md"]
    cm5["Courses M5 — authoring<br/>loop in the hub:<br/>objectives editor ·<br/>reorder w/ id pinning<br/>· regenerate on the<br/>claude lane w/<br/>validate-or-rollback ·<br/>zip export · epic<br/>complete 07-19"]
    bugp1["Bug fixes P1 — all 5<br/>medium 07-19 hunt<br/>findings fixed 07-19,<br/>one PR each,<br/>test-first:<br/>blank-brief PR 73 ·<br/>promptless scout add<br/>PR 74 · frozen news<br/>category PR 75 · UTC<br/>streak days PR 76 ·<br/>dev-vs-prod port clash<br/>PR 77"]
    qu5["Wave 1 QU5 — notes on<br/>News/For-You cards:<br/>Note button →<br/>existing POST<br/>/brief/notes, origin<br/>slug credited,<br/>interleaves on /notes<br/>· PR 84"]
    wave1["Wave 1 — trust +<br/>liveness COMPLETE<br/>07-19: didnt-run<br/>banner QU12 PR 82 ·<br/>trust gauge PR5 PR 83<br/>· notes on News QU5 PR<br/>84 · heartbeat PR12 PR<br/>85 + Mac install"]
    w2b1["W2 batch 1 —<br/>sweep/brief pipeline:<br/>unreadable-file 500 #7<br/>· query-string dedup<br/>#6 · atomic render<br/>staging #22 ·<br/>RunAtLoad #19 ·<br/>re-sweep note guard<br/>HA2 · PR 87"]
    w2b2["W2 batch 2 — LLM-lane<br/>containment: full<br/>env-scrub set #10 ·<br/>tools-off + scratch<br/>cwd #23 · untrusted<br/>framing HA4 · PR 89"]
    w2b3["W2 batch 3 — news<br/>resilience:<br/>parsed-empty cache<br/>guard HA8 · roster<br/>write lock #12 ·<br/>local-day scout gate<br/>#13 · PR 90"]
    w2b4["W2 batch 4 — offline<br/>honesty: audio-date<br/>pairing + player hide<br/>#15 · offline delete<br/>#16 · per-request dist<br/>#8 · PR 91"]
    w2b5["W2 batch 5 — store<br/>safety: pre-migration<br/>snapshot HA11 ·<br/>bad-row-proof streaks<br/>#9 · PR 92"]
    w2b6["W2 batch 6 — notes<br/>UX: undo toast FR10<br/>(3 destructive taps) ·<br/>filter fallback #14 ·<br/>honest delete error<br/>#17 · PR 93"]
    wave2["Wave 2 — correctness<br/>sweep COMPLETE 07-19:<br/>6 test-first batches<br/>PRs 87 89 90 91 92 93<br/>· 14 low bugs + 4<br/>hardens + FR10 closed"]
  doing["🔄 In progress"]
    hbm6proof["HB M6 remainder —<br/>phone eyes-on<br/>evidence: home-screen<br/>standalone ·<br/>airplane-mode banner ·<br/>iOS audio scrub ·<br/>reboot survival · Kyle"]
    wave3["Wave 3 — walk and<br/>phone: QU3 audio<br/>resume done PR 95 ·<br/>QU4 topic chips done<br/>PR 96 · next nav<br/>survival FR15 → audio<br/>chapters FR4 →<br/>developing context<br/>FR13 → phone sweep<br/>trigger FR2 →<br/>yesterdays brief QU1"]
  next["📋 Planned"]
  decide["⏸️ Awaiting decision"]
  later["🧊 Later / parked"]
    wave4["Wave 4 — post-08-03<br/>decisions: moonshot<br/>pick, Mirror v0<br/>recommended (Readiness<br/>· Calibrated Doubt ·<br/>Overnight CoS on the<br/>bench) · vault feed<br/>PR10 only if habit<br/>wobbles · courses bug<br/>batch 11/18/20/21"]
    defer["Kickoff-deferred: ESPN<br/>· auto-courses ·<br/>alerts · public<br/>writing"]
```

_If the board above doesn't render in your viewer, the checklists below carry the same truth —
the board is a convenience view, the checklists are the record._

---

## Roadmap — replenish wave order (locked 2026-07-19)

_Prioritization session 2026-07-19: the replenish backlog (21 ideas + 18 low bugs) sequenced
into four waves. Organizing principle: everything that protects the ~08-03 v1 criteria
(≥5 mornings/week · events reach Kyle here first · ≥3 notes/week) ships before the check;
the big bets wait for its verdict. Ids are brainstorm-lane ids (QU/PR/HA/FR = QuickWin /
Premortem / Harden / Friction), **not** pull-request numbers; `BACKLOG.md ## Open` stays the
item-level record, with a vision doc per idea in [`ideas/`](ideas/)._

1. **Wave 1 — trust + liveness + notes funnel** — ✅ **COMPLETE 2026-07-19**: QU12 didn't-run
   banner (PR #82) → PR5 sweep-trust gauge (PR #83) → QU5 notes-on-News (PR #84) → PR12
   heartbeat (PR #85; Mac install + live verify done same session — healthy path read the
   real ledger, forced-stale run proved both alert channels; evidence in the Last-updated
   entry).
2. **Wave 2 — correctness sweep** — ✅ **COMPLETE 2026-07-19** (6 test-first batches,
   PRs #87 · #89 · #90 · #91 · #92 · #93; backend 524 → 555, frontend 76 → 86): the 14
   non-courses bug lows + the 4 hardens + FR10 (the 4
   courses lows #11/#18/#20/#21 are Wave 4's batch), batched into 6
   test-first subsystem PRs — sweep/brief pipeline (#7 #22 #19 #6 + HA2 re-sweep warn) ·
   LLM-lane containment (HA4 untrusted framing + #23 tools/cwd + #10 env-scrub set) · news
   resilience (HA8 + #12 + #13) · offline/PWA honesty (#15 #16 #8) · store safety (HA11
   pre-migration snapshot + #9) · notes UX (FR10 undo toast + #14 + #17).
   **Batch 1 (sweep/brief pipeline) ✅ shipped 2026-07-19, PR #87**: #7 unreadable-file
   500 · #22 atomic render staging (renderer stays frozen) · #19 RunAtLoad (reinstalled
   + live-verified same session: on-load fire = 8/8 SKIP_DONE no-op, rc=0) · #6
   query-string dedup identity · HA2 re-sweep note guard.
   **Batch 2 (LLM-lane containment) ✅ shipped 2026-07-19, PR #89**: #10 full env-scrub
   set (both claude lanes + the launchd wrapper) · #23 `--tools ""` + empty scratch cwd
   (both lanes) · HA4 untrusted-data framing in both build_prompts.
   **Batch 3 (news resilience) ✅ shipped 2026-07-19, PR #90**: HA8 parsed-empty cache
   guard (serve stale, never clobber) · #12 roster write lock + unique tempfile · #13
   scout persistence gate on America/Chicago days.
   **Batch 4 (offline/PWA honesty) ✅ shipped 2026-07-19, PR #91**: #15 sw.js audio-date
   pairing + error-driven player hide · #16 offline disables the per-note delete · #8
   per-request dist check (make build needs no restart).
   **Batch 5 (store safety) ✅ shipped 2026-07-19, PR #92**: HA11 unconditional
   pre-migration snapshot (newest 5 kept; failing-migration restorability proven) · #9
   bad-row-proof streak parsing.
   **Batch 6 (notes UX) ✅ shipped 2026-07-19, PR #93**: FR10 shared undo toast over
   all three destructive taps (Undo = zero API mutation) · #14 filter fallback · #17
   honest delete-error banner. **Wave closed.**
3. **Wave 3 — walk & phone experience** — 🔄 **in progress** (started 2026-07-20): QU3 audio
   resume → QU4 topic chips → FR15
   Today-survives-navigation → FR4 audio chapters → FR13 developing "what changed" → FR2
   sweep-from-the-phone → QU1 yesterday's brief. (QU3/FR15/FR4 all touch the audio player —
   the FR15 structural hoist lands before the things that build on it.)
   **QU3 audio resume ✅ shipped 2026-07-20, PR #95**: localStorage position memory on the
   M4 player — timeupdate saves keyed by brief date · loadedmetadata restores before first
   play · ended clears (open question decided: a finished brief starts fresh). Handlers on
   the element itself so the FR15 hoist carries them. Frontend 86 → 89.
   **QU4 topic chips ✅ shipped 2026-07-20, PR #96**: id={slug} + scroll-mt anchors on every
   TopicSection, sticky chip row under the app header scrollIntoView-ing each — every served
   topic gets a chip (no dimming), row hides for a single topic, horizontal scroll over wrap.
   Frontend 89 → 91.
4. **Wave 4 — post-08-03 decision points** (decisions, not commitments — gated on the v1
   check's verdict): the moonshot pick — **Mirror v0 recommended first** (cheapest
   deterministic bet, zero LLM/zero writes, doubles as instrumentation of the very behavior
   the check measures); Readiness Brief / Calibrated Doubt / Overnight Chief of Staff stay
   on the bench (Calibrated needs an M0-style graded week; Overnight needs its own gate
   conversation + the out-of-repo vault bridge; Readiness v0 risks feeling thin without the
   calendar join) · PR10 feed-the-vault **only if** the habit check wobbles (it is the
   antibody for exactly that failure) · courses correctness batch (#11 #18 #20 #21) in one PR.

Waves 1–3 are roughly two weeks at normal cadence, landing at the ~08-03 checkpoint.

---

## Arc 1 — Learning Hub (SPEC build order + extensions) — ✅ COMPLETE

The original product: a NotebookLM learning dashboard (see [`SPEC.md`](../SPEC.md)).
Phases 1–5 were the SPEC build order; 6–7 extended it.

| # | Milestone | Status | Plan doc | Evidence |
|---|-----------|:------:|----------|----------|
| 1 | Catalog + Home + Topic detail (read-only sidecar ingest) | ✅ shipped | [PHASE1_PLAN](PHASE1_PLAN.md) | June 2026 scaffold; parser anti-fabrication guards |
| 2 | In-hub quiz player (offline oracle, answer-key-free sessions) | ✅ shipped | [PHASE2_PLAN](PHASE2_PLAN.md) | `app/quiz/*`, `/api/quiz/*`, QuizPlayer UI |
| 3 | Progress dashboard (trends, streaks, shaky material) | ✅ shipped | [PHASE3_PLAN](PHASE3_PLAN.md) | `store/progress.py`, Progress page w/ inline-SVG sparklines |
| 4 | Mastery decay + "Review next" queue | ✅ shipped | [PHASE4_PLAN](PHASE4_PLAN.md) | `store/mastery.py`, `GET /api/review`, home badges |
| 5 | Custom (non-NotebookLM) topics on home | ✅ shipped | [PHASE5_PLAN](PHASE5_PLAN.md) | `/api/custom-topics` CRUD + "Custom" home section |
| 6 | SM-2 per-item scheduler + daily study plan + reflections journal | ✅ shipped | [PHASE6_PLAN](PHASE6_PLAN.md) | `store/scheduler.py`, `study/planner.py`, `GET /api/study-plan`, Plan page |
| 7 | Courses M1 — course-pipeline vertical slice | ✅ shipped | [PHASE7_PLAN](PHASE7_PLAN.md) | `app/courses/*`, `/api/courses`, Courses UI, `/build-course` |
| 7-M2 | Courses M2 — course quizzes in the player + per-course SM-2 | ✅ shipped | [PHASE7_M2_PLAN](PHASE7_M2_PLAN.md) | `7f2db03`; `course:<slug>` namespace, notebook aggregates filtered |
| 7-M3 | Courses M3 — generation at depth: project/capstone + tracked rubrics · course "what to do next" · skill fan-out at depth | ✅ shipped | [PHASE7_M3_PLAN](PHASE7_M3_PLAN.md) | PR #48; `course_rubric_assessment` (schema v6) · `GET /courses/{slug}/next` · `POST /courses/{slug}/assess` · rubric self-assessment UI |
| 7-M4 | Courses M4 — NotebookLM enrichment in-flow: catalog cross-link on course pages + gated skill flow | ✅ shipped | [PHASE7_M4_PLAN](PHASE7_M4_PLAN.md) | PR #50; `CourseMaterial.notebook` join via `_attach_notebook_refs` · Open-notebook card w/ counts + calm degrades · course-builder §5 two-path flow · **live proof verified 2026-07-16**: `jlens-global-workspace` course (syllabus-gated `/build-course`, `ok:true` zero warnings) links notebook `f84dc873…` via the no-quota path; card resolves against the real catalog |
| 7-M5 | Courses M5 — the authoring loop in the hub: edit objectives · reorder · regenerate · export (the epic's last line) | ✅ shipped | [PHASE7_M5_PLAN](PHASE7_M5_PLAN.md) | PR #69; `courses/writer.py` = the one transactional write path (CLI delegates; write→validate→byte-identical rollback; bundled examples 409/`editable:false`) · `PUT …/objectives` + `PUT …/order` (complete bijection, `pin_ids` oracle-tested against the loader) · `POST …/regenerate` on the chat.py lane (key scrubbed, no tools, per-type contracts, `course-regen.jsonl`) · `GET …/export` zip · edit-mode UI w/ stats-reset warning · 493 backend + 66 frontend tests |

Also closed in this arc: the **bug-hunt audit** — all 11 low-severity findings resolved
(PRs #21–#31, [`docs/bug-hunt/`](bug-hunt/)).

**Open remainder from the course epic's M2 spec** — ✅ closed 2026-07-16:
- [x] Flashcard **review UI** — ✅ shipped 2026-07-16, PR #49: a dedicated review session at
      `/courses/:slug/flashcards` (due → new → later ordering, again/hard/good grades advancing
      per-card SM-2 in the shared store under `course:<slug>` — no schema change), Review CTAs +
      due chips on Course detail, and due decks ranked into the course "what to do next".
      Addendum in [PHASE7_M2_PLAN](PHASE7_M2_PLAN.md)

---

## Arc 2 — Home Base (morning brief) — 🔄 IN FLIGHT

The current arc: evolve the hub into Kyle's daily home base — self-updating morning brief +
inline notes, learning riding along. Contract: [`KICKOFF-home-base.md`](KICKOFF-home-base.md).

- [x] **M0 — Sweep quality week** — ✅ **CLOSED 2026-07-19, verdict PASS** ([grades + audit](M0-sweep-grades.md))
  - [x] Sweep engine: per-topic prompts + `make sweep` runner (PR #34)
  - [x] Day-0 source-verified audit: AI **A−** · fantasy **A** · market **A** (PR #35)
  - [x] JSON pipeline refit: prompts emit strict JSON → validated render (with M1, PR #36)
  - [x] First full-roster 8-topic production sweep verified clean, incl. cloud-session run (2026-07-15, PR #40)
  - [x] Daily A–F grades through 07-18: Kyle's 07-15 blanket B+ · source-verified 07-16→18 audit (~30 cross-searches, zero fabrications), grades adopted by Kyle 07-19
  - [x] **Go/no-go verdict — PASS, 2026-07-19**: market outstanding · fantasy strong · AI passes **with a prompt tune** (`sweeps/prompts/ai-llms.md`: exclusion carries the same sourcing bar as inclusion, after the mishandled Gemini-delay thread). Kill criteria not met.
- [x] **M1 — The brief page** — ✅ shipped 2026-07-13, PR #36 ([plan](M1_PLAN.md); deliberate Day-0 override of the M0 gate)
      _Today route at `/` renders stored sweeps · `GET /api/brief` · visit log (habit metric) · old home → "Learning" tab_
- [x] **M2 — Full roster + notes** — ✅ shipped 2026-07-14, PRs #38 + #39 ([plan](M2_PLAN.md); second deliberate override)
      _`sweeps/topics.json` roster (8 topics, pause flags) · read-time item ids · inline notes (`brief_notes` v5, `/notes` page) · "Your learning" strip_
- [x] **M3 — Hands-off** — ✅ shipped 2026-07-15, PR #43 ([plan](M3_PLAN.md); built under the third deliberate override of the M0-verdict gate)
  - [x] Launchd scheduler + wrapper + installer; on-wake catch-up; auth spike + a bounded launchd run proven end-to-end
  - [x] Cost/usage guardrails: `--output-format json` → `data/sweeps/.runs.jsonl` ledger · API-key guard · skip-done · max-topics
  - [x] Read-time dedup: `developing`/`first_seen` labels on repeated stories (nothing dropped) + subtle Today chip
  - [x] Schedule installed 2026-07-15 at 06:00 CT; **first unattended fire verified 2026-07-16** — 8/8 topics, `rc=0` in 25½ min, fresh briefs + 8 ledger rows (~$10 equiv/day, subscription lane — not billed)
- [x] **M4 — Audio brief** — ✅ shipped 2026-07-16, PR #45 ([plan](M4_PLAN.md); picked same day from the post-M3 menu — audio-first over one combined milestone)
      _`sweeps/audio_brief.py`: deterministic ~650-word ear script → local Kokoro (`com.voicemode.kokoro`) → `data/sweeps/<date>/brief.mp3`, best-effort after every sweep (never fails it) · `GET /api/brief/audio` + `audio_available` · 🎧 player on Today · first real render 4:49 across 8 topics_
- [x] **M5 — Chat with the brief** — ✅ shipped 2026-07-16, PR #47 ([plan](M5_PLAN.md); approach A from its own explore-plan — per-item Ask, no web tools)
      _`app/chat.py` (headless `claude -p` on the subscription lane, API key scrubbed, no tools) · `POST /api/brief/chat` · "Ask about this" on every item with save-as-note reuse · `brief-chat.jsonl` ledger under backend data · live e2e: grounded answer in 13s, ~$0.07 equiv_
- [x] **M6 — Mobile** — ✅ shipped 2026-07-18, PRs #55 + #56 ([plan](M6_PLAN.md); promoted from the kickoff-deferred list, the M4/M5 path; fourth deliberate override of the M0-verdict gate — zero new prompt surface)
      _One-port serving backbone (FastAPI serves `frontend/dist`, `/api` always wins) + `com.homebase.server` KeepAlive LaunchAgent (printed pmset, never sudo) · sw.js v2 cached-last-brief offline w/ `X-Served-From-Cache` honesty (writes never queue) · bottom tab bar &lt;sm + Today/Notes phone pass (desktop untouched) · Mac-side live verify clean 2026-07-18 incl. audio Range 206 · **real-iPhone reach verified 2026-07-18 (PR #64)** — ts.net load from the phone's tailnet IP, SW registered, first phone visit logged · remaining: Kyle's eyes-on trio (home-screen standalone · airplane-mode banner · iOS audio scrub) + reboot survival_

- [x] **M7 — News mode** — ✅ shipped 2026-07-18, all four phases: PRs #58 · #60 · #62 · #63 ([plan](M7_PLAN.md); approved by Kyle from a recon-backed interview — RSS sourcing · Local = Chicago/Lake Co. · behavior-only For You signals; fifth deliberate M0-gate override, zero new LLM surface)
  - [x] Phase 1 — RSS shell: `sweeps/news_categories.json` roster · `app/news.py` (stdlib fetch/parse, sha1-link ids) · `news_feed_cache` (schema v7, 15-min TTL, stale-honesty) · `GET /api/news/*` · `/news` page w/ category tabs + text-first cards · 13 backend + 5 page tests
  - [x] Phase 2 — signals ✅ 2026-07-18: `news_events` (schema v8, snapshot columns) + `POST /api/news/events` (invalid events 400) + visit/click logging + More-like-this / Not-interested card buttons, all fire-and-forget
  - [x] Phase 3 — For You ✅ 2026-07-18: `app/foryou.py` decaying profile (click +3 · more_like +5 · not_interested −8 · visit +1, 14-day half-life) → all sections + per-term search RSS candidates → interest × freshness ranking w/ seen-exclusion, negative-drop, headline dedup · `GET /api/news/foryou` · default For You tab w/ origin chips + honest cold start
  - [x] Phase 4 — topic scout ✅ 2026-07-18: `suggest_topics` (score ≥ 9 across ≥ 3 days · event-level roster coverage · token-disjoint one-card-per-theme · theme-wide dismiss memory, schema v9) → evidence cards in For You → `POST /api/news/suggestions/add` appends atomically to `sweeps/topics.json` (409 on dupe; the one deliberate Mode-B → Mode-A write) · live e2e proof clean
  - [x] Post-ship polish ✅ 2026-07-18: **PR #65** News promoted into the mobile bottom tab bar · **PR #66** Uplifting category (good-news feeds + attribution fallback) · **PR #67** near-duplicate headline collapse on category pages (newest copy wins)

**v1 success criteria to check ~3 weeks in** (from the kickoff): ≥5 mornings/week habit (visit
log) · significant events reach Kyle here first · foraging → ~zero · ≥3 notes/week attach.
_Instrumented 2026-07-17 (PR #52): `GET /api/brief/habit` + a self-hiding "Habit check" strip on
Today count mornings + notes per local Monday-start week — the two measurable criteria read at a
glance instead of a sqlite dig._

---

## Parked / deferred (not scheduled — do not build without a decision)

- **Kickoff-deferred v1 outs**: ESPN league integration · auto-courses from news items ·
  breaking-news alerts · public writing. _(The audio brief became M4 and chat-with-the-brief
  became M5 on 2026-07-16; mobile access became M6 on 2026-07-18.)_
- **BACKLOG parked ideas** ([BACKLOG.md](../BACKLOG.md)): study-planner subagent (superseded by
  Phase 6), learner-profile doc, "Generate from hub" button, hosted phone access (M6's
  Tailscale retires the same-LAN half; the Mac-must-be-running half stays parked).

---

## Doc map (the detailed plans this page summarizes)

| Doc | What it holds |
|---|---|
| [`SPEC.md`](../SPEC.md) | Arc-1 product spec (Learning Hub) |
| [`KICKOFF-home-base.md`](KICKOFF-home-base.md) | Arc-2 contract: brief, scope, risks, milestones |
| [`PHASE1..7_PLAN.md`, `PHASE7_M2..M5_PLAN.md`](.) | Per-phase build plans (Arc 1) |
| [`COURSE_PIPELINE_SPEC.md`](COURSE_PIPELINE_SPEC.md) | Course epic vision + M1–M5 roadmap |
| [`M1_PLAN.md`](M1_PLAN.md) … [`M7_PLAN.md`](M7_PLAN.md) | Home Base milestone plans (record decided design forks — don't relitigate) |
| [`M0-sweep-grades.md`](M0-sweep-grades.md) | The grading week's durable evidence + running verdict |
| [`sweep-trust-log.md`](sweep-trust-log.md) | PR5 trust gauge: the monthly accuracy re-grade log (`last_graded` reads its newest dated heading) |
| [`bug-hunt/2026-07-19-post-m7.md`](bug-hunt/2026-07-19-post-m7.md) | Post-M7 verified bug audit — 23 findings, ranked, triage-only |
| [`ideas/`](ideas/) | Vision docs for captured brainstorm ideas (replenish 2026-07-19) |
| [`../BACKLOG.md`](../BACKLOG.md) | Parking lot for uncommitted ideas + the replenished `## Open` queue |
