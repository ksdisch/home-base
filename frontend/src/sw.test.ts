// Bug #15 (docs/bug-hunt/2026-07-19-post-m7.md): brief JSON and audio aged independently
// in BRIEF_CACHE with no date pairing — offline Saturday could play Tuesday's narration
// under Friday's brief. The SW records which brief date the cached audio belongs to and
// evicts the audio when it caches a brief for a different date.
//
// The real public/sw.js runs inside a tiny harness: `self`, `caches`, and `fetch` are
// injected, fetch events are driven by hand, and the floating cache-write promises are
// flushed — no service-worker runtime, no network.
import { describe, expect, it } from "vitest";

// The real service worker, loaded as text through vite's ?raw pipeline.
import SW_SRC from "../public/sw.js?raw";

type Listener = (event: unknown) => void;

function makeCaches() {
  const stores = new Map<string, Map<string, Response>>();
  const norm = (key: unknown) => {
    const url = typeof key === "string" ? key : (key as Request).url;
    return url.startsWith("http") ? new URL(url).pathname : url;
  };
  const openStore = (name: string) => {
    if (!stores.has(name)) stores.set(name, new Map());
    const m = stores.get(name)!;
    return {
      match: async (key: unknown) => m.get(norm(key)),
      put: async (key: unknown, res: Response) => void m.set(norm(key), res),
      delete: async (key: unknown) => m.delete(norm(key)),
      addAll: async () => {},
    };
  };
  const caches = {
    open: async (name: string) => openStore(name),
    match: async (key: unknown) => {
      for (const m of stores.values()) {
        const r = m.get(norm(key));
        if (r) return r;
      }
      return undefined;
    },
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
  };
  return { stores, caches };
}

function loadSw(fetchImpl: (req: Request) => Promise<Response>) {
  const listeners: Record<string, Listener> = {};
  const swSelf = {
    addEventListener: (type: string, fn: Listener) => {
      listeners[type] = fn;
    },
    skipWaiting: () => {},
    clients: { claim: () => {} },
  };
  const { stores, caches } = makeCaches();
  new Function("self", "caches", "fetch", "Response", "Headers", "URL", "Request", SW_SRC)(
    swSelf,
    caches,
    fetchImpl,
    Response,
    Headers,
    URL,
    Request,
  );
  return { listeners, stores };
}

async function driveFetch(listeners: Record<string, Listener>, request: Request) {
  let result: Promise<Response> | undefined;
  listeners.fetch({
    request,
    respondWith: (p: Promise<Response>) => {
      result = p;
    },
  });
  const res = result ? await result : undefined;
  // The SW's cache writes are deliberately floating promises — let them settle.
  for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0));
  return res;
}

const briefRes = (date: string) =>
  new Response(JSON.stringify({ date, has_data: true, topics: [] }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
const audioRes = () =>
  new Response(new Uint8Array([1, 2, 3]), {
    status: 200,
    headers: { "Content-Type": "audio/mpeg" },
  });

const BRIEF_REQ = () => new Request("http://hub.local/api/brief");
const AUDIO_REQ = () => new Request("http://hub.local/api/brief/audio");
const BRIEF_CACHE = "home-base-brief-v1";

describe("sw brief/audio date pairing (#15)", () => {
  it("caching a brief for a new date evicts the old day's cached audio", async () => {
    const responses: Record<string, () => Response> = {
      "/api/brief": () => briefRes("2026-07-18"),
      "/api/brief/audio": audioRes,
    };
    const { listeners, stores } = loadSw(async (req) =>
      responses[new URL(req.url).pathname](),
    );

    await driveFetch(listeners, BRIEF_REQ());
    await driveFetch(listeners, AUDIO_REQ());
    expect(stores.get(BRIEF_CACHE)?.has("/api/brief/audio")).toBe(true);

    responses["/api/brief"] = () => briefRes("2026-07-19"); // a new morning arrives
    await driveFetch(listeners, BRIEF_REQ());

    // Friday's brief must not replay Tuesday's narration: the mismatched audio is gone,
    // the fresh brief is cached.
    expect(stores.get(BRIEF_CACHE)?.has("/api/brief/audio")).toBe(false);
    expect(stores.get(BRIEF_CACHE)?.has("/api/brief")).toBe(true);
  });

  it("re-caching the same day's brief keeps its audio", async () => {
    const responses: Record<string, () => Response> = {
      "/api/brief": () => briefRes("2026-07-18"),
      "/api/brief/audio": audioRes,
    };
    const { listeners, stores } = loadSw(async (req) =>
      responses[new URL(req.url).pathname](),
    );

    await driveFetch(listeners, BRIEF_REQ());
    await driveFetch(listeners, AUDIO_REQ());
    await driveFetch(listeners, BRIEF_REQ()); // an on-wake reload, same morning

    expect(stores.get(BRIEF_CACHE)?.has("/api/brief/audio")).toBe(true);
  });

  it("offline replay of the cached brief still works after the pairing write", async () => {
    const responses: Record<string, () => Response> = {
      "/api/brief": () => briefRes("2026-07-18"),
      "/api/brief/audio": audioRes,
    };
    let online = true;
    const { listeners } = loadSw(async (req) => {
      if (!online) throw new TypeError("offline");
      return responses[new URL(req.url).pathname]();
    });

    await driveFetch(listeners, BRIEF_REQ());
    online = false;
    const replay = await driveFetch(listeners, BRIEF_REQ());

    expect(replay?.headers.get("X-Served-From-Cache")).toBe("1");
    expect(((await replay?.json()) as { date: string }).date).toBe("2026-07-18");
  });

  it("an archived-day request (?date=) never touches the offline morning cache (QU1)", async () => {
    // The archive is live-only: the SW must stand aside for /api/brief?date=… — caching
    // it under the same pathname key would clobber the offline last-morning AND move the
    // date marker, evicting today's paired audio.
    const responses: Record<string, () => Response> = {
      "/api/brief": () => briefRes("2026-07-18"),
      "/api/brief/audio": audioRes,
    };
    const { listeners, stores } = loadSw(async (req) => {
      const u = new URL(req.url);
      if (u.pathname === "/api/brief" && u.search) return briefRes("2026-07-13");
      return responses[u.pathname]();
    });

    await driveFetch(listeners, BRIEF_REQ());
    await driveFetch(listeners, AUDIO_REQ()); // today's brief + audio pair cached

    const archived = await driveFetch(
      listeners,
      new Request("http://hub.local/api/brief?date=2026-07-13"),
    );
    expect(archived).toBeUndefined(); // the SW never intercepted it

    const cachedBrief = stores.get(BRIEF_CACHE)?.get("/api/brief");
    expect(((await cachedBrief?.clone().json()) as { date: string }).date).toBe("2026-07-18");
    expect(stores.get(BRIEF_CACHE)?.has("/api/brief/audio")).toBe(true);
  });
});
