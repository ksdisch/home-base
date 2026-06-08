import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CourseDetail as Detail, CourseQuizzesResponse } from "../api/types";
import CourseDetail from "./CourseDetail";

// Mock the API client so the page renders deterministically without a backend.
const course = vi.fn();
const courseQuizzes = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    course: (s: string) => course(s),
    courseQuizzes: (s: string) => courseQuizzes(s),
  },
}));

const SLUG = "learning-how-to-learn";

const COURSE: Detail = {
  slug: SLUG,
  title: "Learning How to Learn",
  topic: "",
  level: "beginner",
  summary: "",
  prerequisites: [],
  estimated_hours: null,
  created_at: "",
  generator: "",
  module_count: 1,
  lesson_count: 1,
  material_counts: { quiz: 1 },
  completed_lessons: 0,
  progress_pct: 0,
  modules: [
    {
      id: "m2",
      title: "Evidence-Based Techniques",
      summary: "",
      lessons: [
        {
          id: "m2l2",
          title: "Putting It Together",
          objectives: [],
          estimated_minutes: 10,
          completed: false,
          materials: [
            { type: "quiz", title: "Module 2 check", path: "quizzes/m2l2.json", count: 5 },
          ],
        },
      ],
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/courses/${SLUG}`]}>
      <Routes>
        <Route path="/courses/:slug" element={<CourseDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  course.mockReset();
  courseQuizzes.mockReset();
});

describe("CourseDetail — course quizzes (M2)", () => {
  it("launches a taken quiz into the player and shows last score + due-for-review", async () => {
    course.mockResolvedValue(COURSE);
    courseQuizzes.mockResolvedValue({
      slug: SLUG,
      generated_at: "now",
      quizzes: [
        {
          path: "quizzes/m2l2.json",
          lesson_id: "m2l2",
          module_id: "m2",
          title: "Module 2 check",
          question_count: 5,
          attempts: 1,
          last_score: 4,
          last_total: 5,
          last_pct: 80,
          last_attempt_at: "2026-06-08",
          tracked_questions: 5,
          due_questions: 2,
        },
      ],
    } satisfies CourseQuizzesResponse);

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    // Expand the lesson to reveal its materials.
    const toggle = await screen.findByRole("button", { name: /Putting It Together/i });
    await user.click(toggle);

    // A prior attempt → "Retake quiz", linking to the answer-key-free course player with the
    // material path in the query string.
    const link = await screen.findByRole("link", { name: /Retake quiz/i });
    expect(link).toHaveAttribute("href", `/courses/${SLUG}/quiz?path=quizzes%2Fm2l2.json`);

    expect(screen.getByText("Last: 4/5")).toBeInTheDocument();
    expect(screen.getByText(/2 due for review/i)).toBeInTheDocument();
  });

  it("shows 'Take quiz' for an unattempted quiz", async () => {
    course.mockResolvedValue(COURSE);
    courseQuizzes.mockResolvedValue({
      slug: SLUG,
      generated_at: "now",
      quizzes: [
        {
          path: "quizzes/m2l2.json",
          lesson_id: "m2l2",
          module_id: "m2",
          title: "Module 2 check",
          question_count: 5,
          attempts: 0,
          last_score: null,
          last_total: null,
          last_pct: null,
          last_attempt_at: null,
          tracked_questions: 0,
          due_questions: 0,
        },
      ],
    } satisfies CourseQuizzesResponse);

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Putting It Together/i }));
    expect(await screen.findByRole("link", { name: /Take quiz/i })).toBeInTheDocument();
    expect(screen.queryByText(/due for review/i)).not.toBeInTheDocument();
  });
});
