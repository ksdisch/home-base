# Smoke — M6 phone eyes-on evidence (2026-07-19)

The last open M6 evidence: four checks only Kyle's real iPhone can witness. Everything
server-side was preflighted green today before this checklist was handed over (see bottom),
so any failure below is a real phone-side finding, not a dead server.

**URL (phone + Mac, same origin):** `https://kyles-macbook-pro.tail01200d.ts.net`
**Precondition:** Tailscale iOS app connected (cellular is fine — off-home-network is the
point). The phone (`iphone182`, `100.96.118.39`) was on the tailnet at preflight time.

Do the checks in order — each sets up the next.

## 1 · Home-screen standalone

- [x] In iOS **Safari**, open the URL. Confirm Today loads with **today's brief (2026-07-19)**.
- [x] Share sheet → **Add to Home Screen**. Expect name **"Home Base"** + the teal icon. Add it.
- [x] Launch from the **home-screen icon**. **PASS =** opens full-screen app-like: **no Safari
  URL bar or toolbars**, bottom tab bar visible (Today · News · Notes · Learning · More).
- Evidence: **PASS — Kyle, 2026-07-19 ~13:3x CT.** One usability detour recorded: Add to
  Home Screen is NOT in Safari's tab-overview long-press menu or the tab-group share sheet —
  it's in the **page** share sheet, in the action list below the contact/app rows. Added,
  launched from the icon, full-screen standalone confirmed. Server log corroborates the
  icon fetches + first standalone launches from `100.96.118.39`.

## 2 · Airplane-mode "Offline copy" banner

> **Attempt 1 (2026-07-19 ~13:45 CT): FAIL — blank white page offline** (screenshots in
> session). Root-caused same hour: sw.js v2 never held usable JS/CSS bodies — the only
> SW-intercepted asset fetches were WebKit revalidations answered `304 Not Modified`
> (empty body; server log shows the phone's 304s), install pre-cached no hashed assets,
> and the index.html offline fallback answered missed assets with HTML → executed nothing.
> **Fixed in PR #71 (sw.js v3**: 200-only puts · install-time asset pre-cache parsed from
> index.html · navigation-only fallback**), merged + deployed + verified**: live Chromium
> run against the ts.net URL shows both hashed assets in `home-base-shell-v3`, and an
> offline relaunch renders Today + "Offline copy" banner (offline console errors are the
> four by-design loud API failures). **Phone re-test pending — boxes stay unticked until
> Kyle's iPhone passes.**

Stay in the standalone app you just opened — that online visit re-cached today's brief.
Post-fix note: open the app **online once more first** so the v3 service worker installs
(it pre-caches the assets at install).

- [ ] Turn on **Airplane Mode**, then check Control Center: **Wi-Fi must be off too** (iOS
  likes to keep it on). Tailscale dropping is expected — that's the test.
- [ ] **Swipe the app away** (kill it), relaunch from the home-screen icon.
- [ ] **PASS =** the shell loads (no Safari error page), **today's brief renders from cache**,
  an honest **"Offline copy — brief as of 2026-07-19"** banner shows, and **both composers
  (note + Ask) are disabled** — nothing pretends it will send later.
- [ ] Negative check: try the disabled composers — no input, no queued write, no fake success.
- [ ] Airplane Mode **off**, wait for Tailscale to reconnect (icon in Control Center), refresh
  (pull or relaunch): **banner gone, composers re-enabled**.
- Evidence: _…_

## 3 · iOS audio scrub

Back online, in the standalone app, on Today:

- [x] Tap 🎧 **play** on the audio brief (~5 min, rendered 06:25 CDT today). It plays.
- [x] **Drag the scrubber forward** (say ~3:00): **PASS =** playback jumps there and continues
  — it does **not** restart from 0:00. Scrub **backward** once too.
