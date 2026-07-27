import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BriefAudioCard } from "./BriefAudioCard";

// The four bugs the two drifted player copies carried, pinned on the one component that
// replaced them. jsdom has no real media pipeline — play/pause/load are not-implemented
// stubs — so behaviour is driven with fireEvent and observed with spies, matching the
// Object.defineProperty(player, "currentTime", …) idiom the Brief tests already use.
const CHAPTERS = [
  { slug: "ai-llms", title: "AI / LLMs", start_seconds: 95.5 },
  { slug: "fantasy-football", title: "Fantasy football", start_seconds: 1.0 },
];

function renderCard(props: Partial<Parameters<typeof BriefAudioCard>[0]> = {}) {
  const utils = render(
    <BriefAudioCard
      src="/api/brief/audio"
      chapters={CHAPTERS}
      posKey="audio-pos-2026-07-14"
      trackKey="2026-07-14"
      {...props}
    />,
  );
  const player = document.querySelector("audio")!;
  Object.defineProperty(player, "currentTime", { value: 0, writable: true, configurable: true });
  vi.spyOn(player, "play").mockImplementation(() => Promise.resolve());
  return { ...utils, player };
}

// jsdom ships no Media Session API at all, so the whole surface is stubbed: handlers
// land in a map the tests can invoke exactly as the OS would from a locked screen.
type Handler = (details?: { seekTime?: number }) => void;
let handlers: Map<string, Handler | null>;
let mediaSession: {
  metadata: unknown;
  playbackState: string;
  setActionHandler: (a: string, h: Handler | null) => void;
  setPositionState?: (s: unknown) => void;
};

beforeEach(() => {
  localStorage.clear();
  handlers = new Map();
  mediaSession = {
    metadata: null,
    playbackState: "none",
    setActionHandler: (a, h) => handlers.set(a, h),
    setPositionState: vi.fn(),
  };
  Object.defineProperty(navigator, "mediaSession", {
    value: mediaSession,
    writable: true,
    configurable: true,
  });
  // MediaMetadata is likewise absent — a plain passthrough is enough to assert on.
  (globalThis as unknown as { MediaMetadata: unknown }).MediaMetadata = class {
    constructor(init: Record<string, unknown>) {
      Object.assign(this, init);
    }
  };
});

