import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import News from "./News";
import { NewsShell } from "../components/NewsShell";

const newsCategories = vi.fn();
const newsCategory = vi.fn();
const newsForYou = vi.fn();
const logNewsEvent = vi.fn();
const addNewsTopic = vi.fn();
const dismissNewsSuggestion = vi.fn();
const addBriefNote = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    newsCategories: () => newsCategories(),
    newsCategory: (slug: string) => newsCategory(slug),
    newsForYou: () => newsForYou(),
    logNewsEvent: (body: unknown) => logNewsEvent(body),
    addNewsTopic: (body: unknown) => addNewsTopic(body),
    dismissNewsSuggestion: (body: unknown) => dismissNewsSuggestion(body),
    addBriefNote: (body: unknown) => addBriefNote(body),
  },
}));

const CATEGORIES = {
  generated_at: "now",
  categories: [
    { slug: "top", title: "Top stories" },
    { slug: "local", title: "Local" },
  ],
};

const TOP_FEED = {
  generated_at: "now",
  slug: "top",
  title: "Top stories",
  fetched_at: "2026-07-18T12:00:00+00:00",
  stale: false,
  items: [
    {
      id: "abc123abc123",
      headline: "Big national story",
      url: "https://news.example/1",
      source: "AP News",
      published_at: "2026-07-18T11:00:00+00:00",
    },
    {
      id: "def456def456",
      headline: "Undated story",
      url: "https://news.example/2",
      source: null,
      published_at: null,
    },
  ],
};

const LOCAL_FEED = {
  ...TOP_FEED,
  slug: "local",
  title: "Local",
  items: [
    {
      id: "loc111loc111",
      headline: "Lake County story",
      url: "https://news.example/3",
      source: "Patch",
      published_at: "2026-07-18T10:00:00+00:00",
    },
  ],
};

const FORYOU_WARM = {
  generated_at: "now",
  learning: false,
  event_count: 42,
  suggestions: [],
  items: [
    {
      id: "fy1fy1fy1fy1",
      headline: "Ranked quantum story",
      url: "https://news.example/q",
      source: "Wire",
      published_at: "2026-07-18T11:30:00+00:00",
      category_slug: "top",
    },
    {
      id: "fy2fy2fy2fy2",
      headline: "Searched interest story",
      url: "https://news.example/s",
      source: "Blog",
      published_at: "2026-07-18T09:00:00+00:00",
      category_slug: "search:quantum computing",
    },
  ],
};

function renderNews(path = "/news") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <NewsShell>
        <News />
      </NewsShell>
    </MemoryRouter>,
  );
}

const SUGGESTION = {
  term: "quantum computing",
  score: 11.6,
  days_seen: 3,
  example_headlines: ["Quantum computing breakthrough at the lab"],
};

beforeEach(() => {
  sessionStorage.clear();
  newsCategories.mockReset();
  newsCategory.mockReset();
  newsForYou.mockReset();
  logNewsEvent.mockReset();
  addNewsTopic.mockReset();
  dismissNewsSuggestion.mockReset();
  addBriefNote.mockReset();
  logNewsEvent.mockResolvedValue({ ok: true, id: 1, created_at: "now" });
});

