import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

// The shell renders both navs (CSS shows one per breakpoint — jsdom keeps both in the
// tree): the desktop top nav and the M6 mobile tab bar. Mock the api so the Today page
// mounted at "/" stays quiet; briefWithMeta is a fn so FR15 tests can serve a real
// payload, and briefNotes covers the Notes page the navigation tests hop through.
const briefWithMeta = vi.fn();
vi.mock("./api/client", () => ({
  api: {
    briefWithMeta: () => briefWithMeta(),
    briefAudioUrl: () => "/api/brief/audio",
    briefNotes: () => Promise.resolve({ notes: [] }),
    logBriefVisit: () => Promise.resolve({ ok: true, day: "2026-07-18", visited_at: "" }),
    review: () =>
      Promise.resolve({ generated_at: "now", has_data: false, due_count: 0, items: [] }),
    courses: () => Promise.resolve({ generated_at: "now", courses: [] }),
    briefHabit: () => Promise.resolve({ generated_at: "now", weeks: [] }),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear(); // F5: the freshness dot reads localStorage — isolate per test.
  briefWithMeta.mockResolvedValue({
    brief: { generated_at: "now", has_data: false, date: null, topics: [] },
    fromCache: false,
  });
});

function renderApp() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App shell navigation", () => {
  it("the desktop top nav renders all six links", async () => {
    renderApp();
    await screen.findByText(/No sweeps yet/);

    const topNav = screen.getAllByRole("navigation").find((n) => !n.getAttribute("aria-label"));
    expect(topNav).toBeTruthy();
    for (const label of ["Today", "Notes", "Learning", "Plan", "Courses", "Progress"]) {
      expect(topNav!).toHaveTextContent(label);
    }
  });

  it("the mobile tab bar renders the morning-loop tabs and More pops the rest", async () => {
    renderApp();
    await screen.findByText(/No sweeps yet/);

    const tabBar = screen.getByRole("navigation", { name: "Primary" });
    for (const label of ["Today", "Notes", "Learning", "More"]) {
      expect(tabBar).toHaveTextContent(label);
    }
    // Plan/Courses/Progress live behind More until it's opened.
    expect(tabBar).not.toHaveTextContent("Plan");
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    for (const label of ["Plan", "Courses", "Progress"]) {
      expect(tabBar).toHaveTextContent(label);
    }
  });

  // FR15: the core loop bounces Today↔News↔Notes mid-walk, but the router remounts the
  // Today route on every return — the audio brief snapped to 0:00 and the page rebuilt
  // from a blank skeleton. The brief payload and the single <audio> element must live
  // above <Routes> and survive the hop.

  it("the audio element survives Today → Notes → Today as the same node (FR15)", async () => {
    briefWithMeta.mockResolvedValue({
      brief: {
        generated_at: "now",
        has_data: true,
        date: "2099-01-01",
        topics: [],
        audio_available: true,
      },
      fromCache: false,
    });
    renderApp();

    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const player = document.querySelector("audio")!;
    Object.defineProperty(player, "currentTime", { value: 137, writable: true, configurable: true });

    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("link", { name: "Today" })[0]);
    expect(await screen.findByText(/Listen to this brief/)).toBeInTheDocument();
    const back = document.querySelector("audio")!;
    expect(back).toBe(player); // the same DOM node — playback position and state intact
    expect((back as HTMLAudioElement).currentTime).toBe(137);
  });

  it("returning to Today shows the held brief instantly — no skeleton, no flash (FR15)", async () => {
    briefWithMeta.mockResolvedValue({
      brief: {
        generated_at: "now",
        has_data: true,
        date: "2099-01-01",
        topics: [
          {
            slug: "ai-llms",
            title: "AI / LLMs",
            as_of: null,
            top_line: null,
            context_note: null,
            items: [],
            raw_markdown: null,
            error: null,
          },
        ],
      },
      fromCache: false,
    });
    renderApp();

    expect(await screen.findByText("AI / LLMs")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("link", { name: "Today" })[0]);
    // Synchronously present — the held payload renders in the same commit as the route
    // swap; no "Reading your morning brief…" flash, no skeleton.
    expect(screen.getByText("AI / LLMs")).toBeInTheDocument();
    expect(screen.queryByText(/Reading your morning brief/)).not.toBeInTheDocument();
    // Let the background revalidate settle so nothing updates outside act().
    await waitFor(() => expect(briefWithMeta).toHaveBeenCalledTimes(2));
  });
});

// F5: the nav is seven equal links with no "something new landed" signal. A freshness dot
// on Today — driven by comparing the loaded brief.date to a localStorage last-seen stamp —
// tells Kyle a new morning is waiting without opening the tab. The shell now fetches on
// mount (even off Today) so the dot can surface while he's on News/Notes.

describe("Today freshness dot (F5)", () => {
  const freshBrief = {
    brief: { generated_at: "now", has_data: true, date: "2099-01-01", topics: [] },
    fromCache: false,
  };

  it("marks the Today tab fresh when a new brief has arrived and Today isn't open", async () => {
    briefWithMeta.mockResolvedValue(freshBrief);
    render(
      <MemoryRouter initialEntries={["/notes"]}>
        <App />
      </MemoryRouter>,
    );

    // The shell fetches on mount even off Today, so the dot surfaces from another tab.
    await waitFor(() =>
      expect(screen.queryAllByTestId("today-fresh-dot").length).toBeGreaterThan(0),
    );
  });

  it("clears the dot once Today is opened and keeps it cleared after leaving again", async () => {
    briefWithMeta.mockResolvedValue(freshBrief);
    render(
      <MemoryRouter initialEntries={["/notes"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.queryAllByTestId("today-fresh-dot").length).toBeGreaterThan(0),
    );

    // Opening Today records this brief as seen → the dot clears.
    fireEvent.click(screen.getAllByRole("link", { name: "Today" })[0]);
    await waitFor(() =>
      expect(screen.queryAllByTestId("today-fresh-dot").length).toBe(0),
    );

    // Seen is persisted, not just route-hidden: it stays cleared back on another tab.
    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    await screen.findByText(/No notes yet/);
    expect(screen.queryAllByTestId("today-fresh-dot").length).toBe(0);
  });
});
