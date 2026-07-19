// Home Base service worker — v2 (M6).
// Installable shell (network-first, as v1) + the offline morning read: exactly two API
// responses — GET /api/brief and (opportunistically) GET /api/brief/audio — are cached and
// replayed ONLY when the network fails, marked X-Served-From-Cache so the page can show an
// honest "offline copy" banner and disable writes. Every other /api route is never cached.
const SHELL_CACHE = "home-base-shell-v2";
const BRIEF_CACHE = "home-base-brief-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];
const OFFLINE_API = ["/api/brief", "/api/brief/audio"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
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

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  if (url.pathname.startsWith("/api")) {
    // Only the morning read participates in offline; every other API call passes through
    // untouched (writes must fail loud when the hub is unreachable — never queue).
    if (!OFFLINE_API.includes(url.pathname)) return;
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          // Cache full 200s only — iOS audio Range requests yield 206 partials, so the
          // audio copy is opportunistic by design. Same-URL puts keep just the last good one.
          if (res.status === 200) {
            const copy = res.clone();
            caches.open(BRIEF_CACHE).then((c) => c.put(url.pathname, copy)).catch(() => {});
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

  // App shell: network-first with cache fallback (v1 behavior, rebranded cache).
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(SHELL_CACHE).then((c) => c.put(event.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(event.request).then((m) => m || caches.match("/index.html")))
  );
});
