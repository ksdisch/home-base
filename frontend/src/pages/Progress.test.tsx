import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  PathsResponse,
  ProgressResponse,
  ReflectionsResponse,
  ReviewResponse,
} from "../api/types";
import Progress from "./Progress";

// Mock the API client so the page renders deterministically without a backend.
const progress = vi.fn();
const review = vi.fn();
const reflections = vi.fn();
const paths = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    progress: () => progress(),
    review: () => review(),
    reflections: () => reflections(),
    paths: () => paths(),
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
  paths.mockReset();
  // Paths empty by default so the existing per-endpoint tests are unaffected (no band, no rows).
  paths.mockResolvedValue({ generated_at: "now", items: [] } satisfies PathsResponse);
});

const EMPTY_REFLECTIONS: ReflectionsResponse = {
  generated_at: "now",
  has_data: false,
  count: 0,
  avg_grasp: null,
  items: [],
};

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

  // Bug #11: the allSettled degrade was real, but BOTH body branches gated on `data` — set
  // only when api.progress() fulfils. So the one rejection the page couldn't survive was the
  // progress endpoint's own: header over a blank page, no banner, while review, reflections
  // and paths had all loaded fine and sat unreachable behind the gate.
  it("keeps review, reflections and paths reachable when only the progress endpoint fails", async () => {
    progress.mockRejectedValue(new Error("progress endpoint flaked"));
    review.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      due_count: 1,
      items: [
        {
          notebook_id: "nb1",
          title: "Spaced Repetition 101",
          topic_url: "/topics/nb1",
          mastery: 0.6,
          decayed: 0.4,
          due: true,
          priority: 1,
          days_since_review: 12,
          total_misses: 3,
          shaky_questions: 2,
          last_review_at: "2026-06-26",
          reason: "3 shaky questions",
        },
      ],
    } satisfies ReviewResponse);
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
    paths.mockResolvedValue({
      generated_at: "now",
      items: [
        {
          notebook_id: "nb-jac",
          title: "Jacobian Lens Path",
          topic: "interpretability",
          step_count: 10,
          completed_steps: 6,
          progress_pct: 60,
          next_step: null,
          confidence: 3.2,
        },
      ],
    } satisfies PathsResponse);

    renderPage();

    // Everything that loaded still renders — the page degrades, it does not blank.
    expect(await screen.findByRole("heading", { name: "Reflections" })).toBeInTheDocument();
    expect(screen.getByText("This one finally clicked.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Learning paths" })).toBeInTheDocument();
    expect(screen.getByText("Jacobian Lens Path")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Review next" })).toBeInTheDocument();

    // And the failure is admitted rather than rendered as an empty page.
    expect(screen.getByText(/Couldn't load your progress/)).toBeInTheDocument();
    // The empty state would be a lie here — there IS data, one endpoint just didn't answer.
    expect(screen.queryByText(/Take a quiz from any topic/)).not.toBeInTheDocument();
  });
});

describe("Progress — the three honest axes (M8 #13)", () => {
  // Option B (docs/ideas/learning-paths.md decision 8): Recall is the one real TREND line (attempt
  // scores over time); Coverage + Confidence are honest CURRENT readouts across the learner's paths.
  it("renders the recall trend + honest coverage/confidence readouts with a path and attempts", async () => {
    progress.mockResolvedValue({
      generated_at: "now",
      has_data: true,
      summary: {
        ...EMPTY_SUMMARY,
        attempts_total: 3,
        avg_pct: 72,
        topics_practiced: 1,
        last_activity: "2026-07-20",
      },
      topics: [
        {
          notebook_id: "nb-jac",
          title: "Jacobian Lens",
          topic_url: "/topics/nb-jac",
          attempts: 3,
          last_pct: 80,
          best_pct: 90,
          avg_pct: 72,
          last_practiced: "2026-07-20",
          points: [
            { finished_at: "2026-07-18", pct: 60 },
            { finished_at: "2026-07-19", pct: 76 },
            { finished_at: "2026-07-20", pct: 80 },
          ],
        },
      ],
      shaky: [],
      activity: [{ day: "2026-07-20", count: 3 }],
    } satisfies ProgressResponse);
    review.mockResolvedValue(EMPTY_REVIEW);
    reflections.mockResolvedValue(EMPTY_REFLECTIONS);
    paths.mockResolvedValue({
      generated_at: "now",
      items: [
        {
          notebook_id: "nb-jac",
          title: "Jacobian Lens Path",
          topic: "interpretability",
          step_count: 10,
          completed_steps: 6,
          progress_pct: 60,
          next_step: null,
          confidence: 3.2,
        },
      ],
    } satisfies PathsResponse);

    renderPage();

    // The three-axis headline band.
    expect(await screen.findByRole("heading", { name: "Your three axes" })).toBeInTheDocument();
    // Recall = avg score (the real trend axis); Coverage = 6/10 across paths; Confidence = mean rating.
    // Each value appears in the band AND its per-path detail row, so assert at least one occurrence.
    expect(screen.getAllByText("72%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("60%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("3.2/5").length).toBeGreaterThan(0);
    // The per-path coverage/confidence detail row links into the path player.
    expect(screen.getByRole("heading", { name: "Learning paths" })).toBeInTheDocument();
    expect(screen.getByText("Jacobian Lens Path")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open/i })).toHaveAttribute(
      "href",
      "/learning/path/nb-jac",
    );
  });

  it("keeps the three-axis band hidden when there are no paths and no attempts", async () => {
    progress.mockResolvedValue({
      generated_at: "now",
      has_data: false, // no graded quiz attempts
      summary: { ...EMPTY_SUMMARY, last_activity: "2026-06-26" },
      topics: [],
      shaky: [],
      activity: [{ day: "2026-06-26", count: 1 }], // activity-only (e.g. a listen)
    } satisfies ProgressResponse);
    review.mockResolvedValue(EMPTY_REVIEW);
    reflections.mockResolvedValue(EMPTY_REFLECTIONS);
    // paths default = empty (no bundled example in the mock)

    renderPage();

    // Activity still surfaces (so the page settled)...
    expect(await screen.findByRole("heading", { name: "Recent activity" })).toBeInTheDocument();
    // ...but with no path and no quiz, the three-axis band + per-path rows are not shown (all cells
    // would be em-dashes) — Option B's honest cold start.
    expect(screen.queryByRole("heading", { name: "Your three axes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Learning paths" })).not.toBeInTheDocument();
  });
});
