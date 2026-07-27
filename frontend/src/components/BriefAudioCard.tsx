import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import type { BriefAudioChapter } from "../api/types";

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
          // #5: never persist a position read off the previous track under the new key.
          if (!posKey || loadedTrack.current !== trackKey) return;
          localStorage.setItem(posKey, String(e.currentTarget.currentTime));
        }}
        onLoadedMetadata={(e) => {
          loadedTrack.current = trackKey;
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
