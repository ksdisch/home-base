import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PathResponse, PathStep, StudyProposal, StudyScheduleState } from "../api/types";
import PathPlayer from "./PathPlayer";

// M8 #15 — the slice-quality green gate for the outline+detail path player. Mock the client with
// ONLY the methods PathPlayer calls; a new api.X() in the effect would otherwise throw here.
const path = vi.fn();
const topic = vi.fn();
const completeStep = vi.fn();
const rateStepConfidence = vi.fn();
const gradeBridge = vi.fn();
// Study Scheduler surface (added below): PathPlayer now fetches api.schedule in an effect, so the
// mock MUST carry it (and the write methods) or every test above would throw on the missing method.
const schedule = vi.fn();
const setScheduleOptIn = vi.fn();
const proposeSchedule = vi.fn();
const confirmSchedule = vi.fn();
const removeSchedule = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    path: (id: string) => path(id),
    topic: (id: string) => topic(id),
    completeStep: (id: string, stepId: string, completed: boolean) =>
      completeStep(id, stepId, completed),
    rateStepConfidence: (id: string, stepId: string, rating: number) =>
      rateStepConfidence(id, stepId, rating),
    gradeBridge: (id: string, stepId: string, answer: string) => gradeBridge(id, stepId, answer),
    schedule: (id: string) => schedule(id),
    setScheduleOptIn: (id: string, body: unknown) => setScheduleOptIn(id, body),
    proposeSchedule: (id: string, body: unknown) => proposeSchedule(id, body),
    confirmSchedule: (id: string, blocks: unknown) => confirmSchedule(id, blocks),
    removeSchedule: (id: string, ids?: unknown) => removeSchedule(id, ids),
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

const scheduleState = (over: Partial<StudyScheduleState> = {}): StudyScheduleState => ({
  track_kind: "path",
  track_id: "nb-jac",
  enabled: false,
  session_minutes: 45,
  connected: false,
  calendar_id: null,
  blocks: [],
  ...over,
});

const makeBlock = (title: string, stepId: string) => ({
  start: "2026-07-22T18:00:00-05:00",
  end: "2026-07-22T18:45:00-05:00",
  minutes: 45,
  title,
  step_ids: [stepId],
  steps: [{ id: stepId, kind: "audio", title, minutes: 8 }],
});

const makeProposal = (...items: [string, string][]): StudyProposal => ({
  ok: true,
  connected: true,
  session_minutes: 45,
  blocks: items.map(([t, s]) => makeBlock(t, s)),
  unscheduled_step_ids: [],
  message: null,
});

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
  schedule.mockReset();
  setScheduleOptIn.mockReset();
  proposeSchedule.mockReset();
  confirmSchedule.mockReset();
  removeSchedule.mockReset();
  // topic() is a best-effort fetch for the NotebookLM link; give it something so the effect resolves.
  topic.mockResolvedValue({ notebooklm_url: "https://notebooklm.google.com/nb-jac" });
  // Default: the scheduler effect resolves to an unconnected, opted-out state so the tests above
  // (which don't care about scheduling) render cleanly.
  schedule.mockResolvedValue(scheduleState());
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

describe("PathPlayer — Study Scheduler surface", () => {
  it("shows the connect-your-calendar state when the calendar isn't wired", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ connected: false }));
    renderAt();
    expect(await screen.findByText(/Connect your Google Calendar/i)).toBeInTheDocument();
  });

  it("proposes a batch then writes it on confirm", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    proposeSchedule.mockResolvedValue(makeProposal(["Ep 1", "s1"]));
    confirmSchedule.mockResolvedValue(
      scheduleState({
        enabled: true,
        connected: true,
        blocks: [
          { id: 1, step_id: "s1", title: "Ep 1", start: "2026-07-22T18:00:00-05:00", end: "2026-07-22T18:45:00-05:00", event_id: "ev-1", calendar_id: "cal", status: "written" },
        ],
      }),
    );
    const user = userEvent.setup();
    renderAt();

    await user.click(await screen.findByRole("button", { name: /Propose times/i }));
    // Read-only: proposing writes nothing — just surfaces a reviewable set with one confirm. With an
    // empty note the deterministic control knobs are sent (preference stays null).
    expect(proposeSchedule).toHaveBeenCalledWith(
      "nb-jac",
      expect.objectContaining({ preference: null }),
    );
    const confirmBtn = await screen.findByRole("button", { name: /Add 1 block to my calendar/i });

    await user.click(confirmBtn);
    expect(confirmSchedule).toHaveBeenCalledWith("nb-jac", makeProposal(["Ep 1", "s1"]).blocks);
    expect(await screen.findByText(/On your calendar/i)).toBeInTheDocument();
  });

  it("excludes a dropped block from the confirmed batch", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    const p = makeProposal(["Ep 1", "s1"], ["Quiz", "s2"]);
    proposeSchedule.mockResolvedValue(p);
    confirmSchedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    const user = userEvent.setup();
    renderAt();

    await user.click(await screen.findByRole("button", { name: /Propose times/i }));
    await screen.findByRole("button", { name: /Add 2 blocks to my calendar/i });

    // Drop the first proposed block → only the second is written.
    await user.click(screen.getAllByRole("button", { name: "Drop" })[0]);
    await user.click(await screen.findByRole("button", { name: /Add 1 block to my calendar/i }));
    expect(confirmSchedule).toHaveBeenCalledWith("nb-jac", [p.blocks[1]]);
  });

  it("persists the opt-in when toggled", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: false, connected: true }));
    setScheduleOptIn.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    const user = userEvent.setup();
    renderAt();

    await user.click(await screen.findByLabelText(/Schedule on my calendar/i));
    expect(setScheduleOptIn).toHaveBeenCalledWith("nb-jac", { enabled: true });
  });

  it("removes a written block from the calendar", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(
      scheduleState({
        enabled: true,
        connected: true,
        blocks: [
          { id: 7, step_id: "s1", title: "Ep 1", start: "2026-07-22T18:00:00-05:00", end: "2026-07-22T18:45:00-05:00", event_id: "ev-7", calendar_id: "cal", status: "written" },
        ],
      }),
    );
    removeSchedule.mockResolvedValue(scheduleState({ enabled: true, connected: true, blocks: [] }));
    const user = userEvent.setup();
    renderAt();

    await user.click(await screen.findByRole("button", { name: "Remove" }));
    expect(removeSchedule).toHaveBeenCalledWith("nb-jac", [7]);
  });
});