- [x] Tell Claude when you've scrubbed — corroboration is server-side: fresh
  `100.96.118.39 … GET /api/brief/audio … 206 Partial Content` lines in
  `backend/data/logs/launchd.log` at scrub time.
- Evidence (phone): **PASS — Kyle, 2026-07-19**: played + scrubbed in the standalone app.
- Evidence (server log): **3× `GET /api/brief/audio → 206 Partial Content` from
  `100.96.118.39`** during the pass window (grep verified this session) — iOS issued real
  Range requests and the server answered partials. Corroborated.

## 4 · Reboot survival (deferred — closes at the next Mac restart)

Config already predicts it (verified today): installed plist has `RunAtLoad` + `KeepAlive`,
and `tailscale serve --bg` persists across reboots. Kyle's observation closes it:

- [ ] Next time the Mac reboots + you log in: **before touching the Mac further**, launch
  Home Base from the phone icon. **PASS =** it loads **fresh** (no Offline-copy banner) —
  proving the LaunchAgent and tailscale serve both came back with zero terminal.
- Evidence (date + what you saw): _…_

> Want it closed today? Reboot the Mac after this session ends (it kills live Claude
> sessions), log in, phone-check, done.

Mid-pass corroborating (not a substitute): the deploy's `launchctl kickstart -k` restart
(2026-07-19) came back clean on KeepAlive — new pid, health ok — re-proving the
restart-survival half; boot-survival still needs the real reboot observation.

## Mid-pass addendum (2026-07-19, same session)

The pass earned its keep twice beyond the sw bug:
- **Stale backend caught**: the LaunchAgent process predated PR #52's merge (started
  07-18 22:34 vs merge 07-19 10:57 CT) — the phone's `GET /api/brief/habit` 404s exposed
  it. `launchctl kickstart -k` onto current main (`7c71a88`); habit now 200; a "Habit
  check" strip may newly appear on Today.
- **sw.js v3 shipped** (PR #71, see check 2) — offline shell is now a consistent
  install-time snapshot; dist rebuilt (asset hashes unchanged, so phone HTTP caches
  stayed valid); ts.net serves v3.

## TL;DR

- **Really verifying:** M6's promise on the actual device — the hub installs like an app,
  is *honestly* offline (cached brief + banner, writes fail loud, never queue), audio is
  scrubbable on iOS, and the whole thing survives a reboot with zero terminal.
- **Pass bar:** all four observed by Kyle; scrub additionally corroborated by phone-IP 206s
  in the server log. Any one failing reopens M6.
- **Most likely broken:** (a) the airplane test lying because iOS quietly kept Wi-Fi on —
  kill Wi-Fi explicitly; (b) iOS Safari being picky about Range beyond the first chunk —
  scrub *both* directions.

---

### Preflight record (Mac-side, 2026-07-19, this session)

- `com.homebase.server` LaunchAgent: **running** (pid 9269, `keepalive | runatload`).
- Tailnet: Mac `100.94.201.36`, iPhone `iphone182` `100.96.118.39` registered.
- `https://kyles-macbook-pro.tail01200d.ts.net` → `/` 200 · `/api/health` ok · manifest
  `display: standalone`, name "Home Base", 192/512 icons · `sw.js` v2
  (`home-base-shell-v2` + `home-base-brief-v1`).
- Audio `Range: bytes=0-1023` → **206**, `audio/mpeg`, 4.4 MB, rendered today 06:25 CDT;
  `/api/brief` date **2026-07-19**, 8 topics.
- `frontend/dist` was stale (Jul 18 21:51 < today's M5-UI commit) → **rebuilt** (`make
  build`, hashes `index-XAUx0jzW.js` / `index-Cj2IPCKR.css`) and confirmed served over
  ts.net.
- Server log confirmed to record the **phone's tailnet IP directly** (75 prior
  `100.96.118.39` lines incl. News usage) — Mac-originated ts.net requests log as
  `100.94.201.36`, so phone evidence is unambiguous.
