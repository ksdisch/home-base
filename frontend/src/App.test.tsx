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
    briefRunsSummary: () => Promise.resolve({ generated_at: "now", latest: null, days: [], window_days: 7, cost_usd: 0, errors: 0, missing_days: 0 }),
    newsCategories: () => Promise.resolve({ generated_at: "now", categories: [] }),
    newsForYou: () =>
      Promise.resolve({
        generated_at: "now",
        learning: true,
        event_count: 0,
        items: [],
        suggestions: [],
      }),
    newsCategory: () =>
      Promise.resolve({
        generated_at: "now",
        slug: "top",
        title: "Top stories",
        fetched_at: "now",
        stale: false,
        items: [],
      }),
    logNewsEvent: () => Promise.resolve({ ok: true, id: 1, created_at: "" }),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear(); // F5: the freshness dot reads localStorage — isolate per test.
  // jsdom has no layout, so window.scrollTo is a "not implemented" stub — spy on it.
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
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

  it("splits the desktop nav into a daily-loop cluster and a reference shelf (F5)", async () => {
    renderApp();
    await screen.findByText(/No sweeps yet/);

    const topNav = screen.getAllByRole("navigation").find((n) => !n.getAttribute("aria-label"))!;
    const kids = Array.from(topNav.children);
    const dividerIdx = kids.findIndex((el) => el.getAttribute("data-testid") === "nav-cluster-divider");
    // A divider separates the everyday core from the muted reference shelf — the priority
    // hierarchy is the grouping (order), not just a stray separator.
    expect(dividerIdx).toBeGreaterThan(-1);
    expect(kids.slice(0, dividerIdx).map((el) => el.textContent)).toEqual(["Today", "News", "Notes"]);
    expect(kids.slice(dividerIdx + 1).map((el) => el.textContent)).toEqual([
      "Learning",
      "Plan",
      "Courses",
      "Progress",
    ]);
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

  // Single audio owner: FR15 keeps the narration alive across a route hop, which is the
  // point — but off Today the card goes with the route, leaving a voice with no visible
  // source and no way to stop it. The pill is that missing control.

  it("a now-playing pill appears off-route while audio plays, and pauses it", async () => {
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
    const pause = vi.spyOn(player, "pause").mockImplementation(() => {});
    fireEvent.play(player);
    // On Today the card is right there — a pill would be redundant chrome.
    expect(screen.queryByText(/Now playing/)).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();

    expect(screen.getByText(/Now playing/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(pause).toHaveBeenCalled();

    // The element reports the stop; the pill goes with it.
    fireEvent.pause(player);
    await waitFor(() => expect(screen.queryByText(/Now playing/)).not.toBeInTheDocument());
  });

  it("no pill when the narration was never playing", async () => {
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
    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();

    expect(screen.queryByText(/Now playing/)).not.toBeInTheDocument();
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

// F2: React Router doesn't restore (or reset) window scroll across route swaps, so every
// page inherited the previous page's offset — finish a long Today read down at the habit
// strip, tap Notes, and Notes opens pre-scrolled past its own header. News is the one
// exception: it restores its saved offset itself once the feed is back, and a reset here
// would fight that with a top-flash.

describe("scroll reset on navigation (F2)", () => {
  it("scrolls a freshly opened page to the top", async () => {
    renderApp();
    await screen.findByText(/No sweeps yet/);
    (window.scrollTo as unknown as ReturnType<typeof vi.fn>).mockClear();

    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    await screen.findByText(/No notes yet/);

    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
  });

  it("leaves News alone — its own restore owns that offset", async () => {
    renderApp();
    await screen.findByText(/No sweeps yet/);
    (window.scrollTo as unknown as ReturnType<typeof vi.fn>).mockClear();

    fireEvent.click(screen.getAllByRole("link", { name: "News" })[0]);
    await screen.findByRole("heading", { name: "News" });

    expect(window.scrollTo).not.toHaveBeenCalled();
  });

  it("resets again on the way back out of News", async () => {
    renderApp();
    await screen.findByText(/No sweeps yet/);

    fireEvent.click(screen.getAllByRole("link", { name: "News" })[0]);
    await screen.findByRole("heading", { name: "News" });
    (window.scrollTo as unknown as ReturnType<typeof vi.fn>).mockClear();

    fireEvent.click(screen.getAllByRole("link", { name: "Notes" })[0]);
    await screen.findByText(/No notes yet/);

    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
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
