import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FlashcardSessionResponse } from "../api/types";
import FlashcardPlayer from "./FlashcardPlayer";

// Mock the API client so the player runs deterministically without a backend.
const flashcardSession = vi.fn();
const gradeFlashcard = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    flashcardSession: (s: string, p: string) => flashcardSession(s, p),
    gradeFlashcard: (s: string, b: unknown) => gradeFlashcard(s, b),
  },
}));

const SLUG = "learning-how-to-learn";
const PATH = "flashcards/m1l2.json";

const card = (key: string, front: string, back: string, due = true) => ({
  card_key: key,
  front,
  back,
  new: due,
  due,
  reps: due ? 0 : 1,
  due_at: due ? null : "2099-01-01 00:00:00",
});

const SESSION: FlashcardSessionResponse = {
  slug: SLUG,
  path: PATH,
  ok: true,
  title: "Core terms",
  total: 3,
  due_count: 2,
  cards: [
    card("k1", "Encoding", "Getting information *in*."),
    card("k2", "Retrieval", "Getting information back out."),
    card("k3", "Spacing", "Already scheduled ahead.", false),
  ],
};

const GRADED = {
  card_key: "k1",
  grade: "good",
  ease: 2.5,
  interval_days: 1,
  reps: 1,
  lapses: 0,
  last_review_at: "now",
  due_at: "tomorrow",
};

function renderPlayer() {
  return render(
    <MemoryRouter initialEntries={[`/courses/${SLUG}/flashcards?path=${encodeURIComponent(PATH)}`]}>
      <Routes>
        <Route path="/courses/:slug/flashcards" element={<FlashcardPlayer />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  flashcardSession.mockReset();
  gradeFlashcard.mockReset();
});

describe("FlashcardPlayer — review loop (M3)", () => {
  it("queues only due cards, grades flip-by-flip, and ends in a summary", async () => {
    flashcardSession.mockResolvedValue(SESSION);
    gradeFlashcard.mockResolvedValue(GRADED);
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPlayer();

    // Two of three cards are due → the queue is 2 long; the back stays hidden until flipped.
    expect(await screen.findByText("Card 1 of 2")).toBeInTheDocument();
    expect(screen.getByText("Encoding")).toBeInTheDocument();
    expect(screen.queryByText(/Getting information/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Good" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Show answer/i }));
    expect(screen.getByText(/Getting information/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Good" }));
    expect(gradeFlashcard).toHaveBeenCalledWith(SLUG, {
      path: PATH,
      card_key: "k1",
      grade: "good",
    });

    // Advanced to the second due card (the not-due "Spacing" card never enters the queue).
    expect(await screen.findByText("Card 2 of 2")).toBeInTheDocument();
    expect(screen.getByText("Retrieval")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Show answer/i }));
    await user.click(screen.getByRole("button", { name: "Again" }));

    // Session summary: both grades tallied, with the "again" card called out.
    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.getByText(/reviewed/i)).toBeInTheDocument();
    expect(screen.getByText(/1 again/i)).toBeInTheDocument();
    expect(screen.getByText(/1 good/i)).toBeInTheDocument();
    expect(screen.getByText(/comes back tomorrow/i)).toBeInTheDocument();
  });

  it("offers 'review anyway' when nothing is due", async () => {
    flashcardSession.mockResolvedValue({
      ...SESSION,
      due_count: 0,
      cards: SESSION.cards.map((c) => ({ ...c, new: false, due: false, reps: 1 })),
    });
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPlayer();

    expect(await screen.findByText(/Nothing due/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Review anyway/i }));
    // The optional pass runs the FULL deck.
    expect(await screen.findByText("Card 1 of 3")).toBeInTheDocument();
  });

  it("degrades calmly when the deck can't load", async () => {
    flashcardSession.mockResolvedValue({
      slug: SLUG,
      path: PATH,
      ok: false,
      title: null,
      total: 0,
      due_count: 0,
      cards: [],
      error: "Couldn't load this deck.",
    } satisfies FlashcardSessionResponse);
    renderPlayer();

    expect(await screen.findByText(/Couldn't start this review/i)).toBeInTheDocument();
    expect(screen.getByText(/Couldn't load this deck/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });
});
