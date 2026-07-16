# M4 Plan — The audio brief (listen to the morning sweep)

_Status: ✅ shipped 2026-07-16 (PR #45) · verified end-to-end the same day — 330 backend
tests green and a real Kokoro render of the live 2026-07-16 brief (651 words → 4:49 MP3,
8 topics). Picked 2026-07-16 from the post-M3 menu (the
kickoff's phased plan ended at M3, so the next build was an open decision): Kyle chose **both**
the audio brief and chat-with-the-brief, then approach **A** from the `/explore-plan` fork —
**audio first as M4**, chat queued as **M5** with its own explore-plan. "Audio version of the
brief" was the #1 item on the kickoff's "would be amazing" list._

## The decided forks (don't relitigate)

### 1. Deterministic ear script — not an LLM "radio host" pass
`sweeps/audio_brief.py` assembles the spoken script mechanically from the day's validated
`<topic>.json` files (per topic: a spoken title + the `top_line` + the top item's headline
and first digest sentence), targeting **~600–700 words ≈ 4–5 minutes** — under local Kokoro's
~750-word single-request comfort zone, so one render, no ffmpeg/concat. Rationale: zero new
LLM cost, zero latency added to the pipeline, and **zero new un-graded prompt surface** while
the M0 grading week is still validating the existing prompts. The premium "radio host" script
(one extra `claude -p` pass, ~+$1 equiv/day) was considered (approach C) and noted as a clean
later upgrade behind an env flag — not v1.

### 2. Generation lives in the sweep pipeline — the backend stays read-only
The MP3 is written by the **pipeline** (`sweep.sh` → `audio_brief.py` →
`data/sweeps/<date>/brief.mp3`, gitignored + regenerable like everything else there). The
backend only **serves** it (`GET /api/brief/audio`, a `FileResponse`) — the strictly
read-only-over-`data/sweeps` invariant holds. On-demand backend generation would have broken
that invariant and added TTS latency to a page load.

### 3. Best-effort by design — audio can never fail the sweep
Kokoro runs as its own login LaunchAgent (`com.voicemode.kokoro`, port 8880 — verified live).
If it's down or the render errors, `sweep.sh` logs one loud line and the sweep still exits 0:
the text brief is the product, the MP3 is a bonus. Idempotency matches the M3 wrapper's
spirit: the script skips itself when `brief.mp3` is already **newer than every
`<topic>.json`** (mtime check), so an on-wake re-fire is a no-op but a late-finishing topic
triggers a regenerate.

### 4. One condensed MP3 — not per-topic files, not the full read
A single "morning drive" cut beats eight files for the listen-on-a-walk use case, and the
full 8-topic read (~3–4K words ≈ 20+ min) both overshoots the habit and strains a single
Kokoro request. The page remains the full-depth surface; the audio is the compressed pass.

## The slice

```
sweeps/audio_brief.py                 NEW — stdlib-only. Reads the day's <topic>.json in
                                      roster order, builds the ear script (speakable titles,
                                      markdown stripped, ~700-word budget with a deterministic
                                      trim ladder), POSTs to Kokoro /v1/audio/speech, writes
                                      data/sweeps/<date>/brief.mp3 atomically. Modes:
                                      --print-script (no render) · --force · env KOKORO_URL /
                                      NARRATE_VOICE / NARRATE_SPEED
sweep.sh                              one best-effort call after the topic loop (guarded `if`,
                                      never increments failures)
backend/app/api/brief.py              GET /brief/audio → FileResponse of the served day's mp3
                                      (404 when absent); get_brief() sets audio_available
backend/app/models.py                 BriefResponse += audio_available: bool = False
frontend/src/api/types.ts             hand-sync audio_available
frontend/src/api/client.ts            api.briefAudioUrl() — the one place the URL lives
frontend/src/pages/Brief.tsx          🎧 player card under the Today header when available
sweeps/README.md                      "The audio brief" section (env knobs, degrade behavior)
```

## Deliberately NOT in M4
- **No LLM script pass** — the C-approach upgrade waits until the deterministic cut proves
  too dry *and* M0's verdict lands.
- **No per-topic MP3s / playlist UI** — one condensed file is the v1 bet.
- **No new service management** — Kokoro's own LaunchAgent owns uptime; the pipeline just
  degrades gracefully when it's absent (also true on any machine without Kokoro).
- **No changes to `render_brief.py`** — the trust-critical write path stays frozen.
- **No autoplay** — `preload="none"`, Kyle presses play.

## Verification
- Backend pytest (house style, synthetic day dirs): `audio_available` flag on/off ·
  `/api/brief/audio` 200-with-audio/mpeg vs 404 (missing file, no sweeps, and mp3-only-in-an-
  older-day must still 404 — never serve stale audio for the wrong day) · script-builder via
  `--print-script` (roster order, speakable titles, markdown/URLs stripped, word budget,
  unparseable topic skipped) · degrade path (unreachable Kokoro → exit 1, no file; fresh mp3
  → skip without contacting Kokoro at all).
- `bash -n sweep.sh` · `make lint` · `make typecheck` · frontend vitest.
- Real end-to-end on today's live data: `--print-script` eyeball, then one real Kokoro render
  of 2026-07-16 → verify bytes/duration (`afinfo`) and send Kyle the MP3 to hear.