describe("PathPlayer — Study Scheduler controls (v1)", () => {
  it("renders the day / time / session controls when enabled + connected", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    renderAt();

    // Day-of-week chips, a session-length chip, and the free-text note all present.
    expect(await screen.findByRole("button", { name: "Monday" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Saturday" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "45-minute sessions" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Scheduling preference/i)).toBeInTheDocument();
  });

  it("hydrates the controls from the persisted prefs", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(
      scheduleState({
        enabled: true,
        connected: true,
        days_of_week: [0, 1, 2, 3, 4],
        day_start_hour: 8,
        day_end_hour: 14,
        session_minutes: 30,
      }),
    );
    renderAt();

    // Weekdays pressed, weekend off; 30-min chip pressed; start hour reflects the saved 8am.
    expect(await screen.findByRole("button", { name: "Monday" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Saturday" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "30-minute sessions" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText(/Start hour/i)).toHaveValue("8");
  });

  it("sends the explicit control knobs on a deterministic propose (empty note)", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    proposeSchedule.mockResolvedValue(makeProposal(["Ep 1", "s1"]));
    const user = userEvent.setup();
    renderAt();

    // Turn off the weekend, then propose — the knobs (not a preference) drive the plan.
    await user.click(await screen.findByRole("button", { name: "Saturday" }));
    await user.click(screen.getByRole("button", { name: "Sunday" }));
    await user.click(screen.getByRole("button", { name: /Propose times/i }));

    expect(proposeSchedule).toHaveBeenCalledWith(
      "nb-jac",
      expect.objectContaining({ preference: null, days_of_week: [0, 1, 2, 3, 4] }),
    );
  });

  it("reflects the applied knobs from the response back into the controls", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    proposeSchedule.mockResolvedValue({
      ...makeProposal(["Ep 1", "s1"]),
      applied: {
        session_minutes: 30,
        day_start_hour: 8,
        day_end_hour: 14,
        days_of_week: [0, 1, 2, 3, 4],
        window_days: 14,
        max_blocks: 8,
        max_per_day: 1,
      },
    });
    const user = userEvent.setup();
    renderAt();

    await user.click(await screen.findByRole("button", { name: /Propose times/i }));
    // The controls snap to what the plan actually used.
    expect(await screen.findByRole("button", { name: "Saturday" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Monday" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "30-minute sessions" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText(/Start hour/i)).toHaveValue("8");
  });

  it("sends a free-text note (alongside the controls) and shows the reply", async () => {
    path.mockResolvedValue(makePath());
    schedule.mockResolvedValue(scheduleState({ enabled: true, connected: true }));
    proposeSchedule.mockResolvedValue({
      ...makeProposal(["Ep 1", "s1"]),
      message: "Weekdays before 2pm it is.",
    });
    const user = userEvent.setup();
    renderAt();

    await user.type(await screen.findByLabelText(/Scheduling preference/i), "weekdays before 2pm");
    // With a note present the action button becomes "Refine".
    await user.click(screen.getByRole("button", { name: /Refine/i }));

    // The note rides along with the current controls; the backend refines them (parser, then claude).
    expect(proposeSchedule).toHaveBeenCalledWith(
      "nb-jac",
      expect.objectContaining({ preference: "weekdays before 2pm" }),
    );
    expect(await screen.findByText(/Weekdays before 2pm it is\./)).toBeInTheDocument();
  });
});
