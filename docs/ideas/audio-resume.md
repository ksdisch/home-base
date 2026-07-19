# Pick up the walk where it left off

**Status:** Idea — not committed. Added by `/brainstorm` (QuickWin mode) on 2026-07-19.

_A localStorage-backed resume on the audio brief: persist the <audio> element's currentTime keyed by brief date and restore it on load, so an interrupted ~5-min Kokoro cut doesn't snap back to 0:00._

## Premise

The M4 player is a stateless <audio> element inside a route-scoped component. Every interruption a walk actually produces — a call, crossing a street, the phone locking, the PWA backgrounding — currently resets it to 0:00. Keying currentTime to the brief date in localStorage and restoring on mount fixes it with browser APIs already on the page, and because the key is date-scoped it self-invalidates when tomorrow's brief lands.

**Why now:** M4's player (shipped 2026-07-16) is still a bare <audio controls preload="none"> with no state, and M6 made the app an installed PWA on Kyle's phone — the precise context (backgrounded WebView reloads, phone locks mid-walk) where losing playback position bites hardest. The listening mode and the phone install both now exist; the resume that makes them survivable does not.

## The bet

No load-bearing assumption targeted — this is pure recurring-tax relief. The one thing that must be true: that 'audio on a walk' is a real, repeated usage mode and walks genuinely get interrupted (a call, a locked phone, a backgrounded PWA whose WebView reloads). The soul brief names audio-on-a-walk as a core-loop mode explicitly, so the bet is well-grounded; a veteran barely flinches here — it's a papercut fix — but the flinch it earns is 'you built a 5-minute audio feature for walks and shipped it with zero playback memory,' which is exactly the gap this closes.

## Decisions / open questions

Clear the saved position on ended, or keep it so a re-open resumes at the end? This is complementary to but distinct from the Friction-lane FR15 (which hoists the audio element above the router to survive in-app navigation) — localStorage persistence also survives a full reload/PWA-reload, so it's robust and ship-order-independent whether or not FR15 lands; worth confirming they don't double-manage position.

## Credible first step

frontend/src/pages/Brief.tsx, the audio_available block at line 395-402 where the bare <audio controls preload="none" src={api.briefAudioUrl()}> lives: add onTimeUpdate writing currentTime to localStorage under a key like `audio-pos-${brief.date}`, onLoadedMetadata seeking to any saved position before first play, onEnded clearing the key. No backend, no API, no new component — verified the element has zero position memory today.

## Dependencies

None beyond browser localStorage and the existing <audio> element; brief.date is already in scope in the component for the key.

## Explicitly out of scope (revisit later)

No backend or API change; no cross-device sync (localStorage is per-browser by design); no playback-speed or volume memory; no rebuild of the player UI — just position persistence on the element that's already there.

## Identity/positioning note

none — tethered.
