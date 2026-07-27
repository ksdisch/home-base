import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BriefShell, useBriefShell } from "../components/BriefShell";
import BriefArchive from "./BriefArchive";

// QU1: read-only time travel over the never-pruned sweep archive. The page fetches the
// requested day live (its payload deliberately stays out of the FR15 shell's held brief —
// an archived day must never pollute Today's payload or the offline cache). It does sit
// *inside* the shell provider, so an archived play can stop Today's narration.
const briefByDate = vi.fn();
const briefWithMeta = vi.fn();
const addBriefNote = vi.fn();
const deleteBriefNote = vi.fn();
// importOriginal keeps the real ApiError class: the #23 branch turns on `instanceof`, so
// a hand-rolled stub would let the honest-copy split pass without being exercised.
vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ApiError: actual.ApiError,
    api: {
      briefByDate: (date: string) => briefByDate(date),
      briefWithMeta: () => briefWithMeta(),
      briefAudioUrl: (date?: string) =>
        date ? `/api/brief/audio?date=${date}` : "/api/brief/audio",
      addBriefNote: (body: unknown) => addBriefNote(body),
      deleteBriefNote: (id: number) => deleteBriefNote(id),
    },
  };
});

const ARCHIVED = {
  generated_at: "now",
  has_data: true,
  date: "2026-07-13",
  prev_date: "2026-07-12",
  next_date: "2026-07-14",
  topics: [
    {
      slug: "ai-llms",
      title: "AI / LLMs",
      as_of: "2026-07-13 07:05 CDT",
      top_line: "One release actually worth your time.",
      context_note: null,
      items: [
        {
          id: "abc123def456",
          headline: "OpenAI lifts caps",
          attribution: "Bleeping Computer, July 12, 2026",
          digest: "OpenAI removed the rolling cap.",
          why_it_matters: "Session budgets change.",
          sources: [{ title: "Bleeping Computer", url: "https://example.com/a" }],
          notes: [
            {
              id: 7,
              item_id: "abc123def456",
              topic_slug: "ai-llms",
              topic_title: "AI / LLMs",
              brief_date: "2026-07-13",
              item_headline: "OpenAI lifts caps",
              body: "what I thought that morning",
              created_at: "t",
            },
          ],
          developing: false,
          first_seen: null,
        },
      ],
      raw_markdown: null,
      error: null,
    },
  ],
  audio_available: false,
  audio_chapters: [],
  missing_topics: [],
};

const CHAPTERS = [
  { slug: "ai-llms", title: "AI / LLMs", start_seconds: 95.5 },
];

beforeEach(() => {
  briefByDate.mockReset();
  briefWithMeta.mockReset();
  addBriefNote.mockReset();
  deleteBriefNote.mockReset();
  // The shell's own Today payload defaults to silent, so `querySelector("audio")` means
  // the archive player unless a test deliberately gives Today one too.
  briefWithMeta.mockResolvedValue({
    brief: { ...ARCHIVED, date: "2026-07-20", audio_available: false, audio_chapters: [] },
    fromCache: false,
  });
});

// Off the Today route the shell's player sits in a detached portal host — still live,
// still able to play, but invisible to document queries. Registering a slot attaches it
// so a test can get a handle on it; it changes nothing about the wiring under test.
function AudioSlot() {
  const { registerAudioSlot } = useBriefShell();
  return <div ref={registerAudioSlot} />;
}

function renderArchive(date = "2026-07-13", withShellSlot = false) {
  return render(
    <MemoryRouter initialEntries={[`/brief/${date}`]}>
      <BriefShell>
        {withShellSlot && <AudioSlot />}
        <Routes>
          <Route path="/brief/:date" element={<BriefArchive />} />
        </Routes>
      </BriefShell>
    </MemoryRouter>,
  );
}

