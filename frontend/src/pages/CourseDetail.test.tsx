import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  CourseDetail as Detail,
  CourseFlashcardsResponse,
  CourseQuizzesResponse,
} from "../api/types";
import CourseDetail from "./CourseDetail";

// Mock the API client so the page renders deterministically without a backend.
const course = vi.fn();
const courseQuizzes = vi.fn();
const courseFlashcards = vi.fn();
const courseMaterial = vi.fn();
const courseNext = vi.fn();
const assessProject = vi.fn();
const editLessonObjectives = vi.fn();
const reorderCourse = vi.fn();
const regenerateMaterial = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    course: (s: string) => course(s),
    courseQuizzes: (s: string) => courseQuizzes(s),
    courseFlashcards: (s: string) => courseFlashcards(s),
    courseMaterial: (s: string, p: string) => courseMaterial(s, p),
    courseNext: (s: string) => courseNext(s),
    assessProject: (s: string, p: string, b: unknown) => assessProject(s, p, b),
    editLessonObjectives: (s: string, l: string, b: unknown) => editLessonObjectives(s, l, b),
    reorderCourse: (s: string, b: unknown) => reorderCourse(s, b),
    regenerateMaterial: (s: string, l: string, b: unknown) => regenerateMaterial(s, l, b),
    courseExportUrl: (s: string) => `/api/courses/${s}/export`,
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
  editable: true,
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
  courseFlashcards.mockReset();
  courseFlashcards.mockResolvedValue({ slug: SLUG, generated_at: "now", decks: [] });
  courseMaterial.mockReset();
  courseMaterial.mockResolvedValue({ path: "", kind: "json", data: [] });
  courseNext.mockReset();
  courseNext.mockResolvedValue({ slug: SLUG, generated_at: "now", all_done: false, items: [] });
  assessProject.mockReset();
  editLessonObjectives.mockReset();
  reorderCourse.mockReset();
  regenerateMaterial.mockReset();
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

const DECK_COURSE: Detail = {
  ...COURSE,
  material_counts: { flashcards: 1 },
  modules: [
    {
      id: "m1",
      title: "How Memory Works",
      summary: "",
      lessons: [
        {
          id: "m1l2",
          title: "Encoding vs. Retrieval",
          objectives: [],
          estimated_minutes: 10,
          completed: false,
          materials: [
            { type: "flashcards", title: "Core vocabulary", path: "flashcards/m1l2.json", count: 2 },
          ],
        },
      ],
    },
  ],
};

