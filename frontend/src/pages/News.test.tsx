import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import News from "./News";

const newsCategories = vi.fn();
const newsCategory = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    newsCategories: () => newsCategories(),
    newsCategory: (slug: string) => newsCategory(slug),
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

function renderNews() {
  return render(
    <MemoryRouter>
      <News />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  newsCategories.mockReset();
  newsCategory.mockReset();
});

describe("News (M7 Phase 1)", () => {
  it("renders category tabs and the first category's articles at the source", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue(TOP_FEED);
    renderNews();

    expect(await screen.findByText("Big national story")).toBeInTheDocument();
    expect(newsCategory).toHaveBeenCalledWith("top"); // first category is the default tab
    expect(screen.getByText("Local")).toBeInTheDocument();
    expect(screen.getByText("AP News")).toBeInTheDocument();
    const link = screen.getByText("Big national story").closest("a");
    expect(link).toHaveAttribute("href", "https://news.example/1");
    expect(link).toHaveAttribute("target", "_blank");
    // An undated item still renders — just without a timestamp.
    expect(screen.getByText("Undated story")).toBeInTheDocument();
  });

  it("switches categories via the tabs", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockImplementation((slug: string) =>
      Promise.resolve(slug === "local" ? LOCAL_FEED : TOP_FEED),
    );
    renderNews();
    await screen.findByText("Big national story");

    fireEvent.click(screen.getByText("Local"));
    expect(await screen.findByText("Lake County story")).toBeInTheDocument();
    expect(newsCategory).toHaveBeenLastCalledWith("local");
    await waitFor(() =>
      expect(screen.queryByText("Big national story")).not.toBeInTheDocument(),
    );
  });

  it("flags a stale payload honestly", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockResolvedValue({ ...TOP_FEED, stale: true });
    renderNews();

    expect(await screen.findByText("Showing saved articles")).toBeInTheDocument();
    expect(screen.getByText("Big national story")).toBeInTheDocument(); // items still shown
  });

  it("shows the section error without killing the tabs", async () => {
    newsCategories.mockResolvedValue(CATEGORIES);
    newsCategory.mockRejectedValue(new Error("news feed unavailable: down"));
    renderNews();

    expect(await screen.findByText("Couldn't load this section")).toBeInTheDocument();
    expect(screen.getByText("Top stories")).toBeInTheDocument(); // tabs survive
  });

  it("shows the empty state when no categories are configured", async () => {
    newsCategories.mockResolvedValue({ generated_at: "now", categories: [] });
    renderNews();

    expect(await screen.findByText("No news categories configured")).toBeInTheDocument();
    expect(newsCategory).not.toHaveBeenCalled();
  });
});
