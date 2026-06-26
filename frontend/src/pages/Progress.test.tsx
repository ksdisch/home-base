import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ProgressResponse,
  ReflectionsResponse,
  ReviewResponse,
} from "../api/types";
import Progress from "./Progress";

// Mock the API client so the page renders deterministically without a backend.
const progress = vi.fn();
const review = vi.fn();
const reflections = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    progress: () => progress(),
    review: () => review(),
    reflections: () => reflections(),
  },
}));

const EMPTY_SUMMARY: ProgressResponse["summary"] = {
  attempts_total: 0,
  topics_practiced: 0,
  avg_pct: 0,
  current_streak: 0,
  longest_streak: 0,
  last_activity: null,
};

const EMPTY_REVIEW: ReviewResponse = {
  generated_at: "now",
  has_data: false,
  due_count: 0,
  items: [],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <Progress />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  progress.mockReset();
  review.mockReset();
  reflections.mockReset();
});

describe("Progress — section visibility is per-endpoint, not gated on quiz attempts", () => {
  // The bug: reflections and activity are written WITHOUT a graded quiz attempt, but the whole
  // results block hung off the /progress has_data flag — so a reflections-only / listen-only user
  // saw only the "No attempts yet" banner and lost their journal + activity history entirely.
  it("surfaces the reflections journal and activity strip for a reflections-only user (zero quiz attempts)", async () => {
    progress.mockResolvedValue({
      generated_at: "now",
      has_data: false, // no graded quiz attempts
      summary: { ...EMPTY_SUMMARY, last_activity: "2026-06-26" },
      topics: [],
      shaky: [],
      activity: [{ day: "2026-06-26", count: 2 }], // reflection/listen activity exists
    } satisfies ProgressResponse);
    review.mockResolvedValue(EMPTY_REVIEW);
    reflections.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      count: 1,
      avg_grasp: 4,
      items: [
        {
          id: 1,
          notebook_id: "nb1",
          title: "Spaced Repetition 101",
          episode_artifact_id: null,
          body: "This one finally clicked.",
          grasp_rating: 4,
          created_at: "2026-06-26",
          topic_url: null,
        },
      ],
    } satisfies ReflectionsResponse);

    renderPage();

    // The reflections journal must surface even with zero quiz attempts.
    expect(await screen.findByRole("heading", { name: "Reflections" })).toBeInTheDocument();
    expect(screen.getByText("Spaced Repetition 101")).toBeInTheDocument();
    // The activity strip carries the reflection/listen days, so it surfaces too.
    expect(screen.getByRole("heading", { name: "Recent activity" })).toBeInTheDocument();
    // And the "No attempts yet" empty state must NOT be shown.
    expect(screen.queryByText(/Take a quiz from any topic/)).not.toBeInTheDocument();
  });

  it("shows the 'No attempts yet' empty state only when nothing at all has data", async () => {
    progress.mockResolvedValue({
      generated_at: "now",
      has_data: false,
      summary: EMPTY_SUMMARY,
      topics: [],
      shaky: [],
      activity: [],
    } satisfies ProgressResponse);
    review.mockResolvedValue(EMPTY_REVIEW);
    reflections.mockResolvedValue({
      generated_at: "now",
      has_data: false,
      count: 0,
      avg_grasp: null,
      items: [],
    } satisfies ReflectionsResponse);

    renderPage();

    expect(await screen.findByText(/Take a quiz from any topic/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Reflections" })).not.toBeInTheDocument();
  });
});

describe("Progress — one flaky endpoint must not blank the whole dashboard", () => {
  // The bug: the three endpoints were fused with Promise.all, so a single rejection replaced the
  // entire page with the error banner — even though the other two loaded fine.
  it("still renders the sections that loaded when one endpoint (review) fails", async () => {
    progress.mockResolvedValue({
      generated_at: "now",
      has_data: false,
      summary: { ...EMPTY_SUMMARY, last_activity: "2026-06-26" },
      topics: [],
      shaky: [],
      activity: [{ day: "2026-06-26", count: 2 }],
    } satisfies ProgressResponse);
    review.mockRejectedValue(new Error("review endpoint flaked"));
    reflections.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      count: 1,
      avg_grasp: 4,
      items: [
        {
          id: 1,
          notebook_id: "nb1",
          title: "Spaced Repetition 101",
          episode_artifact_id: null,
          body: "This one finally clicked.",
          grasp_rating: 4,
          created_at: "2026-06-26",
          topic_url: null,
        },
      ],
    } satisfies ReflectionsResponse);

    renderPage();

    // The reflections + activity that DID load still render...
    expect(await screen.findByRole("heading", { name: "Reflections" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent activity" })).toBeInTheDocument();
    // ...and a single flaky call does NOT replace the whole page with the error banner.
    expect(screen.queryByText(/Couldn't load your progress/)).not.toBeInTheDocument();
  });
});
