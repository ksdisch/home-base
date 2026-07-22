import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PathsResponse, StudyPlanResponse } from "../api/types";
import StudyPlan from "./StudyPlan";

// Mock the API client so the page renders deterministically without a backend.
const studyPlan = vi.fn();
const paths = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    studyPlan: (m: number) => studyPlan(m),
    paths: () => paths(),
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <StudyPlan />
    </MemoryRouter>,
  );
}

const DUE_PLAN: StudyPlanResponse = {
  generated_at: "now",
  has_data: true,
  has_due: true,
  requested_minutes: 20,
  total_minutes: 6,
  total_items: 9,
  due_items: 5,
  segments: [
    {
      notebook_id: "nb-a",
      title: "Stoicism",
      quiz_artifact_id: "qz-a",
      topic_url: "/topics/nb-a",
      item_count: 5,
      due_count: 3,
      minutes: 3,
      priority: 20,
    },
  ],
};

const EMPTY_PLAN: StudyPlanResponse = {
  generated_at: "now",
  has_data: false,
  has_due: false,
  requested_minutes: 20,
  total_minutes: 0,
  total_items: 0,
  due_items: 0,
  segments: [],
};

beforeEach(() => {
  studyPlan.mockReset();
  paths.mockReset();
  // Continue lane empty by default so the Review-lane tests below are unaffected.
  paths.mockResolvedValue({ generated_at: "now", items: [] } satisfies PathsResponse);
});

describe("StudyPlan page — Review lane", () => {
  it("renders due segments with a review link", async () => {
    studyPlan.mockResolvedValue(DUE_PLAN);
    renderPage();

    expect(await screen.findByText("Stoicism")).toBeInTheDocument();
    expect(screen.getByText("🔁 3 due")).toBeInTheDocument();
    // The segment links to the quiz player.
    const link = screen.getByRole("link", { name: /Review/i });
    expect(link).toHaveAttribute("href", "/topics/nb-a/quiz/qz-a");
  });

  it("shows the empty state when no questions are scheduled", async () => {
    studyPlan.mockResolvedValue(EMPTY_PLAN);
    renderPage();

    expect(await screen.findByText(/No questions to schedule yet/i)).toBeInTheDocument();
  });

  it("requests a new plan when the minute budget changes", async () => {
    studyPlan.mockResolvedValue(DUE_PLAN);
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Stoicism");
    expect(studyPlan).toHaveBeenCalledWith(20); // default budget

    await user.click(screen.getByRole("button", { name: "45m" }));
    await waitFor(() => expect(studyPlan).toHaveBeenCalledWith(45));
  });

  it("clears a stale error when a later plan request succeeds", async () => {
    studyPlan.mockRejectedValueOnce(new Error("plan failed")); // first budget (20m) errors
    studyPlan.mockResolvedValue(DUE_PLAN); // a later budget succeeds
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText(/plan failed/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "45m" }));
    expect(await screen.findByText("Stoicism")).toBeInTheDocument();
    // The stale error from the failed 20m request must not linger over the new plan.
    expect(screen.queryByText(/plan failed/i)).not.toBeInTheDocument();
  });
});

describe("StudyPlan page — Continue lane", () => {
  const IN_PROGRESS: PathsResponse = {
    generated_at: "now",
    items: [
      {
        notebook_id: "nb-jac",
        title: "Jacobian Lens Path",
        topic: "interpretability",
        step_count: 9,
        completed_steps: 2,
        progress_pct: 22,
        next_step: {
          id: "ep3",
          kind: "audio",
          title: "Surgery on Thoughts",
          focus: null,
          body: null,
          artifact_id: "a3",
          artifact_type: "audio",
          estimated_minutes: 8,
          completed: false,
          confidence: null,
        },
      },
    ],
  };

  it("shows an in-progress path with its resume point, linking into the player", async () => {
    studyPlan.mockResolvedValue(EMPTY_PLAN); // Review empty — Continue still carries the page
    paths.mockResolvedValue(IN_PROGRESS);
    renderPage();

    expect(await screen.findByText("Jacobian Lens Path")).toBeInTheDocument();
    expect(screen.getByText("2 of 9 · 22%")).toBeInTheDocument(); // coverage line
    expect(screen.getByText(/Surgery on Thoughts/)).toBeInTheDocument(); // next step
    const link = screen.getByRole("link", { name: /Continue/i });
    expect(link).toHaveAttribute("href", "/learning/path/nb-jac");
  });

  it("drops fully-completed paths (no next_step) from the lane", async () => {
    studyPlan.mockResolvedValue(EMPTY_PLAN);
    paths.mockResolvedValue({
      generated_at: "now",
      items: [
        {
          notebook_id: "nb-done",
          title: "Finished Path",
          topic: "x",
          step_count: 4,
          completed_steps: 4,
          progress_pct: 100,
          next_step: null,
        },
      ],
    } satisfies PathsResponse);
    renderPage();

    // Review empty-state renders (so the page settled), but the completed path is not offered.
    expect(await screen.findByText(/No questions to schedule yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Finished Path")).not.toBeInTheDocument();
  });
});
