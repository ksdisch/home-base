# Lock-screen controls + speed chips for the audio brief (Media Session + rate)

**Status:** Idea — not committed. Added by `/replenish` (QuickWin lane) on 2026-07-26.

_QuickWin lane; the Friction lane independently converged on the Media Session half (3 independent blind hits counting QuickWin's internal duplicate) — convergence noted as signal._

_A persisted playback-rate toggle (1x/1.25x/1.5x localStorage chips) on the audio card AND navigator.mediaSession metadata + action handlers (play/pause/seekto/prev-next-chapter) wired to the existing single <audio> element and brief.audio_chapters offsets in BriefShell.tsx — turning the daily brief into a podcast-grade lock-screen listen. Frontend-only, no backend change, one sitting._

## Premise

The daily listen becomes controllable from the lock screen — chapter titles, seek, and a persisted speed — so a walk-brief no longer requires unlocking and re-scrubbing.

**Why now:** Directly serves assumption 6 (phone-first): the daily audio is the second surface of the habit, and its most common real context — locked phone on a walk — is exactly where it's weakest today. Distinct from the shipped audio-resume/chapters idea docs: this is the first OS-integration surface and first rate control.

## The bet

The bet: the walk-listen is the audio brief's real use, and it silently degrades the instant the phone locks (anonymous file, no seek, stuck at 1x). What lands with a veteran: ZERO mediaSession references exist anywhere in frontend/src (grep-confirmed), yet every hard part already shipped — audioRef, audio_chapters with start offsets, chapter-chip seeking, resume position, the onLoadedMetadata handler. Both the OS-integration gap and the rate gap live in the same ~40-line card. 1.5x returns ~100 seconds every single morning.

## Decisions / open questions

(1) Chapter prev/next as previoustrack/nexttrack vs seekbackward/seekforward(15s) — which pair earns the two lock-screen slots? (2) Should the archive player (once unified per bug #20) get the same wiring in the same pass?

## Credible first step

A contained useEffect in /Users/kyledisch/Projects/home-base/frontend/src/components/BriefShell.tsx: set mediaSession.metadata (title 'Morning brief — {brief.date}'), update chapter title on timeupdate against the existing audio_chapters offsets (line 104), register play/pause/seekto/previoustrack/nexttrack reusing the same el.currentTime seek; add rate chips applied in the existing onLoadedMetadata handler (line 133), key 'audio-rate'.

## Dependencies

frontend/src/components/BriefShell.tsx (audioRef, audio_chapters, onLoadedMetadata, seekChapter), navigator.mediaSession (iOS Safari PWA), localStorage.

## Explicitly out of scope (revisit later)

No podcast RSS feed (separate parked candidate), no backend change, no new audio artifacts.

## Identity/positioning note

none — tethered.
