// The ONE place the API base URL lives. Everything goes through "/api" (Vite proxies it to
// the FastAPI backend in dev). To point elsewhere, set VITE_API_BASE at build time.
import type {
  CatalogResponse,
  CourseDetail,
  CourseFlashcardsResponse,
  CourseMaterialResponse,
  CourseQuizzesResponse,
  CoursesResponse,
  CustomTopic,
  CustomTopicCreate,
  CustomTopicsResponse,
  CustomTopicUpdate,
  FlashcardGradeRequest,
  FlashcardGradeResponse,
  FlashcardSessionResponse,
  HealthResponse,
  LessonCompleteResponse,
  ProgressResponse,
  QuizGradeRequest,
  QuizGradeResponse,
  QuizPrepareResponse,
  ReflectionsResponse,
  ReviewResponse,
  StudyGuideResponse,
  StudyPlanResponse,
  TopicDetail,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<HealthResponse>("/health"),
  catalog: () => get<CatalogResponse>("/catalog"),
  progress: () => get<ProgressResponse>("/progress"),
  review: () => get<ReviewResponse>("/review"),
  studyPlan: (minutes: number) => get<StudyPlanResponse>(`/study-plan?minutes=${minutes}`),
  reflections: (notebookId?: string) =>
    get<ReflectionsResponse>(
      `/reflections${notebookId ? `?notebook_id=${encodeURIComponent(notebookId)}` : ""}`,
    ),
  topic: (id: string, live = false) =>
    get<TopicDetail>(`/topics/${encodeURIComponent(id)}${live ? "?live=true" : ""}`),
  setEpisodeListened: async (
    notebookId: string,
    artifactId: string,
    listened: boolean,
  ): Promise<boolean> => {
    const res = await fetch(
      `${API_BASE}/topics/${encodeURIComponent(notebookId)}/episodes/${encodeURIComponent(
        artifactId,
      )}/listened`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listened }),
      },
    );
    if (!res.ok) throw new ApiError(res.status, "Could not save progress");
    const body = await res.json();
    return Boolean(body.listened);
  },
  studyGuide: (notebookId: string, artifactId: string) =>
    get<StudyGuideResponse>(
      `/topics/${encodeURIComponent(notebookId)}/study-guides/${encodeURIComponent(artifactId)}`,
    ),
  prepareQuiz: (notebookId: string, quizId: string) =>
    post<QuizPrepareResponse>(
      `/topics/${encodeURIComponent(notebookId)}/quizzes/${encodeURIComponent(quizId)}/prepare`,
    ),
  gradeQuiz: (body: QuizGradeRequest) => post<QuizGradeResponse>("/quiz/grade", body),
  customTopics: () => get<CustomTopicsResponse>("/custom-topics"),
  addCustomTopic: (body: CustomTopicCreate) => post<CustomTopic>("/custom-topics", body),
  updateCustomTopic: (id: number, body: CustomTopicUpdate) =>
    patch<CustomTopic>(`/custom-topics/${id}`, body),
  courses: () => get<CoursesResponse>("/courses"),
  course: (slug: string) => get<CourseDetail>(`/courses/${encodeURIComponent(slug)}`),
  courseMaterial: (slug: string, path: string) =>
    get<CourseMaterialResponse>(
      `/courses/${encodeURIComponent(slug)}/materials?path=${encodeURIComponent(path)}`,
    ),
  setLessonComplete: (slug: string, lessonId: string, completed: boolean) =>
    post<LessonCompleteResponse>(
      `/courses/${encodeURIComponent(slug)}/lessons/${encodeURIComponent(lessonId)}/complete`,
      { completed },
    ),
  courseQuizzes: (slug: string) =>
    get<CourseQuizzesResponse>(`/courses/${encodeURIComponent(slug)}/quizzes`),
  // Course quizzes live on disk; prepare stashes a keyed copy server-side and returns the same
  // answer-key-free player view as a NotebookLM quiz. Graded via the shared gradeQuiz().
  prepareCourseQuiz: (slug: string, path: string) =>
    post<QuizPrepareResponse>(
      `/courses/${encodeURIComponent(slug)}/quiz/prepare?path=${encodeURIComponent(path)}`,
    ),
  // Flashcards are self-graded, so the session fetch is a pure read (nothing stashed
  // server-side) and each card's grade is POSTed as it happens — abandoning a session loses
  // nothing.
  courseFlashcards: (slug: string) =>
    get<CourseFlashcardsResponse>(`/courses/${encodeURIComponent(slug)}/flashcards`),
  flashcardSession: (slug: string, path: string) =>
    get<FlashcardSessionResponse>(
      `/courses/${encodeURIComponent(slug)}/flashcards/session?path=${encodeURIComponent(path)}`,
    ),
  gradeFlashcard: (slug: string, body: FlashcardGradeRequest) =>
    post<FlashcardGradeResponse>(
      `/courses/${encodeURIComponent(slug)}/flashcards/grade`,
      body,
    ),
};
