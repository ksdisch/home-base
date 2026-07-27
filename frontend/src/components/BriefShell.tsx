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
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { BriefResponse } from "../api/types";
import { shortDate } from "../lib/format";
import { BriefAudioCard } from "./BriefAudioCard";

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
  /** True while the Today narration is actually playing (drives the now-playing pill). */
  isPlaying: boolean;
  /** Stop the Today narration — the single-track rule's lever for other players. */
  pauseAudio: () => void;
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
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  // The single-audio-owner rule: the shell knows when its narration is sounding, so a
  // walk off the Today route can surface a control for it and the archive player can
  // stop it before starting a second voice.
  const [isPlaying, setIsPlaying] = useState(false);
  const shellAudio = useRef<HTMLAudioElement | null>(null);
  const pauseAudio = useCallback(() => {
    shellAudio.current?.pause();
  }, []);
  // #22: a load error hides the player, but a successful network revalidate is honest
  // evidence the mp3 may be reachable again — bumping this un-hides it.
  const [netLoads, setNetLoads] = useState(0);

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
        if (!r.fromCache) setNetLoads((n) => n + 1);
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

  // F5: fetch on mount so the freshness signal (and a warm brief) is ready even when Kyle
  // opens straight to News/Notes. The inFlight guard dedupes with Brief's per-visit refresh.
  useEffect(() => {
    refresh();
  }, [refresh]);

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

  return (
    <BriefShellContext.Provider
      value={{
        brief,
        fromCache,
        error,
        loading,
        refresh,
        registerAudioSlot: setSlot,
        isPlaying,
        pauseAudio,
      }}
    >
      {children}
      {/* The narration keeps sounding off the Today route (the walk case FR15 exists for),
          but until now nothing on screen said so or could stop it. When audio is playing
          with no card mounted anywhere, this pill is the control — and the honest label
          for a voice with no visible source. Rendered outside the portal so it survives
          the host div's detachment. */}
      {isPlaying && slot === null && brief?.date && (
        <div className="fixed inset-x-0 bottom-20 z-20 flex justify-center px-4 sm:bottom-4">
          <div className="flex items-center gap-3 rounded-full border border-line bg-card/95 px-4 py-2 text-xs shadow-lg backdrop-blur">
            <span className="text-muted">
              Now playing —{" "}
              <Link to="/" className="font-medium text-accent hover:underline">
                {shortDate(brief.date)}
              </Link>
            </span>
            <button
              type="button"
              onClick={pauseAudio}
              className="rounded-full border border-line px-3 py-1 font-medium text-ink hover:border-accent hover:text-accent"
            >
              Pause
            </button>
          </div>
        </div>
      )}
      {createPortal(
        brief?.audio_available ? (
          <BriefAudioCard
            src={api.briefAudioUrl()}
            chapters={brief.audio_chapters ?? []}
            posKey={audioPosKey}
            trackKey={brief.date ?? ""}
            retryKey={netLoads}
            mediaRef={shellAudio}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
          />
        ) : null,
        hostRef.current,
      )}
    </BriefShellContext.Provider>
  );
}