describe("BriefAudioCard", () => {
  it("seeks a chapter 2s early and starts playback on tap (#20)", () => {
    const { player } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "AI / LLMs" }));

    expect(player.currentTime).toBe(93.5);
    expect(player.play).toHaveBeenCalled();
  });

  it("never seeks past the start of the track", () => {
    const { player } = renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Fantasy football" }));
    expect(player.currentTime).toBe(0);
  });

  // Bug #21: with preload="none" the chip tap is what triggers the load, so the metadata
  // handler fires *after* the seek — and used to overwrite it with the stale resume point.
  it("a chapter tap before metadata survives the saved-resume restore (#21)", () => {
    localStorage.setItem("audio-pos-2026-07-14", "205.5");
    const { player } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "AI / LLMs" }));
    expect(player.currentTime).toBe(93.5);
    fireEvent.loadedMetadata(player);

    expect(player.currentTime).toBe(93.5);
  });

  it("still restores the saved position when no seek is pending (QU3)", () => {
    localStorage.setItem("audio-pos-2026-07-14", "205.5");
    const { player } = renderCard();

    fireEvent.loadedMetadata(player);

    expect(player.currentTime).toBe(205.5);
  });

  it("a seek only outranks the very next metadata load, not every later one (#21)", () => {
    localStorage.setItem("audio-pos-2026-07-14", "205.5");
    const { player } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "AI / LLMs" }));
    fireEvent.loadedMetadata(player);
    expect(player.currentTime).toBe(93.5);
    // A later reload with no pending tap resumes normally again.
    fireEvent.loadedMetadata(player);
    expect(player.currentTime).toBe(205.5);
  });

  // Bug #22: one transient error used to hide the player until a full page reload.
  it("hides on a load error and comes back when retryKey bumps (#22)", () => {
    const { player, rerender } = renderCard({ retryKey: 0 });

    fireEvent.error(player);
    expect(document.querySelector("audio")).toBeNull();
    expect(screen.queryByText(/Listen to this brief/)).not.toBeInTheDocument();

    rerender(
      <BriefAudioCard
        src="/api/brief/audio"
        chapters={CHAPTERS}
        posKey="audio-pos-2026-07-14"
        trackKey="2026-07-14"
        retryKey={1}
      />,
    );

    expect(document.querySelector("audio")).not.toBeNull();
  });

  // Bug #5: the shell's src is a constant dateless URL, so a date flip under the
  // never-remounted element needs an explicit load() or yesterday's narration keeps
  // playing under today's brief — with today's chapter offsets seeking into it.
  it("pauses and reloads the element when the track date flips (#5)", () => {
    const { player, rerender } = renderCard();
    const pause = vi.spyOn(player, "pause").mockImplementation(() => {});
    const load = vi.spyOn(player, "load").mockImplementation(() => {});
    fireEvent.loadedMetadata(player);

    rerender(
      <BriefAudioCard
        src="/api/brief/audio"
        chapters={CHAPTERS}
        posKey="audio-pos-2026-07-15"
        trackKey="2026-07-15"
      />,
    );

    expect(pause).toHaveBeenCalled();
    expect(load).toHaveBeenCalled();
  });

  it("suppresses the resume write until the new track's metadata lands (#5)", () => {
    const { player, rerender } = renderCard();
    vi.spyOn(player, "pause").mockImplementation(() => {});
    vi.spyOn(player, "load").mockImplementation(() => {});
    fireEvent.loadedMetadata(player);

    rerender(
      <BriefAudioCard
        src="/api/brief/audio"
        chapters={CHAPTERS}
        posKey="audio-pos-2026-07-15"
        trackKey="2026-07-15"
      />,
    );

    // A timeupdate fired off the OLD resource must not be written under the NEW key.
    Object.defineProperty(player, "currentTime", { value: 137, writable: true, configurable: true });
    fireEvent.timeUpdate(player);
    expect(localStorage.getItem("audio-pos-2026-07-15")).toBeNull();

    // Once the new track reports itself loaded, positions persist again.
    fireEvent.loadedMetadata(player);
    fireEvent.timeUpdate(player);
    expect(localStorage.getItem("audio-pos-2026-07-15")).toBe("137");
  });

  it("clears the resume key and reports the stop when playback ends (QU3)", () => {
    localStorage.setItem("audio-pos-2026-07-14", "205.5");
    const onPause = vi.fn();
    const { player } = renderCard({ onPause });

    fireEvent.ended(player);

    expect(localStorage.getItem("audio-pos-2026-07-14")).toBeNull();
    // A natural end fires `ended`, not `pause` — the owner still has to learn the
    // narration stopped, or a now-playing pill would outlive the audio.
    expect(onPause).toHaveBeenCalled();
  });

  // Losing the element fires no `pause` — the owner has to be told, or a now-playing
  // pill outlives the audio and its Pause button points at nothing.
  it("reports the stop when a load error degrades the card away", () => {
    const onPause = vi.fn();
    const { player } = renderCard({ onPause });

    fireEvent.play(player);
    fireEvent.error(player);

    expect(document.querySelector("audio")).toBeNull();
    expect(onPause).toHaveBeenCalled();
  });

  it("reports the stop when the card unmounts mid-playback", () => {
    const onPause = vi.fn();
    const { player, unmount } = renderCard({ onPause });

    fireEvent.play(player);
    onPause.mockClear();
    unmount();

    expect(onPause).toHaveBeenCalled();
  });

  it("reports play/pause to its owner and exposes the element through mediaRef", () => {
    const onPlay = vi.fn();
    const onPause = vi.fn();
    const mediaRef = { current: null as HTMLAudioElement | null };
    const { player } = renderCard({ onPlay, onPause, mediaRef });

    expect(mediaRef.current).toBe(player);
    fireEvent.play(player);
    expect(onPlay).toHaveBeenCalled();
    fireEvent.pause(player);
    expect(onPause).toHaveBeenCalled();
  });

  // Lock-screen controls (docs/ideas/lock-screen-audio-controls.md). The walk-listen is the
  // audio brief's real use, and it degraded the moment the phone locked: an anonymous file,
  // no seek, no chapter skip, stuck at 1x. Zero mediaSession references existed anywhere in
  // frontend/src, yet every hard part — chapters with offsets, the seek, the single element
  // — had already shipped. This lands on the ONE shared card, so the archive player gets it
  // in the same pass (idea-doc question 2, answered by bug #20's extract).

  it("names the brief on the lock screen instead of an anonymous file", () => {
    renderCard();
    expect((mediaSession.metadata as { title: string }).title).toMatch(/Morning brief/);
    expect((mediaSession.metadata as { title: string }).title).toMatch(/2026-07-14|Jul 14/);
  });

  it("shows which chapter is playing as the track moves", () => {
    const { player } = renderCard();

    (player as HTMLAudioElement).currentTime = 120;
    fireEvent.timeUpdate(player);

    // 120s is past AI / LLMs' 95.5s offset — the later chapter wins.
    expect((mediaSession.metadata as { artist: string }).artist).toBe("AI / LLMs");
  });

  it("play and pause work from the lock screen", () => {
    const { player } = renderCard();
    const pause = vi.spyOn(player, "pause").mockImplementation(() => {});

    handlers.get("play")?.();
    expect(player.play).toHaveBeenCalled();

    handlers.get("pause")?.();
    expect(pause).toHaveBeenCalled();
  });

  it("the lock-screen scrubber seeks the track", () => {
    const { player } = renderCard();

    handlers.get("seekto")?.({ seekTime: 42 });

    expect(player.currentTime).toBe(42);
  });

  it("gives its two skip slots to chapters, not a blind 15 seconds", () => {
    // The brief HAS real chapters with offsets; ±15s is already reachable via the
    // scrubber, so the scarce lock-screen slots go to the thing nothing else provides.
    renderCard();
    expect(handlers.get("nexttrack")).toBeTypeOf("function");
    expect(handlers.get("previoustrack")).toBeTypeOf("function");
    expect(handlers.get("seekforward") ?? null).toBeNull();
    expect(handlers.get("seekbackward") ?? null).toBeNull();
  });

  it("skips forward to the next chapter", () => {
    const { player } = renderCard();

    // Chapters sort by offset: Fantasy football (1.0) then AI / LLMs (95.5).
    (player as HTMLAudioElement).currentTime = 10;
    handlers.get("nexttrack")?.();

    expect(player.currentTime).toBe(93.5); // the same −2s lead the chips use
  });

  it("skips back the way every media player does — restart, then previous", () => {
    const { player } = renderCard();

    // Mid-chapter, ⏮ restarts the chapter you're in rather than skipping past it.
    (player as HTMLAudioElement).currentTime = 120;
    handlers.get("previoustrack")?.();
    expect(player.currentTime).toBe(93.5);

    // Pressed again from the top of that chapter, it goes to the one before.
    handlers.get("previoustrack")?.();
    expect(player.currentTime).toBe(0); // Fantasy football at 1.0 − 2, clamped
  });

  it("skipping past the last chapter does nothing rather than jumping to the end", () => {
    const { player } = renderCard();

    (player as HTMLAudioElement).currentTime = 200;
    handlers.get("nexttrack")?.();

    expect(player.currentTime).toBe(200);
  });

  it("a card with no chapters registers no chapter skips", () => {
    renderCard({ chapters: [] });
    expect(handlers.get("nexttrack") ?? null).toBeNull();
    expect(handlers.get("previoustrack") ?? null).toBeNull();
  });

  // Speed chips: 1.5x returns ~100 seconds of every single morning.

  it("applies a chosen rate to the element and remembers it", () => {
    const { player, unmount } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "1.5x" }));
    expect(player.playbackRate).toBe(1.5);

    unmount();
    const again = renderCard();
    fireEvent.loadedMetadata(again.player);
    expect(again.player.playbackRate).toBe(1.5);
  });

  it("defaults to 1x when nothing was ever chosen", () => {
    const { player } = renderCard();
    fireEvent.loadedMetadata(player);
    expect(player.playbackRate).toBe(1);
  });

  it("a junk stored rate falls back to 1x rather than breaking playback", () => {
    localStorage.setItem("audio-rate", "not-a-number");
    const { player } = renderCard();
    fireEvent.loadedMetadata(player);
    expect(player.playbackRate).toBe(1);
  });

  it("renders nothing media-session-ish when the browser has no support", () => {
    // iOS < 15 and any non-supporting browser: the card must still work.
    Object.defineProperty(navigator, "mediaSession", { value: undefined, configurable: true });
    expect(() => renderCard()).not.toThrow();
    expect(screen.getByRole("button", { name: "1.5x" })).toBeInTheDocument();
  });
});
