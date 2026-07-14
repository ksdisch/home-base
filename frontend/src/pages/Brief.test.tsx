import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Brief from "./Brief";

// Mock the API client so the page renders deterministically without a backend.
const brief = vi.fn();
const logBriefVisit = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    brief: () => brief(),
    logBriefVisit: () => logBriefVisit(),
  },
}));

beforeEach(() => {
  brief.mockReset();
  logBriefVisit.mockReset();
  logBriefVisit.mockResolvedValue({ ok: true, day: "2026-07-14", visited_at: "" });
});

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
      items: [
        {
          headline: "OpenAI lifts caps",
          attribution: "Bleeping Computer, July 13, 2026",
          digest: "OpenAI removed the rolling cap.",
          why_it_matters: "Session budgets change.",
          sources: [{ title: "Bleeping Computer", url: "https://example.com/a" }],
        },
      ],
      raw_markdown: null,
      error: null,
    },
  ],
};

describe("Brief (Today page)", () => {
  it("renders a structured topic — items, sources, as-of — and logs a visit", async () => {
    brief.mockResolvedValue(STRUCTURED);
    render(<Brief />);

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
    render(<Brief />);

    expect(await screen.findByText("Fantasy football")).toBeInTheDocument();
    expect(screen.getByText("Quiet camp-eve Monday.")).toBeInTheDocument();
    expect(screen.getByText(/An item — PFR, July 11/)).toBeInTheDocument();
  });

  it("empty state points at make sweep", async () => {
    brief.mockResolvedValue({ generated_at: "now", has_data: false, date: null, topics: [] });
    render(<Brief />);

    expect(await screen.findByText(/No sweeps yet/)).toBeInTheDocument();
    expect(screen.getByText("make sweep")).toBeInTheDocument();
  });

  it("a failed brief load still shows the error banner (and never a blank page)", async () => {
    brief.mockRejectedValue(new Error("backend down"));
    render(<Brief />);

    expect(await screen.findByText(/Couldn't load the brief/)).toBeInTheDocument();
    expect(screen.getByText(/backend down/)).toBeInTheDocument();
  });
});
