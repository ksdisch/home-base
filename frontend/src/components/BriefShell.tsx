import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import type { BriefResponse } from "../api/types";

// FR15: the core loop bounces Today↔News↔Notes mid-walk, but React Router remounts the
// Today route on every return — skeleton flash, refetch, and the audio brief snapping
// back to 0:00. This shell sits above <Routes> and owns what must outlive a route hop:
// the brief payload and the single <audio> element. The audio card renders through a
// portal whose target div never changes identity, so React never remounts the element;
// Brief just tells the shell where that host div currently belongs in the DOM. Off the
// Today route the host sits detached — invisible, still playing (the walk case).

type BriefShellState = {
  brief: BriefResponse | null;
  fromCache: boolean;
  error: string | null;
  loading: boolean;
  /** Fetch on first call; silently revalidate in the background after that. */
  refresh: () => void;
  /** Brief hands the shell the div the audio card should live in (null on unmount). */
  registerAudioSlot: (el: HTMLElement | null) => void;
};

const BriefShellContext = createContext<BriefShellState | null>(null);

export function useBriefShell(): BriefShellState {
  const ctx = useContext(BriefShellContext);
  if (!ctx) throw new Error("useBriefShell must be used inside <BriefShell>");
  return ctx;
}

export function BriefShell({ children }: { children: ReactNode }) {
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Bug #15 (hoisted with the player): audio_available reflects the served (possibly
  // cached) payload, but the mp3 itself can be unreachable — offline with an uncached
  // copy (iOS Range → 206 → never stored) or evicted by the SW's date pairing. No
  // player beats a broken one.
  const [audioBroken, setAudioBroken] = useState(false);
  const [slot, setSlot] = useState<HTMLElement | null>(null);

  // Stable portal target — created once, moved between Brief's slot and detachment.
  const hostRef = useRef<HTMLDivElement | null>(null);
  if (hostRef.current === null) hostRef.current = document.createElement("div");

  const briefRef = useRef<BriefResponse | null>(null);
  const inFlight = useRef(false);
  const refresh = useCallback(() => {
    if (inFlight.current) return;
    inFlight.current = true;
    api
      .briefWithMeta()
      .then((r) => {
        briefRef.current = r.brief;
        setBrief(r.brief);
        setFromCache(r.fromCache);
        setError(null);
      })
      .catch((e) => {
        // A failed revalidate with a payload in hand keeps serving it silently — a
        // Today→Notes→Today hop must never banner over a morning that already loaded.
        if (briefRef.current === null) setError(e.message ?? "Failed to load the brief");
      })
      .finally(() => {
        inFlight.current = false;
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const host = hostRef.current!;
    if (slot) {
      slot.appendChild(host);
      return () => {
        host.remove();
      };
    }
  }, [slot]);

  // QU3 (hoisted with the player): date-keyed resume, cleared on ended.
  const audioPosKey = brief?.date ? `audio-pos-${brief.date}` : null;

  // FR4: chapter chips seek the single track. Offsets are word-count estimates, so land
  // 2s early — the spoken "Next up:" lead confirms the jump instead of a mid-sentence
  // surprise. `?? []` tolerates a stale pre-FR4 payload from the service-worker cache.
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const chapters = brief?.audio_chapters ?? [];
  const seekChapter = (start: number) => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = Math.max(0, start - 2);
    el.play()?.catch(() => {});
  };

  return (
    <BriefShellContext.Provider
      value={{ brief, fromCache, error, loading, refresh, registerAudioSlot: setSlot }}
    >
      {children}
      {createPortal(
        brief?.audio_available && !audioBroken ? (
          <div className="mb-6 rounded-2xl border border-stone-200 bg-white/60 p-4">
            <p className="mb-2 text-xs font-medium text-muted">
              🎧 Listen to this brief — the ~5-minute cut
            </p>
            <audio
              ref={audioRef}
              controls
              preload="none"
              src={api.briefAudioUrl()}
              className="w-full"
              onError={() => setAudioBroken(true)}
              onTimeUpdate={(e) => {
                if (audioPosKey) localStorage.setItem(audioPosKey, String(e.currentTarget.currentTime));
              }}
              onLoadedMetadata={(e) => {
                if (!audioPosKey) return;
                const saved = Number(localStorage.getItem(audioPosKey));
                if (saved > 0) e.currentTarget.currentTime = saved;
              }}
              onEnded={() => {
                if (audioPosKey) localStorage.removeItem(audioPosKey);
              }}
            />
            {chapters.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {chapters.map((ch) => (
                  <button
                    key={ch.slug}
                    type="button"
                    onClick={() => seekChapter(ch.start_seconds)}
                    className="rounded-full border border-stone-200 bg-white/70 px-3 py-1 text-xs font-medium text-ink hover:border-accent hover:text-accent"
                  >
                    {ch.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : null,
        hostRef.current,
      )}
    </BriefShellContext.Provider>
  );
}