describe("BriefArchive (/brief/:date)", () => {
  it("renders the archived morning with its notes, neighbors, and no Ask (QU1)", async () => {
    briefByDate.mockResolvedValue(ARCHIVED);
    renderArchive();

    expect(await screen.findByText(/Archived brief/)).toBeInTheDocument();
    expect(briefByDate).toHaveBeenCalledWith("2026-07-13");
    // The morning as it was swept — topics, items, and the notes joined onto them.
    expect(screen.getByText("AI / LLMs")).toBeInTheDocument();
    expect(screen.getByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByText("what I thought that morning")).toBeInTheDocument();
    // Walkable history: prev/next neighbors + the way back to Today.
    expect(screen.getByRole("link", { name: /Jul 12/ })).toHaveAttribute(
      "href",
      "/brief/2026-07-12",
    );
    expect(screen.getByRole("link", { name: /Jul 14/ })).toHaveAttribute(
      "href",
      "/brief/2026-07-14",
    );
    expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("href", "/");
    // Notes stay live on an archived day; Ask doesn't — chat resolves the served
    // (latest) day only, and a button that 404s would be a broken promise.
    expect(screen.getByRole("button", { name: "+ Add note" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask about this" })).not.toBeInTheDocument();
    // No stale nag — Kyle opened a past day on purpose.
    expect(screen.queryByText(/from a previous day/)).not.toBeInTheDocument();
  });

  it("a day with no archived morning gets an honest empty state (QU1)", async () => {
    const { ApiError } = await import("../api/client");
    briefByDate.mockRejectedValue(new ApiError(404, "no brief for 2026-07-01"));
    renderArchive("2026-07-01");

    expect(await screen.findByText(/isn't in the archive/)).toBeInTheDocument();
    expect(screen.getByText(/no brief for 2026-07-01/)).toBeInTheDocument();
    // The header nav and the banner both point home — either way back works.
    for (const link of screen.getAllByRole("link", { name: "Today" })) {
      expect(link).toHaveAttribute("href", "/");
    }
  });

  // Bug #23: the archive is never pruned, so "that morning isn't here" is a claim about
  // the record — one a dead network gives no standing to make.
  it("a network failure says the hub is unreachable, not that the day is missing (#23)", async () => {
    briefByDate.mockRejectedValue(new TypeError("Failed to fetch"));
    renderArchive("2026-07-13");

    expect(await screen.findByText(/hub is unreachable/)).toBeInTheDocument();
    expect(screen.queryByText(/isn't in the archive/)).not.toBeInTheDocument();
  });

  // Bug #20: the archive player was a drifted copy — raw offsets, no play() on tap. It
  // now shares one component with the Today shell, so it inherits both.
  it("a chapter chip seeks with the −2s lead and starts playback (#20)", async () => {
    briefByDate.mockResolvedValue({
      ...ARCHIVED,
      audio_available: true,
      audio_chapters: CHAPTERS,
    });
    renderArchive();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const player = document.querySelector("audio")!;
    expect(player).toHaveAttribute("src", "/api/brief/audio?date=2026-07-13");
    Object.defineProperty(player, "currentTime", { value: 0, writable: true, configurable: true });
    const play = vi.spyOn(player, "play").mockImplementation(() => Promise.resolve());

    fireEvent.click(screen.getByRole("button", { name: "AI / LLMs" }));
    expect(player.currentTime).toBe(93.5);
    expect(play).toHaveBeenCalled();
  });

  // The single-track rule: two Kokoro voices at once is the dueling-narrator bug this
  // page would otherwise ship.
  it("playing an archived morning pauses Today's narration (single-track)", async () => {
    briefWithMeta.mockResolvedValue({
      brief: { ...ARCHIVED, date: "2026-07-20", audio_available: true, audio_chapters: [] },
      fromCache: false,
    });
    briefByDate.mockResolvedValue({ ...ARCHIVED, audio_available: true, audio_chapters: [] });
    renderArchive("2026-07-13", true);

    expect(await screen.findByText(/OpenAI lifts caps/)).toBeInTheDocument();
    const players = document.querySelectorAll("audio");
    expect(players).toHaveLength(2);
    const shellPlayer = [...players].find((p) => p.getAttribute("src") === "/api/brief/audio")!;
    const archivePlayer = [...players].find(
      (p) => p.getAttribute("src") === "/api/brief/audio?date=2026-07-13",
    )!;
    const pause = vi.spyOn(shellPlayer, "pause").mockImplementation(() => {});

    fireEvent.play(archivePlayer);
    expect(pause).toHaveBeenCalled();
  });
});
