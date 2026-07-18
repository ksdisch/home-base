# M6 Plan — Mobile (the brief in your pocket)

_Status: ✅ **shipped 2026-07-18** (PR **#55** backbone + `serve/` + PWA rename · PR **#56**
sw.js v2 offline + responsive morning loop) · **Mac-side live verify clean 2026-07-18**:
`install-server.sh` → `com.homebase.server` running headless (survives `launchctl
kickstart -k`), `/` + `/notes` + `/sw.js` 200, `/api/health` ok, unknown `/api/*` still
JSON-404s; **audio Range confirmed — `bytes=0-1023` → 206** (iOS scrub has server-side
support); Tailscale up (`kyles-macbook-pro`, kstan.disch@). **Tailnet HTTPS live-verified
2026-07-18** (Kyle enabled serve in the admin console; `tailscale serve --bg
http://127.0.0.1:8000` persists across reboots): **`https://kyles-macbook-pro.tail01200d.ts.net`**
serves `/` 200 · `/api/health` ok · `/sw.js` 200 (secure context → the phone can register
the SW) · audio `Range` → 206 over HTTPS. **Offline story e2e-verified in a real browser
2026-07-18** (Playwright, iPhone-size viewport 390×844, against the live ts.net URL): SW
registered + controlling, tab bar renders, `home-base-brief-v1` caches the brief (note:
the first-ever visit races SW control and doesn't cache — every later visit does), then
with the network emulated fully off: shell served from SW cache, cached brief rendered,
**"Offline copy" banner shown, both composers disabled**; back online: banner gone,
composers re-enabled. **Remaining proof is iPhone-hardware-only**: Tailscale app + login
(without it the ts.net name doesn't resolve — expected), Add to Home Screen (standalone
display), real iOS audio seek; reboot survival proves itself at next login — record here
M4/M5-style when done. Picked by Kyle
on 2026-07-18 from the kickoff-deferred list — "mobile access" was the last "would be
amazing" item with live pull (audio → M4, chat → M5). Planning/building ahead of the M0
verdict (~07-19) is the **fourth deliberate override** of that gate, in writing, same as
M1–M3; M6 adds **zero new prompt surface**, so it can't muddy the grading. All four forks
below were chosen by Kyle from an explicit menu (reach · UI scope · offline · Mac ops) —
he took the recommended option on each._

## The decided forks (don't relitigate)

### 1. Reach — Tailscale tailnet, not LAN-only / Cloudflare / hosting
Tailscale (free personal tier) on the Mac + iPhone; `tailscale serve` fronts the hub at a
stable `https://<mac>.<tailnet>.ts.net` URL with automatic certs. That gives: access from
anywhere the phone has signal (cellular included), nothing publicly exposed, zero backend
changes — and the **HTTPS is what unlocks a real service worker on the phone** (secure
context; plain `http://<LAN-IP>` can never register one). LAN-only was the zero-dependency
fallback; Cloudflare Tunnel adds a public-ish auth surface for no single-user gain. **Real
hosting stays parked** (BACKLOG "hosted phone access"): sweeps (subscription-lane
`claude`), Kokoro, `nlm`, and SQLite are Mac-local by design — hosting is an architecture
split, not a milestone.

### 2. One-port serving backbone — FastAPI serves the built frontend
Today the hub *only* runs as `make dev` in a terminal: `npm run build` emits `dist/` that
nothing serves, so the PWA scaffolding (manifest/icons/sw.js, PROD-only registration in
`main.tsx`) has never executed. M6 makes the backend serve `frontend/dist` when it exists —
`/assets` static mount + root PWA files + SPA catch-all to `index.html`, with `/api` always
winning — so the whole hub is one port (:8000), runnable headless. **Dev flow is untouched**
(`make dev` still runs Vite + proxy + HMR; absent `dist/`, behavior is exactly today's).
Same-origin serving also means the prod path never depends on the CORS LAN regex.

### 3. UI scope — the morning loop, first-class; learning pages stay desktop
The phone use case is the habit loop: read the brief at breakfast, jot a take, ask a
follow-up, play the audio, browse notes. The mobile-first pass covers the **app shell +
Today (`Brief.tsx`) + `/notes`** — currently there are zero responsive breakpoint classes
in any of them. Plan + flashcard review (genuinely phone-shaped SR grading) are the natural
encore; the full 11-route sweep (quiz player, course reader, Progress charts) is
desktop-posture work that would dilute the milestone.

### 4. Offline — cache the last good brief, honestly labeled; never queue writes
The real availability constraint is the **Mac, not the network**: launchd fires at 06:00
only if the Mac is awake, and an asleep Mac is unreachable on any network path. So the
service worker keeps its network-first stance but caches exactly two API responses — `GET
/api/brief` and (opportunistically) `GET /api/brief/audio` — and replays them **only when
the network fails**, marked with an `X-Served-From-Cache` header. The page then shows an
honest banner ("offline copy — brief as of <date>") and disables notes/Ask composers
(writes require the hub; they fail loud, never queue). Every other `/api` route stays
uncached, same as today. This is the house "as of" staleness honesty, extended to offline.

### 5. Navigation — bottom tab bar on phones, top nav unchanged on desktop
Below `sm`, the 6-link header (which overflows a phone width) is replaced by a fixed,
safe-area-aware bottom tab bar: **Today · Notes · Learning · More** (More pops Plan /
Courses / Progress). Thumb-reachable and app-like in standalone PWA display; ≥`sm` the
existing top nav renders exactly as today — no desktop visual changes anywhere in M6.

### 6. Mac ops — KeepAlive LaunchAgent; pmset wake stays in Kyle's hands
A login LaunchAgent (`com.homebase.server`, mirroring M3's `sweeps/schedule/` pattern:
plist template + idempotent installer + wrapper) runs the venv uvicorn on :8000 whenever
the Mac is up — no terminal. The installer **prints** the optional wake schedule
(`sudo pmset repeat wakeorpoweron MTWRFSU 05:55:00` — plugged-in Macs wake reliably for
the 06:00 sweep) but never runs sudo itself. A lid-closed Mac on battery can still sleep
through; that residual gap is exactly what fork 4's cached brief covers.

### 7. Zero new LLM surface, zero new cost
No new prompts, no model calls, no changes to `render_brief.py` or the sweep pipeline; the
read-only-over-`data/sweeps` invariant holds. Tailscale is free; M6 is the first milestone
with no token line at all. The backend↔frontend contract (`models.py` ↔ `types.ts`) is
untouched — offline-ness is frontend-only metadata.

## The slice

```
backend/app/main.py                   serve frontend/dist when present: /assets mount +
                                      root PWA files (sw.js, manifest, icons) + SPA
                                      catch-all → index.html; /api always wins; no dist →
                                      today's behavior
backend/app/config.py                 frontend_dist path setting (env FRONTEND_DIST)
serve/run-server.sh                   NEW — venv uvicorn app.main:app :8000 (no --reload)
serve/com.homebase.server.plist.template  NEW — RunAtLoad + KeepAlive login LaunchAgent
serve/install-server.sh               NEW — idempotent install/uninstall (fills template,
                                      launchctl bootstrap/enable); prints the pmset wake
                                      one-liner instead of sudo-ing
serve/README.md                       NEW — runbook: build+install · Tailscale serve ·
                                      install-to-home-screen · pmset wake · uninstall
frontend/public/manifest.webmanifest  rename to Home Base (name/short_name/description —
                                      still says "Learning Hub" from before the rename)
frontend/index.html                   <title>Home Base</title>
frontend/public/sw.js                 v2: shell cache rebranded/bumped + brief cache
                                      (fork 4); X-Served-From-Cache on offline replay
frontend/src/api/client.ts            brief fetch variant surfacing fromCache (no
                                      types.ts contract change)
frontend/src/App.tsx                  responsive shell: bottom tab bar <sm (fork 5),
                                      safe-area insets; ≥sm unchanged
frontend/src/pages/Brief.tsx          morning-loop pass: ≥44px tap targets, wrapping
                                      action rows, full-width composers, audio card,
                                      offline banner + disabled composers when cached
frontend/src/pages/Notes.tsx          cards/filters collapse on small screens
frontend/src/index.css                safe-area padding + small-screen polish
```

## Deliberately NOT in M6
- **No hosting / no public URL** — tailnet-private only; BACKLOG "hosted phone access" is
  only half-retired (same-LAN constraint gone; Mac-must-be-running remains).
- **No mobile pass on learning surfaces** (Plan / flashcards / quiz player / courses /
  Progress) — usable-not-optimized; tier-2 encore.
- **No offline write queue** — notes/Ask offline fail loud with the banner, never sync later.
- **No push notifications** (breaking-news alerts stay kickoff-deferred) · **no native
  wrapper** · **no desktop visual changes** · **no new LLM surface**.

## Verification
- Backend pytest (house style, tmp dist fixture): `/` serves `index.html` when dist exists ·
  `/assets/*` served · unknown SPA path → `index.html` · `/api/*` unaffected and wins over
  the catch-all · absent dist → today's 404s and a healthy API.
- Frontend vitest: offline banner renders (and composers disable) on `fromCache` · tab bar /
  top nav both render their links.
- `make lint` · `make typecheck` · both suites green · `bash -n` on the new shell scripts ·
  contract-reviewer no-op (no `models.py`/`types.ts` drift by design).
- **Live e2e on the Mac + iPhone:** build → `install-server.sh` → server up with no terminal
  (`launchctl kickstart` + reboot survival) → `tailscale serve` → phone loads the ts.net URL
  on cellular → install to home screen, standalone display, SW registered → airplane mode
  shows the cached brief with the banner → audio plays; **check seek/scrub on iOS Safari**
  (Range support depends on the resolved Starlette behind `fastapi>=0.110`; if scrubbing
  fails, serve the MP3 range-aware) → next real morning: pmset wake fires, sweep ledger row
  + phone visit logged before the Mac is touched.
