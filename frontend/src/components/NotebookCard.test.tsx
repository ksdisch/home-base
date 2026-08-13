import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NotebookCard as Card, PathResponse } from "../api/types";
import { NotebookCard } from "./NotebookCard";

// M8 #15 — the slice-quality green gate for the Learning card + its on-demand Generate flow. Mock
// the client with ONLY the two methods the card calls (path fetch + generatePath).
const path = vi.fn();
const generatePath = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    path: (id: string) => path(id),
    generatePath: (id: string) => generatePath(id),
  },
}));

function makeCard(over: Partial<Card> = {}): Card {
  return {
    notebook_id: "nb-jac",
    alias: "jac",
    title: "Jacobian Lens",
    group: "ai",
    group_label: "AI / LLMs",
    template: null,
    tags: [],
    archived: false,
    notebooklm_url: "https://notebooklm.google.com/nb-jac",
    topic_url: "/topics/nb-jac",
    counts: { audio: 12, quiz: 1 },
    courses: [],
    progress_pct: null,
    mastery: null,
    due_for_review: false,
    last_touched: null,
    ...over,
  };
}

function makePath(over: Partial<PathResponse> = {}): PathResponse {
  return {
    notebook_id: "nb-jac",
    title: "Jacobian Lens Path",
    topic: "interpretability",
    generated_at: "now",
    generator: "designer",
    steps: [
      { id: "s1", kind: "audio", title: "Listen: overview", completed: false, confidence: null },
      { id: "s2", kind: "quiz", title: "Quiz yourself", completed: false, confidence: null },
    ],
    step_count: 2,
    completed_steps: 0,
    progress_pct: 0,
    mastery: null,
    confidence: null,
    ...over,
  };
}

function renderCard(card: Card = makeCard()) {
  return render(
    <MemoryRouter>
      <NotebookCard card={card} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  path.mockReset();
  generatePath.mockReset();
});

describe("NotebookCard — path entry + on-demand Generate (M8 #15)", () => {
  it("offers ✨ Generate when no path exists, then lights up into the path state on success", async () => {
    path.mockResolvedValue(null); // 404 → no path composed yet
    generatePath.mockResolvedValue({ ok: true, path: makePath(), errors: [], error: null });
    const user = userEvent.setup();
    renderCard();

    const gen = await screen.findByRole("button", { name: /Generate path/ });
    await user.click(gen);

    expect(generatePath).toHaveBeenCalledWith("nb-jac");
    // Fresh composed path (0%) → the primary action is "Start", linking into the player.
    const start = await screen.findByRole("link", { name: /Start →/ });
    expect(start).toHaveAttribute("href", "/learning/path/nb-jac");
    // ...and the Generate button is gone now that a path exists.
    expect(screen.queryByRole("button", { name: /Generate path/ })).not.toBeInTheDocument();
  });

  // 08-12 hunt #2 — the client resolves null ONLY for a 404 ("no path yet") and rethrows every
  // other failure, precisely so the card can tell "absent" from "broken". Collapsing both into
  // NoPathState puts an unconfirmed Generate button — a REPLACE — in front of a path that exists.
  it("does NOT offer Generate when the path fetch fails for a reason other than 404", async () => {
    path.mockRejectedValue(new Error("Network request failed"));
    renderCard();

    expect(await screen.findByText(/Couldn't load this topic's path/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate path/ })).not.toBeInTheDocument();
    expect(generatePath).not.toHaveBeenCalled();
  });

  // A 422 means the file IS on disk and unparseable — permanent and hand-fixable, not a blip. Saying
  // "just now" about it would be the same class of surface PR #182 fixed (a stated guarantee the
  // surface doesn't keep), so the copy has to distinguish it and carry the server's own detail.
  it("names a malformed path file instead of calling it a passing hiccup", async () => {
    const err = Object.assign(new Error("malformed path: step id 'x y' must be URL-safe"), {
      status: 422,
    });
    path.mockRejectedValue(err);
    renderCard();

    expect(await screen.findByText(/malformed and needs a fix/)).toBeInTheDocument();
    expect(screen.getByText(/must be URL-safe/)).toBeInTheDocument();
    expect(screen.queryByText(/just now/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate path/ })).not.toBeInTheDocument();
  });

  it("surfaces a calm error (no crash) when Generate comes back ok:false", async () => {
    path.mockResolvedValue(null);
    generatePath.mockResolvedValue({
      ok: false,
      path: null,
      errors: [],
      error: "The designer hiccuped — try again.",
    });
    const user = userEvent.setup();
    renderCard();

    await user.click(await screen.findByRole("button", { name: /Generate path/ }));

    expect(await screen.findByText("The designer hiccuped — try again.")).toBeInTheDocument();
    // Still on the Generate state — nothing was composed.
    expect(screen.getByRole("button", { name: /Generate path/ })).toBeInTheDocument();
  });

  it("shows the three honest axes + a Continue action for an in-progress path (no Generate)", async () => {
    path.mockResolvedValue(makePath({ completed_steps: 1, progress_pct: 33, mastery: null, confidence: 4 }));
    renderCard();

    // Coverage %, and the honest "— not tested" mastery while recall is unearned.
    expect(await screen.findByText("33%")).toBeInTheDocument();
    expect(screen.getByText(/not tested/)).toBeInTheDocument();
    // In-progress → Continue (not Start / Review), linking into the player; and no Generate button.
    expect(screen.getByRole("link", { name: /Continue →/ })).toHaveAttribute(
      "href",
      "/learning/path/nb-jac",
    );
    expect(screen.queryByRole("button", { name: /Generate path/ })).not.toBeInTheDocument();
  });

  it("cross-links to the course(s) built on this notebook", async () => {
    path.mockResolvedValue(null);
    renderCard(makeCard({ courses: [{ slug: "jlens-global-workspace", title: "Jacobian Lens" }] }));

    const chip = await screen.findByRole("link", { name: /Course: Jacobian Lens/ });
    expect(chip).toHaveAttribute("href", "/courses/jlens-global-workspace");
  });
});
