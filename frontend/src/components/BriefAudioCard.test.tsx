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

beforeEach(() => {
  localStorage.clear();
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
});
