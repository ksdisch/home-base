// The ONE place the API base URL lives. Everything goes through "/api" (Vite proxies it to
// the FastAPI backend in dev). To point elsewhere, set VITE_API_BASE at build time.
import type {
  BriefChatRequest,
  BriefChatResponse,
  BriefNote,
  BriefNoteCreate,
  BriefNoteDeleteResponse,
  BriefNotesResponse,
  BriefResponse,
  BriefVisitResponse,
  CatalogResponse,
  CourseDetail,
  CourseMaterialResponse,
  CourseQuizzesResponse,
  CoursesResponse,
  CustomTopic,
  CustomTopicCreate,
  CustomTopicsResponse,
  CustomTopicUpdate,
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

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
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
  brief: () => get<BriefResponse>("/brief"),
  // M4: the served day's narrated MP3 — a plain URL for an <audio> element, not a fetch.
  briefAudioUrl: () => `${API_BASE}/brief/audio`,
  // The habit metric — one row per Today-page load; fire-and-forget from the page.
  logBriefVisit: () => post<BriefVisitResponse>("/brief/visit"),
  // M2 inline notes on brief items — browse (optionally per topic), add, delete.
  briefNotes: (topic?: string) =>
    get<BriefNotesResponse>(`/brief/notes${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`),
  addBriefNote: (body: BriefNoteCreate) => post<BriefNote>("/brief/notes", body),
  deleteBriefNote: (id: number) => del<BriefNoteDeleteResponse>(`/brief/notes/${id}`),
  // M5: one grounded follow-up answer about a served item (subscription lane, no web) —
  // slow by web standards (a real model call, ~5–20s), so callers show a thinking state.
  briefChat: (body: BriefChatRequest) => post<BriefChatResponse>("/brief/chat", body),
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
};
