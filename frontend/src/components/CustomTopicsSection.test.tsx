import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CustomTopicsSection } from "./CustomTopicsSection";

// Mock the API client so the section renders deterministically without a backend.
const customTopics = vi.fn();
const addCustomTopic = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    customTopics: () => customTopics(),
    addCustomTopic: (v: unknown) => addCustomTopic(v),
  },
}));

beforeEach(() => {
  customTopics.mockReset();
  addCustomTopic.mockReset();
});

describe("CustomTopicsSection", () => {
  it("clears a stale error once a later reload succeeds", async () => {
    customTopics.mockRejectedValueOnce(new Error("topics failed")); // initial load fails
    customTopics.mockResolvedValue({ topics: [] }); // the reload after adding succeeds
    addCustomTopic.mockResolvedValue({});
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();

    render(<CustomTopicsSection />);

    // Initial load failed → error banner.
    expect(await screen.findByText(/topics failed/i)).toBeInTheDocument();

    // Adding a topic triggers a successful reload (load()), which must clear the stale error.
    await user.click(screen.getByRole("button", { name: /Add custom topic/i }));
    await user.type(screen.getByPlaceholderText(/A book, a YouTube series/i), "Dune");
    await user.click(screen.getByRole("button", { name: "Add topic" }));

    await screen.findByText(/Track a book/i); // empty-state for the now-loaded (empty) topics
    expect(screen.queryByText(/topics failed/i)).not.toBeInTheDocument();
  });
});
