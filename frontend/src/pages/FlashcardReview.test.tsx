import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FlashcardReview from "./FlashcardReview";

// Mock the API client so the session runs deterministically without a backend.
const courseMaterial = vi.fn();
const courseFlashcardState = vi.fn();
const courseFlashcards = vi.fn();
const reviewFlashcard = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    courseMaterial: (s: string, p: string) => courseMaterial(s, p),
    courseFlashcardState: (s: string, p: string) => courseFlashcardState(s, p),
    courseFlashcards: (s: string) => courseFlashcards(s),
    reviewFlashcard: (s: string, p: string, b: unknown) => reviewFlashcard(s, p, b),
  },
}));

const SLUG = "learning-how-to-learn";
const PATH = "flashcards/m1l2.json";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/courses/${SLUG}/flashcards?path=${encodeURIComponent(PATH)}`]}>
      <Routes>
        <Route path="/courses/:slug/flashcards" element={<FlashcardReview />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  courseMaterial.mockReset();
  courseMaterial.mockResolvedValue({
    path: PATH,
    kind: "json",
    data: [
      { front: "What is encoding?", back: "Getting information **in**." },
      { front: "What is retrieval?", back: "Getting information back out." },
    ],
  });
  courseFlashcardState.mockReset();
  // Card 1 is due (reviewed before); card 0 has never been reviewed → session order: 1 then 0.
  courseFlashcardState.mockResolvedValue({
    slug: SLUG,
    path: PATH,
    generated_at: "now",
    cards: [
      { index: 0, tracked: false, due: false, reps: 0, lapses: 0, due_at: null, last_review_at: null },
      { index: 1, tracked: true, due: true, reps: 1, lapses: 0, due_at: "2026-06-01 00:00:00", last_review_at: null },
    ],
  });
  courseFlashcards.mockReset();
  courseFlashcards.mockResolvedValue({
    slug: SLUG,
    generated_at: "now",
    decks: [
      {
        path: PATH,
        lesson_id: "m1l2",
        module_id: "m1",
        title: "Core vocabulary",
        card_count: 2,
        tracked_cards: 1,
        due_cards: 1,
      },
    ],
  });
  reviewFlashcard.mockReset();
  reviewFlashcard.mockResolvedValue({
    index: 0,
    tracked: true,
    due: false,
    reps: 1,
    lapses: 0,
    due_at: "2026-06-10 00:00:00",
    last_review_at: "2026-06-09 00:00:00",
  });
});

describe("FlashcardReview — a graded session over one deck", () => {
  it("orders due cards first, grades through the deck, and ends on a summary", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    // Deck meta + the due-first ordering: the due card (index 1) leads the session.
    expect(await screen.findByText("Core vocabulary")).toBeInTheDocument();
    expect(await screen.findByText("What is retrieval?")).toBeInTheDocument();
    expect(screen.queryByText(/Getting information back out/)).not.toBeInTheDocument();

    // Reveal → the back appears with the grade buttons.
    await user.click(screen.getByRole("button", { name: /Reveal answer/i }));
    expect(screen.getByText(/Getting information back out/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Good$/ }));
    expect(reviewFlashcard).toHaveBeenCalledWith(SLUG, PATH, { index: 1, rating: "good" });

    // The new card (index 0) comes next, front-only again.
    expect(await screen.findByText("What is encoding?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Reveal answer/i }));
    await user.click(screen.getByRole("button", { name: /^Good$/ }));
    expect(reviewFlashcard).toHaveBeenCalledWith(SLUG, PATH, { index: 0, rating: "good" });

    // Both graded → the session summary.
    expect(await screen.findByText(/Session done/i)).toBeInTheDocument();
    expect(screen.getByText(/2 cards graded/i)).toBeInTheDocument();
  });

  it("re-queues an 'again' card so the session ends only after a pass", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    // Grade the due card "again" — it should come back at the end of the session.
    await screen.findByText("What is retrieval?");
    await user.click(screen.getByRole("button", { name: /Reveal answer/i }));
    await user.click(screen.getByRole("button", { name: /^Again$/ }));
    expect(reviewFlashcard).toHaveBeenCalledWith(SLUG, PATH, { index: 1, rating: "again" });

    // Next: the new card...
    await screen.findByText("What is encoding?");
    await user.click(screen.getByRole("button", { name: /Reveal answer/i }));
    await user.click(screen.getByRole("button", { name: /^Good$/ }));

    // ...then the "again" card returns before the session can end.
    expect(await screen.findByText("What is retrieval?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Reveal answer/i }));
    await user.click(screen.getByRole("button", { name: /^Good$/ }));

    expect(await screen.findByText(/Session done/i)).toBeInTheDocument();
    expect(screen.getByText(/3 cards graded/i)).toBeInTheDocument();
  });

  it("shows a calm error when the material isn't a deck", async () => {
    courseMaterial.mockResolvedValue({ path: PATH, kind: "text", text: "not a deck" });
    renderPage();
    expect(await screen.findByText(/Couldn't start this review/i)).toBeInTheDocument();
  });
});
