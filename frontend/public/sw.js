// Home Base service worker — v3 (M6, + real-iPhone offline fix).
// Installable shell (network-first, as v1) + the offline morning read: exactly two API
// responses — GET /api/brief and (opportunistically) GET /api/brief/audio — are cached and
// replayed ONLY when the network fails, marked X-Served-From-Cache so the page can show an
// honest "offline copy" banner and disable writes. Every other /api route is never cached.
//
// v3, after the 2026-07-19 phone pass found offline blank-paging: the shell cache may only
// ever hold full 200 bodies — WebKit revalidates cached assets and a 304 has an EMPTY body,
// so blindly caching "whatever fetch returned" stored husks. The hashed /assets bundle is
// now pre-cached at install (parsed out of index.html — runtime caching alone never sees a
// 200 for an asset the HTTP cache is revalidating), and the index.html offline fallback is
// navigation-only — answering a missed asset with HTML renders a silent blank page.
const SHELL_CACHE = "home-base-shell-v3";
const BRIEF_CACHE = "home-base-brief-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];
const OFFLINE_API = ["/api/brief", "/api/brief/audio"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const c = await caches.open(SHELL_CACHE);
      await c.addAll(SHELL).catch(() => {});
      // Pre-cache the exact hashed assets this index.html references, so the offline shell
      // is a consistent snapshot from day one instead of depending on runtime cache luck.
      // Best-effort like the shell addAll: a failed pre-cache must never block install.
      try {
        const idx = await c.match("/index.html");
        const html = idx ? await idx.text() : "";
        const assets = [...new Set(html.match(/\/assets\/[^"']+/g) || [])];
        if (assets.length) await c.addAll(assets);
      } catch {
        // Online behavior is unaffected either way.
      }
    })()
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => k !== SHELL_CACHE && k !== BRIEF_CACHE).map((k) => caches.delete(k))
        )
      )
  );
  self.clients.claim();
});

// Rebuild a cached response with the offline marker (cached headers are immutable).
async function markedFromCache(cached) {
  const headers = new Headers(cached.headers);
  headers.set("X-Served-From-Cache", "1");
  return new Response(await cached.blob(), {
    status: cached.status,
    statusText: cached.statusText,
    headers,
  });
}

// Bug #15: brief JSON and audio aged independently — offline Saturday could play
// Tuesday's narration under Friday's brief. A synthetic cache entry records which brief
// date the cached pair belongs to; caching a brief for a DIFFERENT date evicts the audio
// (it re-caches opportunistically the next time the player streams online).
const BRIEF_DATE_KEY = "/__cached-brief-date";
async function cacheBriefWithDatePairing(res) {
  try {
    const c = await caches.open(BRIEF_CACHE);
    const newDate = String((await res.clone().json()).date ?? "");
    const marker = await c.match(BRIEF_DATE_KEY);
    const oldDate = marker ? await marker.text() : "";
    if (oldDate && newDate && oldDate !== newDate) await c.delete("/api/brief/audio");
    await c.put(BRIEF_DATE_KEY, new Response(newDate));
    await c.put("/api/brief", res);
  } catch {
    // Best-effort like every other cache write — online behavior is unaffected.
  }
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  if (url.pathname.startsWith("/api")) {
    // Only the morning read participates in offline; every other API call passes through
    // untouched (writes must fail loud when the hub is unreachable — never queue).
    if (!OFFLINE_API.includes(url.pathname)) return;
    // QU1: archived-day views (?date=) are live-only — never cached, never replayed.
    // Caching one under the shared pathname key would clobber the offline last-morning
    // and move the date marker, evicting today's paired audio.
    if (url.search) return;
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          // Cache full 200s only — iOS audio Range requests yield 206 partials, so the
          // audio copy is opportunistic by design. Same-URL puts keep just the last good
          // one; the brief's put also maintains the date pairing (bug #15).
          if (res.status === 200) {
            const copy = res.clone();
            if (url.pathname === "/api/brief") {
              cacheBriefWithDatePairing(copy);
            } else {
              caches.open(BRIEF_CACHE).then((c) => c.put(url.pathname, copy)).catch(() => {});
            }
          }
          return res;
        })
        .catch(async () => {
          const cached = await caches.open(BRIEF_CACHE).then((c) => c.match(url.pathname));
          // A cached full audio answers even a Range request (200 → playback without seek).
          return cached ? markedFromCache(cached) : Response.error();
        })
    );
    return;
  }

  // App shell: network-first with cache fallback. Store full 200s only — a 304
  // revalidation has no body, and caching one poisons the offline copy.
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.status === 200) {
          const copy = res.clone();
          caches.open(SHELL_CACHE).then((c) => c.put(event.request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(event.request).then((m) => {
          if (m) return m;
          // SPA offline entry is for navigations only — serving HTML for a missed asset
          // would execute nothing and blank the page instead of failing visibly.
          if (event.request.mode === "navigate") return caches.match("/index.html");
          return Response.error();
        })
      )
  );
});
