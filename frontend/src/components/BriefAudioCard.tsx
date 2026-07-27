import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import type { BriefAudioChapter } from "../api/types";
import { shortDate } from "../lib/format";

// Lock-screen controls + speed (docs/ideas/lock-screen-audio-controls.md). The walk-listen
// is this player's real use and it degraded the instant the phone locked: an anonymous
// file, no seek, no chapter skip, stuck at 1x. Living on the ONE shared card means the
// archive player gets the same wiring for free — the point of bug #20's extract.
const RATES = [1, 1.25, 1.5];
const RATE_KEY = "audio-rate";

function storedRate(): number {
  const raw = Number(localStorage.getItem(RATE_KEY));
  return RATES.includes(raw) ? raw : 1;
}

// The one narrated-brief player. BriefShell's hoisted Today card and BriefArchive's
// historical card were separate copies until they drifted (bug #20: the archive lost the
// −2s chapter lead, the play() on tap, and the onError degrade). One component, one set
// of behaviours, so a fix to either surface is a fix to both.
//
// Every handler here defends one specific failure the two copies hit:
//   #21 pendingSeek — a chapter tap before metadata must survive the saved-resume restore
//   #22 retryKey    — a transient load error must not hide the player for the session
//   #5  trackKey    — the shell's src is a constant dateless URL, so a date flip needs an
//                     explicit load() or the element keeps yesterday's narration
export function BriefAudioCard({
  src,
  chapters,
  posKey,
  trackKey,
  retryKey,
  mediaRef,
  onPlay,
  onPause,
}: {
  src: string;
  chapters: BriefAudioChapter[];
  /** localStorage key for the date-scoped resume point; null disables resume. */
  posKey: string | null;
  /** The date `src` resolves to — a change means a different track in the same element. */
  trackKey: string;
  /** Bump to clear a previous load error (a successful network revalidate). */
  retryKey?: number;
  /** Lets an owner (the shell) pause this element without owning the markup. */
  mediaRef?: MutableRefObject<HTMLAudioElement | null>;
  onPlay?: () => void;
  onPause?: () => void;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [rate, setRate] = useState<number>(storedRate);
  // #21: set by a chapter tap, cleared by the metadata handler it must outrank.
  const pendingSeek = useRef(false);
  // #5: which track the element has actually loaded — null until metadata lands.
  const loadedTrack = useRef<string | null>(null);
  // Bug #15: audio_available reflects the served (possibly cached) payload, but the mp3
  // itself can be unreachable — offline with an uncached copy, or evicted by the SW's
  // date pairing. No player beats a broken one.
  const [broken, setBroken] = useState(false);

  // Stable identity on purpose: an inline callback ref is detached and re-attached on
  // every render, which would churn the element handle the trackKey effect depends on.
  const setRef = useCallback(
    (el: HTMLAudioElement | null) => {
      audioRef.current = el;
      if (mediaRef) mediaRef.current = el;
    },
    [mediaRef],
  );

  // #5: a date flip under a persistent element. The src string changes, but the media
  // element keeps the already-loaded resource until told otherwise, so yesterday's
  // narration would play under today's brief with today's chapter offsets seeking into it.
  useEffect(() => {
    setBroken(false);
    const el = audioRef.current;
    if (!el) return;
    if (loadedTrack.current !== null && loadedTrack.current !== trackKey) {
      el.pause();
      el.load();
      loadedTrack.current = null;
    }
  }, [trackKey]);

  // #22: a successful network revalidate is honest evidence the mp3 may be reachable
  // again — re-show the player and let the next play attempt re-verify via onError. Kept
  // separate from the trackKey effect on purpose: folding the revalidate counter into
  // trackKey would load() mid-playback on every 30s background poll.
  useEffect(() => {
    setBroken(false);
  }, [retryKey]);

  // Losing the element is not an event it can report: unmounting an <audio> mid-playback
  // fires no `pause`. Without this the owner would still believe a narration is sounding
  // — a "Now playing" pill over silence, with a Pause button wired to nothing.
  const onPauseRef = useRef(onPause);
  onPauseRef.current = onPause;
  useEffect(() => () => onPauseRef.current?.(), []);

  // Chapters in play order. audio_brief.py writes them in narration order already, but the
  // skip handlers below do arithmetic on the offsets, so sort rather than assume.
  const ordered = [...chapters].sort((a, b) => a.start_seconds - b.start_seconds);
  const orderedKey = ordered.map((c) => `${c.slug}:${c.start_seconds}`).join("|");

  // The lock screen. Registered on the shared card, so Today and the archive both get it.
  useEffect(() => {
    const ms = navigator.mediaSession;
    if (!ms) return; // iOS < 15 and any non-supporting browser — the card still works
    ms.metadata = new MediaMetadata({
      title: `Morning brief — ${shortDate(trackKey) || trackKey}`,
      artist: ordered[0]?.title ?? "Home Base",
      album: "Home Base",
    });

    const el = () => audioRef.current;
    // The same −2s lead the chips use: land on the spoken "Next up:" rather than
    // mid-sentence. Shared so the two entry points can never drift apart.
    const jump = (start: number) => {
      const a = el();
      if (!a) return;
      pendingSeek.current = true;
      a.currentTime = Math.max(0, start - 2);
    };

    const set = (action: string, handler: (() => void) | ((d: { seekTime?: number }) => void) | null) => {
      try {
        ms.setActionHandler(action as MediaSessionAction, handler as never);
      } catch {
        /* an action this browser doesn't know: skip it, keep the rest */
      }
    };

    set("play", () => el()?.play()?.catch(() => {}));
    set("pause", () => el()?.pause());
    set("seekto", (d: { seekTime?: number } = {}) => {
      const a = el();
      if (a && typeof d.seekTime === "number") a.currentTime = d.seekTime;
    });

    // Idea-doc question 1: the two scarce skip slots go to CHAPTERS, not a blind ±15s.
    // The brief has real chapters with offsets and nothing else surfaces them, while ±15s
    // is already reachable through the scrubber `seekto` registers above.
    if (ordered.length > 0) {
      set("nexttrack", () => {
        const a = el();
        if (!a) return;
        const next = ordered.find((c) => c.start_seconds > a.currentTime + 2);
        if (next) jump(next.start_seconds);
      });
      set("previoustrack", () => {
        const a = el();
        if (!a) return;
        const prior = [...ordered].reverse().find((c) => c.start_seconds < a.currentTime - 2);
        jump(prior ? prior.start_seconds : 0);
      });
    }

    return () => {
      for (const a of ["play", "pause", "seekto", "nexttrack", "previoustrack"]) set(a, null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- orderedKey stands in for `ordered`
  }, [trackKey, orderedKey]);

  if (broken) return null;

  // FR4: chapter chips seek the single track. Offsets are word-count estimates, so land
  // 2s early — the spoken "Next up:" lead confirms the jump instead of a mid-sentence
  // surprise. With preload="none" the play() is what makes a first tap audible at all.
  const seekChapter = (start: number) => {
    const el = audioRef.current;
    if (!el) return;
    pendingSeek.current = true;
    el.currentTime = Math.max(0, start - 2);
    el.play()?.catch(() => {});
  };

  const applyRate = (next: number) => {
    setRate(next);
    try {
      localStorage.setItem(RATE_KEY, String(next));
    } catch {
      /* localStorage unavailable — the rate simply doesn't persist */
    }
    if (audioRef.current) audioRef.current.playbackRate = next;
  };

  return (
    <div className="mb-6 rounded-2xl border border-line bg-card/60 p-4">
      <p className="mb-2 text-xs font-medium text-muted">
        🎧 Listen to this brief — the ~5-minute cut
      </p>
      <audio
        ref={setRef}
        controls
        preload="none"
        src={src}
        className="w-full"
        onError={() => {
          setBroken(true);
          // Same reason as the unmount cleanup: the element is about to disappear, and a
          // mid-playback failure never reports the stop it caused.
          onPause?.();
        }}
        onPlay={onPlay}
        onPause={onPause}
        onTimeUpdate={(e) => {
          // Keep the lock screen's chapter label current — "which topic is this?" is the
          // one thing a locked phone can't otherwise answer.
          const ms = navigator.mediaSession;
          if (ms?.metadata && ordered.length > 0) {
            const now = e.currentTarget.currentTime;
            const current = [...ordered].reverse().find((c) => c.start_seconds <= now + 2);
            if (current && ms.metadata.artist !== current.title) ms.metadata.artist = current.title;
          }
          // #5: never persist a position read off the previous track under the new key.
          if (!posKey || loadedTrack.current !== trackKey) return;
          localStorage.setItem(posKey, String(e.currentTarget.currentTime));
        }}
        onLoadedMetadata={(e) => {
          loadedTrack.current = trackKey;
          // A load() resets playbackRate to 1, so the chosen speed is re-applied here
          // rather than only at tap time.
          e.currentTarget.playbackRate = rate;
          // #21: a chapter tap already chose a position — with preload="none" that tap is
          // what triggered this load, so restoring the saved point here would silently
          // discard the jump the tap just made.
          if (pendingSeek.current) {
            pendingSeek.current = false;
            return;
          }
          if (!posKey) return;
          const saved = Number(localStorage.getItem(posKey));
          if (saved > 0) e.currentTarget.currentTime = saved;
        }}
        onEnded={() => {
          if (posKey) localStorage.removeItem(posKey);
          // A natural end fires `ended`, not `pause` — without this the owner would
          // still believe the narration is sounding (a now-playing pill that never
          // clears once the brief finishes).
          onPause?.();
        }}
      />
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs text-muted">Speed</span>
        {RATES.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => applyRate(r)}
            aria-pressed={rate === r}
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
              rate === r
                ? "border-accent text-accent"
                : "border-line text-muted hover:border-accent hover:text-accent"
            }`}
          >
            {r}x
          </button>
        ))}
      </div>
      {chapters.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {chapters.map((ch) => (
            <button
              key={ch.slug}
              type="button"
              onClick={() => seekChapter(ch.start_seconds)}
              className="rounded-full border border-line bg-card/70 px-3 py-1 text-xs font-medium text-ink hover:border-accent hover:text-accent"
            >
              {ch.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
