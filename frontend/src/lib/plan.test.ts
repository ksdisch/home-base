import { describe, expect, it } from "vitest";
import type { StudyPlanResponse, StudyPlanSegment } from "../api/types";
import { planSummary, quizPlayerPath, segmentSummary } from "./plan";

function seg(over: Partial<StudyPlanSegment> = {}): StudyPlanSegment {
  return {
    notebook_id: "nb",
    title: "A Topic",
    quiz_artifact_id: "qz",
    topic_url: "/topics/nb",
    item_count: 3,
    due_count: 2,
    minutes: 2,
    priority: 10,
    ...over,
  };
}

function plan(over: Partial<StudyPlanResponse> = {}): StudyPlanResponse {
  return {
    generated_at: "now",
    has_data: true,
    has_due: true,
    requested_minutes: 20,
    total_minutes: 12,
    total_items: 18,
    due_items: 10,
    segments: [seg({ notebook_id: "a" }), seg({ notebook_id: "b" })],
    ...over,
  };
}

describe("quizPlayerPath", () => {
  it("builds the encoded quiz-player route", () => {
    expect(quizPlayerPath("nb 1", "qz/2")).toBe("/topics/nb%201/quiz/qz%2F2");
  });
});

describe("planSummary", () => {
  it("summarizes minutes, questions and distinct topics", () => {
    expect(planSummary(plan())).toBe("~12 min · 18 questions across 2 topics");
  });

  it("handles an empty plan", () => {
    expect(planSummary(plan({ total_items: 0, segments: [] }))).toBe(
      "Nothing to review right now.",
    );
  });

  it("singularizes one question / one topic", () => {
    const p = plan({ total_items: 1, total_minutes: 1, segments: [seg()] });
    expect(planSummary(p)).toBe("~1 min · 1 question across 1 topic");
  });
});

describe("segmentSummary", () => {
  it("shows due count when something is due", () => {
    expect(segmentSummary(seg({ due_count: 2, item_count: 3, minutes: 2 }))).toBe(
      "2 due · 3 questions · ~2 min",
    );
  });

  it("says 'getting ahead' when nothing is due", () => {
    expect(segmentSummary(seg({ due_count: 0, item_count: 1, minutes: 1 }))).toBe(
      "getting ahead · 1 question · ~1 min",
    );
  });
});
