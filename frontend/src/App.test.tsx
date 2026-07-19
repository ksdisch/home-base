import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

// The shell renders both navs (CSS shows one per breakpoint — jsdom keeps both in the
// tree): the desktop top nav and the M6 mobile tab bar. Mock the api so the Today page
// mounted at "/" stays quiet.
vi.mock("./api/client", () => ({
  api: {
    briefWithMeta: () =>
      Promise.resolve({
        brief: { generated_at: "now", has_data: false, date: null, topics: [] },
        fromCache: false,
      }),
    logBriefVisit: () => Promise.resolve({ ok: true, day: "2026-07-18", visited_at: "" }),
    review: () =>
      Promise.resolve({ generated_at: "now", has_data: false, due_count: 0, items: [] }),
    courses: () => Promise.resolve({ generated_at: "now", courses: [] }),
  },
}));

beforeEach(() => vi.clearAllMocks());

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
});
