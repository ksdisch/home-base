# Ghost narrator + dueling archive player — invisible playback off-route, and two voices at once on the archive branch

**Status:** Idea — not committed. Added by `/replenish` (Friction lane) on 2026-07-26.

_Friction lane; bug-hunt independently verified the same surface drifting (report #20, ArchiveAudioCard feature drift) — complementary fixes, consider one shared player component._

_Give the always-playing brief a visible owner and enforce a single-track rule: track isPlaying in BriefShell, expose {isPlaying, pause, date} through the existing BriefShellContext, and portal a compact fixed 'Now playing — {humanDateShort(date)} · pause' pill whenever audio plays with no card on screen (isPlaying && slot === null). On the in-flight feat/brief-archive-nav branch, ArchiveAudioCard's onPlay calls the shell's pause() so an archived morning can't layer a second narration over the first._

## Premise

Audio can never again play with no visible control, and an archived morning can never dogpile two voices — the brief always has exactly one owner on screen.

**Why now:** The archive branch is unmerged and checked out RIGHT NOW (feat/brief-archive-nav, commits c0d8455 + fe53288), so the dueling-player break ships the moment it merges. This is the in-app control layer; the lock-screen card is the OS layer — complementary, not duplicate.

## The bet

The bet: the friction is the un-designed interaction BETWEEN three shipped features, and it's a LIVE bug on the currently checked-out branch — not hypothetical. What makes a project veteran react: BriefArchive.tsx mounts its OWN independent <audio> (ArchiveAudioCard, verified lines 14–62) with zero coordination with BriefShell's hoisted element, so tapping play on an archived day layers two near-identical narrations and the Today one is unpausable from that screen; off-route BriefShell keeps sound playing by design ('invisible, still playing') with no on-screen control anywhere. Must be true: the single-audio invariant is worth enforcing — two Kokoro voices over each other is the definition of a wince.

## Decisions / open questions

(1) Pill placement vs the bottom tab bar on phone? (2) Does the pill deep-link back to the owning page (Today vs the archived day)? (3) Fold report-bug #20's shared-component unification into the same change?

## Credible first step

On the already-open feat/brief-archive-nav branch: add isPlaying/pause to /Users/kyledisch/Projects/home-base/frontend/src/components/BriefShell.tsx via onPlay/onPause + a portaled fixed pill when slot===null; in /Users/kyledisch/Projects/home-base/frontend/src/pages/BriefArchive.tsx wire ArchiveAudioCard's onPlay to shell.pause(). One sitting.

## Dependencies

frontend/src/components/BriefShell.tsx (BriefShellContext, portal host), frontend/src/pages/BriefArchive.tsx ArchiveAudioCard, the in-flight feat/brief-archive-nav branch.

## Explicitly out of scope (revisit later)

No queueing/playlist behavior, no crossfade — pause-the-other is the whole rule. Lock-screen controls are [`docs/ideas/lock-screen-audio-controls.md`](lock-screen-audio-controls.md), not this.

## Identity/positioning note

none — tethered.
