import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Notes from "./Notes";

// QU1: the date snapshot is now a Link into the archived morning, so the page needs a
// router in the harness.
function renderNotes() {
  return render(
    <MemoryRouter>
      <Notes />
    </MemoryRouter>,
  );
}

const briefNotes = vi.fn();
const deleteBriefNote = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    briefNotes: (topic?: string) => briefNotes(topic),
    deleteBriefNote: (id: number) => deleteBriefNote(id),
  },
}));

const NOTES = {
  generated_at: "now",
  notes: [
    {
      id: 2,
      item_id: "b",
      topic_slug: "chiefs",
      topic_title: "Kansas City Chiefs",
      brief_date: "2026-07-14",
      item_headline: "Kohou on the roster bubble",
      body: "chiefs note",
      created_at: "t2",
    },
    {
      id: 1,
      item_id: "a",
      topic_slug: "ai-llms",
      topic_title: "AI / LLMs",
      brief_date: "2026-07-14",
      item_headline: "OpenAI lifts caps",
      body: "ai note",
      created_at: "t1",
    },
  ],
};

beforeEach(() => {
  briefNotes.mockReset();
  deleteBriefNote.mockReset();
});

describe("Notes (browse page)", () => {
  it("renders every note with its topic + item context", async () => {
    briefNotes.mockResolvedValue(NOTES);
    renderNotes();

    expect(await screen.findByText("chiefs note")).toBeInTheDocument();
    expect(screen.getByText("ai note")).toBeInTheDocument();
    // The topic title shows on the note row AND as a filter option — both are wanted.
    expect(screen.getAllByText(/Kansas City Chiefs/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/OpenAI lifts caps/)).toBeInTheDocument();
  });

  it("filters per topic via the select", async () => {
    briefNotes.mockResolvedValue(NOTES);
    renderNotes();
    await screen.findByText("chiefs note");

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ai-llms" } });
    expect(screen.getByText("ai note")).toBeInTheDocument();
    expect(screen.queryByText("chiefs note")).not.toBeInTheDocument();
  });

  it("deletes a note optimistically and commits after the undo window (FR10)", async () => {
    briefNotes.mockResolvedValue(NOTES);
    deleteBriefNote.mockResolvedValue({ ok: true });
    renderNotes();
    await screen.findByText("chiefs note");

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByLabelText("Delete note 2"));
      expect(screen.queryByText("chiefs note")).not.toBeInTheDocument(); // vanishes now…
      expect(deleteBriefNote).not.toHaveBeenCalled(); // …but the mutation holds
      act(() => {
        vi.runAllTimers();
      });
      expect(deleteBriefNote).toHaveBeenCalledWith(2);
    } finally {
      vi.useRealTimers();
    }
    expect(screen.getByText("ai note")).toBeInTheDocument();
  });

  it("undo within the window restores the note and never calls the API (FR10)", async () => {
    briefNotes.mockResolvedValue(NOTES);
    deleteBriefNote.mockResolvedValue({ ok: true });
    renderNotes();
    await screen.findByText("chiefs note");

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByLabelText("Delete note 2"));
      fireEvent.click(screen.getByRole("button", { name: "Undo" }));
      expect(screen.getByText("chiefs note")).toBeInTheDocument(); // back, same list
      act(() => {
        vi.runAllTimers();
      });
      expect(deleteBriefNote).not.toHaveBeenCalled(); // no API mutation at all
    } finally {
      vi.useRealTimers();
    }
  });

  it("deleting the filtered topic's last note falls back to All instead of stranding (#14)", async () => {
    briefNotes.mockResolvedValue(NOTES);
    deleteBriefNote.mockResolvedValue({ ok: true });
    renderNotes();
    await screen.findByText("chiefs note");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "chiefs" } });
    expect(screen.queryByText("ai note")).not.toBeInTheDocument();

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByLabelText("Delete note 2"));
      act(() => {
        vi.runAllTimers();
      });
    } finally {
      vi.useRealTimers();
    }

    expect(await screen.findByText("ai note")).toBeInTheDocument(); // filter fell back
    expect(screen.queryByText(/No notes yet/)).not.toBeInTheDocument(); // no false empty state
  });

  it("a failed delete reports itself accurately, not as a load failure (#17)", async () => {
    briefNotes.mockResolvedValue(NOTES);
    deleteBriefNote.mockRejectedValue(new Error("hub unreachable"));
    renderNotes();
    await screen.findByText("chiefs note");

    vi.useFakeTimers();
    try {
      fireEvent.click(screen.getByLabelText("Delete note 2"));
      act(() => {
        vi.runAllTimers();
      });
    } finally {
      vi.useRealTimers();
    }

    expect(await screen.findByText("Couldn't delete the note")).toBeInTheDocument();
    expect(screen.getByText(/hub unreachable/)).toBeInTheDocument();
    expect(screen.queryByText("Couldn't load notes")).not.toBeInTheDocument(); // honest title
    expect(screen.getByText("ai note")).toBeInTheDocument(); // the loaded list still renders
    expect(screen.getByText("chiefs note")).toBeInTheDocument(); // failed delete restored
  });

  it("shows the empty state when there are no notes", async () => {
    briefNotes.mockResolvedValue({ generated_at: "now", notes: [] });
    renderNotes();

    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();
  });

  // QU1: the snapshot stops being an inert caption — the date links straight into that
  // archived morning at /brief/:date.

  it("the note's date snapshot links into its archived morning (QU1)", async () => {
    briefNotes.mockResolvedValue(NOTES);
    renderNotes();
    await screen.findByText("chiefs note");

    const links = screen.getAllByRole("link", { name: "2026-07-14" });
    expect(links.length).toBeGreaterThanOrEqual(2); // one per note row
    expect(links[0]).toHaveAttribute("href", "/brief/2026-07-14");
  });
});
