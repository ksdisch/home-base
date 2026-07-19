# Smoke — M6 phone eyes-on evidence (2026-07-19)

The last open M6 evidence: four checks only Kyle's real iPhone can witness. Everything
server-side was preflighted green today before this checklist was handed over (see bottom),
so any failure below is a real phone-side finding, not a dead server.

**URL (phone + Mac, same origin):** `https://kyles-macbook-pro.tail01200d.ts.net`
**Precondition:** Tailscale iOS app connected (cellular is fine — off-home-network is the
point). The phone (`iphone182`, `100.96.118.39`) was on the tailnet at preflight time.

Do the checks in order — each sets up the next.

## 1 · Home-screen standalone

- [ ] In iOS **Safari**, open the URL. Confirm Today loads with **today's brief (2026-07-19)**.
- [ ] Share sheet → **Add to Home Screen**. Expect name **"Home Base"** + the teal icon. Add it.
- [ ] Launch from the **home-screen icon**. **PASS =** opens full-screen app-like: **no Safari
  URL bar or toolbars**, bottom tab bar visible (Today · News · Notes · Learning · More).
- Evidence (what you saw): _…_

## 2 · Airplane-mode "Offline copy" banner

Stay in the standalone app you just opened — that online visit re-cached today's brief.

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

- [ ] Tap 🎧 **play** on the audio brief (~5 min, rendered 06:25 CDT today). It plays.
- [ ] **Drag the scrubber forward** (say ~3:00): **PASS =** playback jumps there and continues
  — it does **not** restart from 0:00. Scrub **backward** once too.
- [ ] Tell Claude when you've scrubbed — corroboration is server-side: fresh
  `100.96.118.39 … GET /api/brief/audio … 206 Partial Content` lines in
  `backend/data/logs/launchd.log` at scrub time.
- Evidence (phone): _…_
- Evidence (server log): _…_

## 4 · Reboot survival (deferred — closes at the next Mac restart)

Config already predicts it (verified today): installed plist has `RunAtLoad` + `KeepAlive`,
and `tailscale serve --bg` persists across reboots. Kyle's observation closes it:

- [ ] Next time the Mac reboots + you log in: **before touching the Mac further**, launch
  Home Base from the phone icon. **PASS =** it loads **fresh** (no Offline-copy banner) —
  proving the LaunchAgent and tailscale serve both came back with zero terminal.
- Evidence (date + what you saw): _…_

> Want it closed today? Reboot the Mac after this session ends (it kills live Claude
> sessions), log in, phone-check, done.

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