describe("CourseDetail — flashcard decks (M2 remainder)", () => {
  it("shows a Review deck CTA with the due chip above the browsable grid", async () => {
    course.mockResolvedValue(DECK_COURSE);
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });
    courseFlashcards.mockResolvedValue({
      slug: SLUG,
      generated_at: "now",
      decks: [
        {
          path: "flashcards/m1l2.json",
          lesson_id: "m1l2",
          module_id: "m1",
          title: "Core vocabulary",
          card_count: 2,
          tracked_cards: 2,
          due_cards: 2,
        },
      ],
    } satisfies CourseFlashcardsResponse);
    courseMaterial.mockResolvedValue({
      path: "flashcards/m1l2.json",
      kind: "json",
      data: [
        { front: "What is encoding?", back: "Getting information in." },
        { front: "What is retrieval?", back: "Getting information back out." },
      ],
    });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/courses/${SLUG}`]}>
        <Routes>
          <Route path="/courses/:slug" element={<CourseDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /Encoding vs. Retrieval/i }));

    const link = await screen.findByRole("link", { name: /Review deck/i });
    expect(link).toHaveAttribute(
      "href",
      `/courses/${SLUG}/flashcards?path=flashcards%2Fm1l2.json`,
    );
    expect(screen.getByText(/2 due for review/i)).toBeInTheDocument();
    expect(screen.getByText("2 cards")).toBeInTheDocument();
    // The browsable flip-card grid still renders below the CTA.
    expect(await screen.findByText("What is encoding?")).toBeInTheDocument();
  });

  it("surfaces due flashcards in the next-up panel with a Review cards CTA", async () => {
    course.mockResolvedValue(DECK_COURSE);
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });
    courseNext.mockResolvedValue({
      slug: SLUG,
      generated_at: "now",
      all_done: false,
      items: [
        {
          kind: "flashcards_review",
          title: "Core vocabulary",
          reason: "2 cards due for review",
          module_id: "m1",
          lesson_id: "m1l2",
          path: "flashcards/m1l2.json",
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={[`/courses/${SLUG}`]}>
        <Routes>
          <Route path="/courses/:slug" element={<CourseDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    const cta = await screen.findByRole("link", { name: /Review cards/i });
    expect(cta).toHaveAttribute(
      "href",
      `/courses/${SLUG}/flashcards?path=flashcards%2Fm1l2.json`,
    );
    expect(screen.getByText(/2 cards due for review/i)).toBeInTheDocument();
  });
});

const NB_ID = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4";

function nbCourse(material: object): Detail {
  return {
    ...COURSE,
    material_counts: { notebooklm: 1 },
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
            materials: [material as Detail["modules"][0]["lessons"][0]["materials"][0]],
          },
        ],
      },
    ],
  };
}

describe("CourseDetail — notebooklm cross-link (M4)", () => {
  it("renders a linked notebook as an Open-notebook card with counts", async () => {
    course.mockResolvedValue(
      nbCourse({
        type: "notebooklm",
        title: "Audio deep-dive",
        artifact: "audio",
        notebook_id: NB_ID,
        note: "Six-episode season.",
        notebook: {
          notebook_id: NB_ID,
          found: true,
          title: "Jlens Workspace",
          topic_url: `/topics/${NB_ID}`,
          notebooklm_url: `https://notebooklm.google.com/notebook/${NB_ID}`,
          counts: { audio: 6, study_guides: 1, quizzes: 1, total: 8 },
        },
      }),
    );
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/courses/${SLUG}`]}>
        <Routes>
          <Route path="/courses/:slug" element={<CourseDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /Putting It Together/i }));

    const link = await screen.findByRole("link", { name: /Open notebook/i });
    expect(link).toHaveAttribute("href", `/topics/${NB_ID}`);
    expect(screen.getByText("Jlens Workspace")).toBeInTheDocument();
    expect(screen.getByText(/6 episodes/)).toBeInTheDocument();
    expect(screen.getByText(/1 guide/)).toBeInTheDocument();
    expect(screen.getByText(/Six-episode season/)).toBeInTheDocument();
  });

  it("degrades calmly when the linked notebook isn't in this machine's catalog", async () => {
    course.mockResolvedValue(
      nbCourse({
        type: "notebooklm",
        title: "Audio deep-dive",
        notebook_id: NB_ID,
        note: "Generate locally.",
        notebook: { notebook_id: NB_ID, found: false, counts: {} },
      }),
    );
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/courses/${SLUG}`]}>
        <Routes>
          <Route path="/courses/:slug" element={<CourseDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /Putting It Together/i }));
    expect(await screen.findByText(/isn't in this machine's catalog/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open notebook/i })).not.toBeInTheDocument();
  });

  it("keeps the plain note when no notebook is linked yet", async () => {
    course.mockResolvedValue(
      nbCourse({
        type: "notebooklm",
        title: "Optional deep-dive",
        note: "Link a notebook later.",
      }),
    );
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/courses/${SLUG}`]}>
        <Routes>
          <Route path="/courses/:slug" element={<CourseDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /Putting It Together/i }));
    expect(await screen.findByText(/Link a notebook later/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open notebook/i })).not.toBeInTheDocument();
  });
});

const TWO_LESSON_COURSE: Detail = {
  ...COURSE,
  lesson_count: 2,
  modules: [
    {
      id: "m2",
      title: "Evidence-Based Techniques",
      summary: "",
      lessons: [
        {
          id: "m2l1",
          title: "First steps",
          objectives: [],
          estimated_minutes: 5,
          completed: false,
          materials: [],
        },
        ...COURSE.modules[0].lessons,
      ],
    },
  ],
};

describe("CourseDetail — authoring loop (M5)", () => {
  it("hides Edit course for a read-only course but always offers Export", async () => {
    course.mockResolvedValue({ ...COURSE, editable: false });
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });

    renderPage();

    const exportLink = await screen.findByRole("link", { name: /Export/i });
    expect(exportLink).toHaveAttribute("href", `/api/courses/${SLUG}/export`);
    expect(screen.queryByRole("button", { name: /Edit course/i })).not.toBeInTheDocument();
  });

  it("saves edited objectives through the writer", async () => {
    course.mockResolvedValue(COURSE);
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });
    editLessonObjectives.mockResolvedValue({ ok: true, errors: [], warnings: [] });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Edit course/i }));
    await user.click(await screen.findByRole("button", { name: /Edit objectives/i }));
    const box = screen.getByRole("textbox", { name: /Objectives for Putting It Together/i });
    await user.clear(box);
    await user.type(box, "Apply retrieval practice{enter}Compare methods");
    await user.click(screen.getByRole("button", { name: /Save objectives/i }));

    expect(editLessonObjectives).toHaveBeenCalledWith(SLUG, "m2l2", {
      objectives: ["Apply retrieval practice", "Compare methods"],
    });
  });

  it("reorders lessons by sending the complete permutation", async () => {
    course.mockResolvedValue(TWO_LESSON_COURSE);
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });
    reorderCourse.mockResolvedValue({ ok: true, errors: [], warnings: [] });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Edit course/i }));
    await user.click(screen.getByRole("button", { name: /Move lesson First steps down/i }));

    expect(reorderCourse).toHaveBeenCalledWith(SLUG, {
      modules: [{ id: "m2", lessons: ["m2l2", "m2l1"] }],
    });
  });

  it("regenerates a deck after warning that stats reset", async () => {
    course.mockResolvedValue(DECK_COURSE);
    courseQuizzes.mockResolvedValue({ slug: SLUG, generated_at: "now", quizzes: [] });
    regenerateMaterial.mockResolvedValue({
      ok: true,
      path: "flashcards/m1l2.json",
      rolled_back: false,
      errors: [],
      warnings: [],
      count: 3,
      duration_ms: 60000,
      total_cost_usd: 0.05,
    });

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Edit course/i }));
    // Anchor to the expand toggle — in edit mode the Move-lesson arrows also carry the title.
    await user.click(await screen.findByRole("button", { name: /^Encoding vs\. Retrieval/ }));
    await user.click(
      await screen.findByRole("button", { name: /Regenerate this flashcards/i }),
    );
    expect(screen.getByText(/resets review\/attempt stats/i)).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: /Guidance for regenerating Core vocabulary/i }),
      "harder cards",
    );
    await user.click(screen.getByRole("button", { name: /^Regenerate$/ }));

    expect(regenerateMaterial).toHaveBeenCalledWith(SLUG, "m1l2", {
      path: "flashcards/m1l2.json",
      guidance: "harder cards",
    });
  });
});
