import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BriefIndex from "./BriefIndex";

// The archive's browsable front door — every morning the sweep ever kept, newest first.
// It shipped untested with the archive entry point; this is that coverage.
const briefArchive = vi.fn();
vi.mock("../api/client", () => ({
  api: { briefArchive: () => briefArchive() },
}));

beforeEach(() => {
  briefArchive.mockReset();
});

function renderIndex() {
  return render(
    <MemoryRouter>
      <BriefIndex />
    </MemoryRouter>,
  );
}

describe("BriefIndex (/archive)", () => {
  it("lists days newest-first, grouped by month, each linking to its morning", async () => {
    briefArchive.mockResolvedValue({
      dates: [
        { date: "2026-07-02", has_audio: false },
        { date: "2026-06-30", has_audio: false },
        { date: "2026-06-29", has_audio: false },
      ],
    });
    renderIndex();

    expect(await screen.findByText(/July 2026/)).toBeInTheDocument();
    expect(screen.getByText(/June 2026/)).toBeInTheDocument();
    // Newest month first, and the two June days stay under one heading.
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["July 2026", "June 2026"]);

    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.startsWith("/brief/"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "/brief/2026-07-02",
      "/brief/2026-06-30",
      "/brief/2026-06-29",
    ]);
  });

  it("marks the days that have an audio brief", async () => {
    briefArchive.mockResolvedValue({
      dates: [
        { date: "2026-07-02", has_audio: true },
        { date: "2026-07-01", has_audio: false },
      ],
    });
    renderIndex();

    expect(await screen.findByText(/July 2026/)).toBeInTheDocument();
    // One 🎧 marker for the one day that actually has an mp3 behind it.
    expect(screen.getAllByTitle("Audio brief available")).toHaveLength(1);
  });

  it("today is named, not linked — the archive is for mornings you've left", async () => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    briefArchive.mockResolvedValue({ dates: [{ date: today, has_audio: false }] });
    renderIndex();

    expect(await screen.findByText(/— today/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: new RegExp(String(now.getDate())) })).toBeNull();
  });

  it("a failed load says so instead of showing an empty archive", async () => {
    briefArchive.mockRejectedValue(new Error("Failed to fetch"));
    renderIndex();

    expect(await screen.findByText(/Failed to fetch/)).toBeInTheDocument();
    // Never the silent "Loading…" that would read as an archive with nothing in it.
    expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
  });
});
