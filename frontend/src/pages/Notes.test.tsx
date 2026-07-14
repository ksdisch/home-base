import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Notes from "./Notes";

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
    render(<Notes />);

    expect(await screen.findByText("chiefs note")).toBeInTheDocument();
    expect(screen.getByText("ai note")).toBeInTheDocument();
    // The topic title shows on the note row AND as a filter option — both are wanted.
    expect(screen.getAllByText(/Kansas City Chiefs/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/OpenAI lifts caps/)).toBeInTheDocument();
  });

  it("filters per topic via the select", async () => {
    briefNotes.mockResolvedValue(NOTES);
    render(<Notes />);
    await screen.findByText("chiefs note");

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ai-llms" } });
    expect(screen.getByText("ai note")).toBeInTheDocument();
    expect(screen.queryByText("chiefs note")).not.toBeInTheDocument();
  });

  it("deletes a note and drops it from the list", async () => {
    briefNotes.mockResolvedValue(NOTES);
    deleteBriefNote.mockResolvedValue({ ok: true });
    render(<Notes />);
    await screen.findByText("chiefs note");

    fireEvent.click(screen.getByLabelText("Delete note 2"));
    await waitFor(() => expect(screen.queryByText("chiefs note")).not.toBeInTheDocument());
    expect(deleteBriefNote).toHaveBeenCalledWith(2);
    expect(screen.getByText("ai note")).toBeInTheDocument();
  });

  it("shows the empty state when there are no notes", async () => {
    briefNotes.mockResolvedValue({ generated_at: "now", notes: [] });
    render(<Notes />);

    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument();
  });
});
