import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Brief from "./Brief";

// Mock the API client so the page renders deterministically without a backend. The Today
// page also mounts the Your-learning strip (review + courses) and the note composer, so
// those calls need deterministic defaults too.
const brief = vi.fn();
const logBriefVisit = vi.fn();
const review = vi.fn();
const courses = vi.fn();
const addBriefNote = vi.fn();
const deleteBriefNote = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    brief: () => brief(),
    logBriefVisit: () => logBriefVisit(),
    review: () => review(),
    courses: () => courses(),
    addBriefNote: (body: unknown) => addBriefNote(body),
    deleteBriefNote: (id: number) => deleteBriefNote(id),
  },
}));

beforeEach(() => {
  brief.mockReset();
  logBriefVisit.mockReset();
  review.mockReset();
  courses.mockReset();
  addBriefNote.mockReset();
  deleteBriefNote.mockReset();
  logBriefVisit.mockResolvedValue({ ok: true, day: "2026-07-14", visited_at: "" });
  // Quiet defaults: nothing due, no courses → the strip hides itself.
  review.mockResolvedValue({ generated_at: "now", has_data: false, due_count: 0, items: [] });
  courses.mockResolvedValue({ generated_at: "now", courses: [] });
});

const ITEM = {
  id: "abc123def456",
  headline: "OpenAI lifts caps",
  attribution: "Bleeping Computer, July 13, 2026",
  digest: "OpenAI removed the rolling cap.",
  why_it_matters: "Session budgets change.",
  sources: [{ title: "Bleeping Computer", url: "https://example.com/a" }],
  notes: [] as unknown[],
};

const STRUCTURED = {
  generated_at: "now",
  has_data: true,
  date: "2099-01-01", // far future so the stale banner can't flake on real dates
  topics: [
    {
      slug: "ai-llms",
      title: "AI / LLMs",
      as_of: "2099-01-01 07:05 CDT",
      top_line: "One release actually worth your time.",
      context_note: "Dead-quiet window.",
      items: [ITEM],
      raw_markdown: null,
      error: null,
    },
  ],
};

function renderBrief() {
  return render(
    <MemoryRouter>
      <Brief />
    </MemoryRouter>,
  );
}

describe("Brief (Today page)", () => {
  it("renders a structured topic — items, sources, as-of — and logs a visit", async () => {
    brief.mockResolvedValue(STRUCTURED);
    renderBrief();

    expect(await screen.findByText("AI / LLMs")).toBeInTheDocument();
    expect(screen.getByText(/as of 2099-01-01 07:05 CDT/)).toBeInTheDocument();
    expect(screen.getByText("One release actually worth your time.")).toBeInTheDocument();
    expect(screen.getByText("Dead-quiet window.")).toBeInTheDocument();
    expect(screen.getByText("OpenAI lifts caps")).toBeInTheDocument();
    expect(screen.getByText(/Why it matters:/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bleeping Computer" })).toHaveAttribute(
      "href",
      "https://example.com/a",
    );
    expect(logBriefVisit).toHaveBeenCalled();
  });

  it("renders a raw-markdown fallback topic (legacy md-only day) with a stale hint", async () => {
    brief.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      date: "2026-07-13", // in the past by the time this runs → stale banner
      topics: [
        {
          slug: "fantasy-football",
          title: "Fantasy football",
          as_of: "2026-07-13 16:47 CDT",
          top_line: null,
          context_note: null,
          items: [],
          raw_markdown: "**Quiet camp-eve Monday.**\n\n### An item — PFR, July 11\nBody text.",
          error: null,
        },
      ],
    });
    renderBrief();

    expect(await screen.findByText("Fantasy football")).toBeInTheDocument();
    expect(screen.getByText("Quiet camp-eve Monday.")).toBeInTheDocument();
    expect(screen.getByText(/An item — PFR, July 11/)).toBeInTheDocument();
  });

  it("empty state points at make sweep", async () => {
    brief.mockResolvedValue({ generated_at: "now", has_data: false, date: null, topics: [] });
    renderBrief();

    expect(await screen.findByText(/No sweeps yet/)).toBeInTheDocument();
    expect(screen.getByText("make sweep")).toBeInTheDocument();
  });

  it("a failed brief load still shows the error banner (and never a blank page)", async () => {
    brief.mockRejectedValue(new Error("backend down"));
    renderBrief();

    expect(await screen.findByText(/Couldn't load the brief/)).toBeInTheDocument();
    expect(screen.getByText(/backend down/)).toBeInTheDocument();
  });

  it("renders an item's existing notes and saves a new one from the composer", async () => {
    brief.mockResolvedValue({
      ...STRUCTURED,
      topics: [
        {
          ...STRUCTURED.topics[0],
          items: [
            {
              ...ITEM,
              notes: [
                {
                  id: 1,
                  item_id: ITEM.id,
                  topic_slug: "ai-llms",
                  topic_title: "AI / LLMs",
                  brief_date: "2099-01-01",
                  item_headline: ITEM.headline,
                  body: "An earlier take.",
                  created_at: "t1",
                },
              ],
            },
          ],
        },
      ],
    });
    addBriefNote.mockResolvedValue({
      id: 2,
      item_id: ITEM.id,
      topic_slug: "ai-llms",
      topic_title: "AI / LLMs",
      brief_date: "2099-01-01",
      item_headline: ITEM.headline,
      body: "My hot take",
      created_at: "t2",
    });
    renderBrief();

    expect(await screen.findByText("An earlier take.")).toBeInTheDocument();

    fireEvent.click(screen.getByText("+ Add note"));
    fireEvent.change(screen.getByPlaceholderText(/Your take or question/), {
      target: { value: "My hot take" },
    });
    fireEvent.click(screen.getByText("Save note"));

    await waitFor(() => expect(screen.getByText("My hot take")).toBeInTheDocument());
    expect(addBriefNote).toHaveBeenCalledWith(
      expect.objectContaining({
        item_id: "abc123def456",
        topic_slug: "ai-llms",
        brief_date: "2099-01-01",
        item_headline: "OpenAI lifts caps",
        body: "My hot take",
      }),
    );
  });

  it("surfaces due reviews and active courses in the Your-learning strip", async () => {
    brief.mockResolvedValue({ generated_at: "now", has_data: false, date: null, topics: [] });
    review.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      due_count: 1,
      items: [
        {
          notebook_id: "nb1",
          title: "SQL Joins",
          due: true,
          reason: "3 shaky questions",
          mastery: 0.4,
          decayed: 0.2,
          priority: 1,
          total_misses: 3,
          shaky_questions: 3,
        },
        {
          notebook_id: "nb2",
          title: "Fresh topic",
          due: false,
          reason: "",
          mastery: 0.9,
          decayed: 0.9,
          priority: 0,
          total_misses: 0,
          shaky_questions: 0,
        },
      ],
    });
    courses.mockResolvedValue({
      generated_at: "now",
      courses: [{ slug: "sql-101", title: "SQL 101", progress_pct: 40 }],
    });
    renderBrief();

    expect(await screen.findByText("Your learning")).toBeInTheDocument();
    expect(screen.getByText("SQL Joins")).toBeInTheDocument();
    expect(screen.queryByText("Fresh topic")).not.toBeInTheDocument(); // only DUE items surface
    expect(screen.getByText("SQL 101")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start a session/ })).toHaveAttribute(
      "href",
      "/plan",
    );
  });
});
