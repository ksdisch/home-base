import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BriefArchive from "./BriefArchive";

// QU1: read-only time travel over the never-pruned sweep archive. The page fetches the
// requested day live (deliberately outside the FR15 shell — an archived day must never
// pollute Today's held payload or the offline cache).
const briefByDate = vi.fn();
const addBriefNote = vi.fn();
const deleteBriefNote = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    briefByDate: (date: string) => briefByDate(date),
    addBriefNote: (body: unknown) => addBriefNote(body),
    deleteBriefNote: (id: number) => deleteBriefNote(id),
  },
}));

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

beforeEach(() => {
  briefByDate.mockReset();
  addBriefNote.mockReset();
  deleteBriefNote.mockReset();
});

function renderArchive(date = "2026-07-13") {
  return render(
    <MemoryRouter initialEntries={[`/brief/${date}`]}>
      <Routes>
        <Route path="/brief/:date" element={<BriefArchive />} />
      </Routes>
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
    briefByDate.mockRejectedValue(new Error("no brief for 2026-07-01"));
    renderArchive("2026-07-01");

    expect(await screen.findByText(/isn't in the archive/)).toBeInTheDocument();
    expect(screen.getByText(/no brief for 2026-07-01/)).toBeInTheDocument();
    // The header nav and the banner both point home — either way back works.
    for (const link of screen.getAllByRole("link", { name: "Today" })) {
      expect(link).toHaveAttribute("href", "/");
    }
  });
});
