import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PathResponse, PathStep } from "../api/types";
import PathPlayer from "./PathPlayer";

// M8 #15 — the slice-quality green gate for the outline+detail path player. Mock the client with
// ONLY the methods PathPlayer calls; a new api.X() in the effect would otherwise throw here.
const path = vi.fn();
const topic = vi.fn();
const completeStep = vi.fn();
const rateStepConfidence = vi.fn();
const gradeBridge = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    path: (id: string) => path(id),
    topic: (id: string) => topic(id),
    completeStep: (id: string, stepId: string, completed: boolean) =>
      completeStep(id, stepId, completed),
    rateStepConfidence: (id: string, stepId: string, rating: number) =>
      rateStepConfidence(id, stepId, rating),
    gradeBridge: (id: string, stepId: string, answer: string) => gradeBridge(id, stepId, answer),
  },
}));

const STEPS: PathStep[] = [
  { id: "s1", kind: "audio", title: "Listen: overview", focus: null, body: null, artifact_id: "a1", artifact_type: "audio", estimated_minutes: 8, completed: true, confidence: 4 },
  { id: "s2", kind: "quiz", title: "Quiz yourself", focus: null, body: null, artifact_id: "q1", artifact_type: "quiz", estimated_minutes: 5, completed: false, confidence: null },
  { id: "s3", kind: "bridge", title: "Bridge check", focus: null, body: "Explain the Jacobian lens.", artifact_id: null, artifact_type: null, estimated_minutes: 3, completed: false, confidence: null },
];

function makePath(over: Partial<PathResponse> = {}): PathResponse {
  return {
    notebook_id: "nb-jac",
    title: "Jacobian Lens Path",
    topic: "interpretability",
    generated_at: "now",
    generator: "fixture",
    steps: STEPS,
    step_count: 3,
    completed_steps: 1,
    progress_pct: 33,
    mastery: null,
    confidence: 4,
    ...over,
  };
}

function renderAt(id = "nb-jac") {
  return render(
    <MemoryRouter initialEntries={[`/learning/path/${id}`]}>
      <Routes>
        <Route path="/learning/path/:id" element={<PathPlayer />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  path.mockReset();
  topic.mockReset();
  completeStep.mockReset();
  rateStepConfidence.mockReset();
  gradeBridge.mockReset();
  // topic() is a best-effort fetch for the NotebookLM link; give it something so the effect resolves.
  topic.mockResolvedValue({ notebooklm_url: "https://notebooklm.google.com/nb-jac" });
});

describe("PathPlayer — outline + detail (M8 #15)", () => {
  it("renders the rail, auto-selects the first incomplete step, and shows the three honest axes", async () => {
    path.mockResolvedValue(makePath());
    renderAt();

    // Header + the whole path as a left-rail table of contents.
    expect(await screen.findByRole("heading", { name: "Jacobian Lens Path" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Listen: overview/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bridge check/ })).toBeInTheDocument();

    // The first INCOMPLETE step (s2, the quiz) is the active detail, deep-linking into the quiz player.
    expect(screen.getByRole("heading", { name: "Quiz yourself" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Take the quiz/ })).toHaveAttribute(
      "href",
      "/topics/nb-jac/quiz/q1",
    );

    // The three axes, honest: coverage 1/3, mastery "— not tested yet" while null.
    expect(screen.getByText("1/3 · 33%")).toBeInTheDocument();
    expect(screen.getByText(/not tested yet/)).toBeInTheDocument();
  });

  it("marks a step done via api.completeStep and reflects the refreshed coverage", async () => {
    path.mockResolvedValue(makePath());
    completeStep.mockResolvedValue(makePath({ completed_steps: 2, progress_pct: 67 }));
    const user = userEvent.setup();
    renderAt();

    await screen.findByRole("heading", { name: "Quiz yourself" });
    await user.click(screen.getByLabelText(/Mark this step done/));

    expect(completeStep).toHaveBeenCalledWith("nb-jac", "s2", true);
    expect(await screen.findByText("2/3 · 67%")).toBeInTheDocument();
  });

  it("rates the active step's confidence via api.rateStepConfidence", async () => {
    path.mockResolvedValue(makePath());
    rateStepConfidence.mockResolvedValue(makePath({ confidence: 3 }));
    const user = userEvent.setup();
    renderAt();

    await screen.findByRole("heading", { name: "Quiz yourself" });
    await user.click(screen.getByRole("button", { name: "Rate your confidence 3 of 5" }));

    expect(rateStepConfidence).toHaveBeenCalledWith("nb-jac", "s2", 3);
  });

  it("grades the bridge-check via api.gradeBridge and shows the feedback", async () => {
    path.mockResolvedValue(makePath());
    gradeBridge.mockResolvedValue({
      ok: true,
      feedback: "Nice — you covered the key idea.",
      error: null,
      path: makePath({ completed_steps: 2, progress_pct: 67 }),
    });
    const user = userEvent.setup();
    renderAt();

    await screen.findByRole("heading", { name: "Quiz yourself" });
    // Jump to the one generated glue step (the bridge-check) from the rail.
    await user.click(screen.getByRole("button", { name: /Bridge check/ }));
    const box = await screen.findByLabelText(/Your bridge-check answer/);
    await user.type(box, "It reads a model as local linear maps.");
    await user.click(screen.getByRole("button", { name: /Submit answer/ }));

    expect(gradeBridge).toHaveBeenCalledWith("nb-jac", "s3", "It reads a model as local linear maps.");
    expect(await screen.findByText(/Nice — you covered the key idea\./)).toBeInTheDocument();
  });

  it("shows the no-path banner when the topic has no composed path", async () => {
    path.mockResolvedValue(null);
    renderAt();
    expect(await screen.findByText(/No learning path yet/)).toBeInTheDocument();
  });
});
