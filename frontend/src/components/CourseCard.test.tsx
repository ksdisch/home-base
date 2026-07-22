import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { CourseSummary } from "../api/types";
import { CourseCard } from "./CourseCard";

function makeCourse(over: Partial<CourseSummary> = {}): CourseSummary {
  return {
    slug: "jlens-global-workspace",
    title: "Global Workspace in LLMs",
    topic: "interpretability",
    level: "intermediate",
    summary: "",
    prerequisites: [],
    estimated_hours: 2,
    created_at: "",
    generator: "",
    module_count: 3,
    lesson_count: 4,
    material_counts: {},
    completed_lessons: 0,
    progress_pct: 0,
    editable: false,
    ...over,
  };
}

function renderCard(course: CourseSummary) {
  return render(
    <MemoryRouter>
      <CourseCard course={course} />
    </MemoryRouter>,
  );
}

describe("CourseCard — source-notebook cross-link", () => {
  it("links to the source notebook when the course references one", () => {
    renderCard(
      makeCourse({
        notebook: {
          notebook_id: "nb-jac",
          found: true,
          title: "Jacobian Lens Paper",
          topic_url: "/topics/nb-jac",
          notebooklm_url: null,
          counts: {},
        },
      }),
    );

    const chip = screen.getByRole("link", { name: /Source notebook: Jacobian Lens Paper/ });
    expect(chip).toHaveAttribute("href", "/topics/nb-jac");
  });

  it("shows no source-notebook chip when there is no linked notebook", () => {
    renderCard(makeCourse({ notebook: null }));
    expect(screen.queryByText(/Source notebook/)).not.toBeInTheDocument();
  });

  it("hides the chip when the linked notebook isn't on this machine (found=false)", () => {
    renderCard(
      makeCourse({
        notebook: { notebook_id: "nb-ghost", found: false, counts: {} },
      }),
    );
    expect(screen.queryByText(/Source notebook/)).not.toBeInTheDocument();
  });
});
