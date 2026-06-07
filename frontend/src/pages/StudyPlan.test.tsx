import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyPlanResponse } from "../api/types";
import StudyPlan from "./StudyPlan";

// Mock the API client so the page renders deterministically without a backend.
const studyPlan = vi.fn();
vi.mock("../api/client", () => ({
  api: { studyPlan: (m: number) => studyPlan(m) },
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

beforeEach(() => {
  studyPlan.mockReset();
});

describe("StudyPlan page", () => {
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
    studyPlan.mockResolvedValue({
      generated_at: "now",
      has_data: false,
      has_due: false,
      requested_minutes: 20,
      total_minutes: 0,
      total_items: 0,
      due_items: 0,
      segments: [],
    } satisfies StudyPlanResponse);
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
});