describe("News (M7)", () => {
  // F1 (full hoist): the per-visit interaction state must outlive a Today→News→Today hop.
  // NewsShell holds hidden/liked/noted above the route, so a remount (the feed refetches
  // fresh) reconciles against the same sets instead of resetting them.
  it("keeps the liked ack across a News remount — state lives above the route (F1)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);

    function Harness() {
      const [mounted, setMounted] = useState(true);
      return (
        <MemoryRouter initialEntries={["/news?cat=top"]}>
          <NewsShell>
            {mounted && <News />}
            <button onClick={() => setMounted((m) => !m)}>toggle-news</button>
          </NewsShell>
        </MemoryRouter>
      );
    }
    render(<Harness />);

    // Like a card → its button flips to the saved ack.
    const like = await screen.findByRole("button", { name: /More like Big national story/ });
    fireEvent.click(like);
    expect(
      await screen.findByRole("button", { name: /More like Big national story/ }),
    ).toHaveTextContent("Noted ✓");

    // Unmount + remount News (a Today→News round trip); the feed refetches fresh.
    fireEvent.click(screen.getByRole("button", { name: "toggle-news" }));
    fireEvent.click(screen.getByRole("button", { name: "toggle-news" }));

    // The like survived above the route — no reset to "More like this".
    const back = await screen.findByRole("button", { name: /More like Big national story/ });
    expect(back).toHaveTextContent("Noted ✓");
  });

  it("lands on For You by default with origin chips", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    renderNews();

    expect(await screen.findByText("Ranked quantum story")).toBeInTheDocument();
    expect(newsForYou).toHaveBeenCalled();
    expect(newsCategory).not.toHaveBeenCalled();
    // Origin chips: a section title for section items, the quoted term for search finds.
    expect(screen.getAllByText("Top stories").length).toBeGreaterThanOrEqual(2); // tab + chip
    expect(screen.getByText("“quantum computing”")).toBeInTheDocument();
  });

  // -- F1 first wedge: News remembers the tab across a navigation hop --------------

  it("restores the last-opened tab on return via sessionStorage (F1)", async () => {
    sessionStorage.setItem("news.tab", "local");
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(LOCAL_FEED);
    renderNews("/news"); // no ?cat= — as if returning from Today

    expect(await screen.findByText("Lake County story")).toBeInTheDocument();
    expect(newsCategory).toHaveBeenCalledWith("local");
    expect(newsForYou).not.toHaveBeenCalled();
  });

  it("persists the opened tab so the next return lands there (F1)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    newsCategory.mockResolvedValue(LOCAL_FEED);
    renderNews();
    await screen.findByText("Ranked quantum story");

    fireEvent.click(screen.getByRole("button", { name: "Local" }));
    await screen.findByText("Lake County story");
    expect(sessionStorage.getItem("news.tab")).toBe("local");
  });

  // -- ① lead hierarchy + F2 primary action ----------------------------------------

  it("promotes the top story to a lead and keeps the rest compact (①)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    renderNews();

    const lead = (await screen.findByText("Ranked quantum story")).closest("a");
    const minor = screen.getByText("Searched interest story").closest("a");
    expect(lead?.className).toMatch(/text-lede/);
    expect(minor?.className).not.toMatch(/text-lede/);
  });

  it("makes the headline the primary tap with an open-in-source affordance (F2)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    renderNews();

    const lead = (await screen.findByText("Ranked quantum story")).closest("a");
    expect(lead).toHaveAttribute("href", "https://news.example/q"); // still opens the article
    expect(lead?.className).toMatch(/font-semibold/);
    expect(lead).toHaveTextContent("↗"); // the open-in-source glyph
  });

  it("gives the category pills ≥44px thumb targets (C5)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    renderNews();
    await screen.findByText("Ranked quantum story");

    const pill = screen.getByRole("button", { name: "Top stories" });
    expect(pill.className).toMatch(/min-h-\[44px\]/);
  });

  it("shows the learning banner during cold start", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue({
      ...FORYOU_WARM,
      learning: true,
      event_count: 3,
      items: FORYOU_WARM.items.slice(0, 1),
    });
    renderNews();

    expect(await screen.findByText("Still learning you")).toBeInTheDocument();
    expect(screen.getByText(/3 of 20 signals/)).toBeInTheDocument();
    expect(screen.getByText("Ranked quantum story")).toBeInTheDocument();
  });

  it("cold start leads with a 'do this first' next-action nudge (F3)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue({
      ...FORYOU_WARM,
      learning: true,
      event_count: 3,
      items: FORYOU_WARM.items.slice(0, 1),
    });
    renderNews();

    // The cold-start banner opens with a directional first move, not just a status line.
    expect(await screen.findByText(/Do this first/i)).toBeInTheDocument();
    expect(screen.getByText("Still learning you")).toBeInTheDocument();
    expect(screen.getByText(/3 of 20 signals/)).toBeInTheDocument(); // status line kept
  });

  it("the first-move nudge clears once For You is warm (F3)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM); // learning:false, event_count:42
    renderNews();

    await screen.findByText("Ranked quantum story");
    expect(screen.queryByText("Still learning you")).not.toBeInTheDocument();
    expect(screen.queryByText(/Do this first/i)).not.toBeInTheDocument();
  });

  it("renders a category feed with articles opening at the source", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");

    expect(await screen.findByText("Big national story")).toBeInTheDocument();
    expect(newsCategory).toHaveBeenCalledWith("top");
    expect(newsForYou).not.toHaveBeenCalled();
    expect(screen.getByText("AP News")).toBeInTheDocument();
    const link = screen.getByText("Big national story").closest("a");
    expect(link).toHaveAttribute("href", "https://news.example/1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.getByText("Undated story")).toBeInTheDocument();
  });

  it("switches categories via the tabs", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockImplementation((slug: string) =>
      Promise.resolve(slug === "local" ? LOCAL_FEED : TOP_FEED),
    );
    renderNews("/news?cat=top");
    await screen.findByText("Big national story");

    fireEvent.click(screen.getByText("Local"));
    expect(await screen.findByText("Lake County story")).toBeInTheDocument();
    expect(newsCategory).toHaveBeenLastCalledWith("local");
  });

  it("flags a stale category payload honestly", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue({ ...TOP_FEED, stale: true });
    renderNews("/news?cat=top");

    expect(await screen.findByText("Showing saved articles")).toBeInTheDocument();
    expect(screen.getByText("Big national story")).toBeInTheDocument();
  });

  it("shows the section error without killing the tabs", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockRejectedValue(new Error("news feed unavailable: down"));
    renderNews("/news?cat=top");

    expect(await screen.findByText("Couldn't load this section")).toBeInTheDocument();
    expect(screen.getByText("For You")).toBeInTheDocument(); // tabs survive
  });

  it("shows the empty state when no categories are configured", async () => {
    newsCategories.mockResolvedValue({ generated_at: "now", categories: [] });
    renderNews();

    expect(await screen.findByText("No news categories configured")).toBeInTheDocument();
    expect(newsCategory).not.toHaveBeenCalled();
    expect(newsForYou).not.toHaveBeenCalled();
    expect(logNewsEvent).not.toHaveBeenCalled(); // no tab, no visit signal
  });

  // -- Phase 2 signals ------------------------------------------------------------

  it("logs a visit per tab opened, including For You", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews();
    await screen.findByText("Ranked quantum story");

    expect(logNewsEvent).toHaveBeenCalledWith({ kind: "visit", category_slug: "foryou" });

    fireEvent.click(screen.getByRole("button", { name: "Top stories" }));
    await waitFor(() =>
      expect(logNewsEvent).toHaveBeenCalledWith({ kind: "visit", category_slug: "top" }),
    );
  });

  it("logs a click with the full item snapshot", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");

    fireEvent.click(await screen.findByText("Big national story"));
    expect(logNewsEvent).toHaveBeenCalledWith({
      kind: "click",
      category_slug: "top",
      item_id: "abc123abc123",
      headline: "Big national story",
      source: "AP News",
      url: "https://news.example/1",
    });
  });

  it("credits For You item signals to their origin section", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    renderNews();

    fireEvent.click(await screen.findByText("Ranked quantum story"));
    expect(logNewsEvent).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "click", category_slug: "top" }),
    );
  });

  it("more-like-this logs once and acknowledges", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");
    await screen.findByText("Big national story");

    const btn = screen.getByLabelText("More like Big national story");
    fireEvent.click(btn);
    fireEvent.click(btn); // second click is a no-op, not a double signal
    expect(logNewsEvent.mock.calls.filter(([b]) => b.kind === "more_like")).toHaveLength(1);
    expect(screen.getByText("Noted ✓")).toBeInTheDocument();
  });

  // -- Phase 4 topic scout ----------------------------------------------------------

  it("renders a scout suggestion with its evidence", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue({ ...FORYOU_WARM, suggestions: [SUGGESTION] });
    renderNews();

    expect(await screen.findByText("quantum computing")).toBeInTheDocument();
    expect(screen.getByText(/across 3 days/)).toBeInTheDocument();
    expect(screen.getByText(/Quantum computing breakthrough/)).toBeInTheDocument();
  });

  it("add-to-brief calls the API and confirms in place", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue({ ...FORYOU_WARM, suggestions: [SUGGESTION] });
    addNewsTopic.mockResolvedValue({ ok: true, slug: "quantum-computing", title: "Quantum Computing" });
    renderNews();
    await screen.findByText("quantum computing");

    fireEvent.click(screen.getByText("Add to my brief"));
    expect(await screen.findByText(/Added ✓/)).toBeInTheDocument();
    expect(addNewsTopic).toHaveBeenCalledWith({ term: "quantum computing" });
  });

  it("dismiss calls the API and drops the card", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue({ ...FORYOU_WARM, suggestions: [SUGGESTION] });
    dismissNewsSuggestion.mockResolvedValue({ ok: true, term: "quantum computing" });
    renderNews();
    await screen.findByText("quantum computing");

    fireEvent.click(screen.getByText("Don't suggest this"));
    await waitFor(() =>
      expect(screen.queryByText("quantum computing")).not.toBeInTheDocument(),
    );
    expect(dismissNewsSuggestion).toHaveBeenCalledWith({ term: "quantum computing" });
    expect(screen.getByText("Ranked quantum story")).toBeInTheDocument(); // feed unaffected
  });

  it("not-interested hides the card now and logs after the undo window (FR10)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");
    await screen.findByText("Big national story");

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByLabelText("Not interested in Big national story"));
      expect(screen.queryByText("Big national story")).not.toBeInTheDocument();
      expect(screen.getByText("Undated story")).toBeInTheDocument(); // only that card hides
      expect(logNewsEvent).not.toHaveBeenCalledWith(
        expect.objectContaining({ kind: "not_interested" }),
      ); // the −8 holds during the window
      act(() => {
        vi.runAllTimers();
      });
      expect(logNewsEvent).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "not_interested", item_id: "abc123abc123" }),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("undo within the window restores the card and never fires the signal (FR10)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");
    await screen.findByText("Big national story");

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByLabelText("Not interested in Big national story"));
      fireEvent.click(screen.getByRole("button", { name: "Undo" }));
      expect(screen.getByText("Big national story")).toBeInTheDocument();
      act(() => {
        vi.runAllTimers();
      });
      expect(logNewsEvent).not.toHaveBeenCalledWith(
        expect.objectContaining({ kind: "not_interested" }),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  // -- QU5 notes-on-News: the note verb reaches the grazing surface -----------------

  const localToday = () => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  };

  it("saves a note on a category card through the one brief-notes path", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    addBriefNote.mockResolvedValue({ id: 1 });
    renderNews("/news?cat=top");
    await screen.findByText("Big national story");

    fireEvent.click(screen.getByLabelText("Note on Big national story"));
    fireEvent.change(screen.getByPlaceholderText(/Your take/), {
      target: { value: "Worth tracking" },
    });
    fireEvent.click(screen.getByText("Save note"));

    expect(await screen.findByText("✓ Saved")).toBeInTheDocument();
    expect(addBriefNote).toHaveBeenCalledWith({
      item_id: "abc123abc123",
      topic_slug: "top",
      brief_date: localToday(),
      item_headline: "Big national story",
      body: "Worth tracking",
    });
  });

  it("credits a For You note to its origin section, like the signals", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsForYou.mockResolvedValue(FORYOU_WARM);
    addBriefNote.mockResolvedValue({ id: 2 });
    renderNews();
    await screen.findByText("Ranked quantum story");

    fireEvent.click(screen.getByLabelText("Note on Ranked quantum story"));
    fireEvent.change(screen.getByPlaceholderText(/Your take/), {
      target: { value: "Keep an eye on this" },
    });
    fireEvent.click(screen.getByText("Save note"));

    await screen.findByText("✓ Saved");
    expect(addBriefNote).toHaveBeenCalledWith(
      expect.objectContaining({ topic_slug: "top", item_id: "fy1fy1fy1fy1" }),
    );
  });

  it("a failed note save shows the error and keeps the composer open", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    addBriefNote.mockRejectedValue(new Error("hub unreachable"));
    renderNews("/news?cat=top");
    await screen.findByText("Big national story");

    fireEvent.click(screen.getByLabelText("Note on Big national story"));
    fireEvent.change(screen.getByPlaceholderText(/Your take/), {
      target: { value: "Worth tracking" },
    });
    fireEvent.click(screen.getByText("Save note"));

    expect(await screen.findByText(/hub unreachable/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Your take/)).toBeInTheDocument();
    expect(screen.queryByText("✓ Saved")).not.toBeInTheDocument();
  });

  // Read-dimming (docs/ideas/news-read-dimming.md): the headline anchor is custom-styled,
  // so the browser's native :visited never fires — a story opened at 06:45 came back
  // pixel-identical at lunch. The click rows were already in news_events; this is the
  // replay Kyle's own eyes never got.

  it("dims a story already opened and leaves the rest alone", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue({
      ...TOP_FEED,
      items: [
        { ...TOP_FEED.items[0], clicked: true },
        { ...TOP_FEED.items[1], clicked: false },
      ],
    });
    renderNews("/news?cat=top");

    const read = await screen.findByText(/Big national story/);
    const unread = screen.getByText(/Undated story/);
    expect(read.className).toMatch(/text-muted/);
    expect(unread.className).not.toMatch(/text-muted/);
  });

  it("marks the read one with a ✓ a screen reader can also hear", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue({
      ...TOP_FEED,
      items: [{ ...TOP_FEED.items[0], clicked: true }, TOP_FEED.items[1]],
    });
    renderNews("/news?cat=top");

    await screen.findByText(/Big national story/);
    expect(screen.getByTitle(/already opened/i)).toBeInTheDocument();
    expect(screen.queryAllByTitle(/already opened/i)).toHaveLength(1);
  });

  it("dims a card the moment it is opened, without waiting for a refetch", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");

    const link = await screen.findByText(/Big national story/);
    expect(link.className).not.toMatch(/text-muted/);
    fireEvent.click(link);

    await waitFor(() => expect(screen.getByText(/Big national story/).className).toMatch(/text-muted/));
  });

  it("a payload with no clicked field at all dims nothing (pre-dimming SW cache)", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews("/news?cat=top");

    await screen.findByText(/Big national story/);
    expect(screen.queryByTitle(/already opened/i)).not.toBeInTheDocument();
  });
});
