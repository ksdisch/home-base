// The ONE place the API base URL lives. Everything goes through "/api" (Vite proxies it to
// the FastAPI backend in dev). To point elsewhere, set VITE_API_BASE at build time.
import type {
  BridgeGradeResponse,
  BriefChatRequest,
  BriefChatResponse,
  BriefHabitResponse,
  BriefNote,
  BriefNoteCreate,
  BriefNoteDeleteResponse,
  BriefNotesResponse,
  BriefOvernightProposal,
  BriefResponse,
  BriefSweepResponse,
  BriefVisitResponse,
  CatalogResponse,
  CourseAssessment,
  CourseAssessmentRequest,
  CourseDetail,
  CourseEditResponse,
  CourseFlashcardsResponse,
  CourseFlashcardStateResponse,
  CourseMaterialResponse,
  CourseNextResponse,
  CourseObjectivesUpdate,
  CourseOrderUpdate,
  CourseQuizzesResponse,
  CourseRegenRequest,
  CourseRegenResponse,
  CoursesResponse,
  CustomTopic,
  CustomTopicCreate,
  CustomTopicsResponse,
  CustomTopicUpdate,
  FlashcardCardState,
  FlashcardReviewRequest,
  HealthResponse,
  LessonCompleteResponse,
  NewsCategoriesResponse,
  NewsCategoryResponse,
  NewsEventCreate,
  NewsEventResponse,
  NewsForYouResponse,
  NewsSuggestionActionRequest,
  NewsSuggestionAddResponse,
  NewsSuggestionDismissResponse,
  PathGenerateResponse,
  PathResponse,
  PathsResponse,
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

async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
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
  // M6: same GET /api/brief, but also surfaces whether the service worker replayed it from
  // the offline cache (X-Served-From-Cache) — frontend-only metadata, never in types.ts.
  briefWithMeta: async (): Promise<{ brief: BriefResponse; fromCache: boolean }> => {
    const res = await fetch(`${API_BASE}/brief`, { headers: { Accept: "application/json" } });
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
    return {
      brief: (await res.json()) as BriefResponse,
      fromCache: res.headers.get("X-Served-From-Cache") === "1",
    };
  },
  // M4: the served day's narrated MP3 — a plain URL for an <audio> element, not a fetch.
  briefAudioUrl: () => `${API_BASE}/brief/audio`,
  // QU1: an archived morning by date — live-only (the SW deliberately stands aside for
  // ?date= so an archive visit can't clobber the cached last morning).
  briefByDate: (date: string) => get<BriefResponse>(`/brief?date=${encodeURIComponent(date)}`),
  // FR2: kick the Mac's sweep pipeline from the stale banner — lock-guarded server-side,
  // so a double tap (or a tap during the 06:00 run) is an honest no-op.
  sweepBrief: () => post<BriefSweepResponse>("/brief/sweep"),
  // The habit metric — one row per Today-page load; fire-and-forget from the page.
  logBriefVisit: () => post<BriefVisitResponse>("/brief/visit"),
  briefHabit: () => get<BriefHabitResponse>("/brief/habit"),
  // M2 inline notes on brief items — browse (optionally per topic), add, delete.
  briefNotes: (topic?: string) =>
    get<BriefNotesResponse>(`/brief/notes${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`),
  addBriefNote: (body: BriefNoteCreate) => post<BriefNote>("/brief/notes", body),
  deleteBriefNote: (id: number) => del<BriefNoteDeleteResponse>(`/brief/notes/${id}`),
  // M5: one grounded follow-up answer about a served item (subscription lane, no web) —
  // slow by web standards (a real model call, ~5–20s), so callers show a thinking state.
  briefChat: (body: BriefChatRequest) => post<BriefChatResponse>("/brief/chat", body),
  // Overnight v0: resolve one draft-only proposal — single-shot on the server (a second
  // verb on the same id is a 409, surfaced inline by the strip).
  approveOvernight: (id: string) =>
    post<BriefOvernightProposal>(`/brief/overnight/${encodeURIComponent(id)}/approve`),
  discardOvernight: (id: string) =>
    post<BriefOvernightProposal>(`/brief/overnight/${encodeURIComponent(id)}/discard`),
  // M7 news mode: the category roster + one category's RSS-backed articles.
  newsCategories: () => get<NewsCategoriesResponse>("/news/categories"),
  newsCategory: (slug: string) =>
    get<NewsCategoryResponse>(`/news/${encodeURIComponent(slug)}`),
  // M7 Phase 2: For-You signals — fire-and-forget from the page (callers swallow errors).
  logNewsEvent: (body: NewsEventCreate) => post<NewsEventResponse>("/news/events", body),
  // M7 Phase 3: the personalized feed (cold start returns Top stories, learning=true).
  newsForYou: () => get<NewsForYouResponse>("/news/foryou"),
  // M7 Phase 4: the topic scout's actions — add to the morning-brief roster, or never again.
  addNewsTopic: (body: NewsSuggestionActionRequest) =>
    post<NewsSuggestionAddResponse>("/news/suggestions/add", body),
  dismissNewsSuggestion: (body: NewsSuggestionActionRequest) =>
    post<NewsSuggestionDismissResponse>("/news/suggestions/dismiss", body),
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
  // -- learning paths (M8) — the AI study-designer over a NotebookLM topic. GET merges the three
  // axes (coverage/recall/confidence); each write returns the refreshed PathResponse. A 404 means
  // no path has been composed for this topic yet (the Learning card's "Generate" state), so path()
  // degrades that one status to null instead of throwing; other errors still propagate.
  path: async (notebookId: string): Promise<PathResponse | null> => {
    try {
      return await get<PathResponse>(`/paths/${encodeURIComponent(notebookId)}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
  completeStep: (notebookId: string, stepId: string, completed: boolean) =>
    post<PathResponse>(
      `/paths/${encodeURIComponent(notebookId)}/steps/${encodeURIComponent(stepId)}/complete`,
      { completed },
    ),
  rateStepConfidence: (notebookId: string, stepId: string, rating: number) =>
    post<PathResponse>(
      `/paths/${encodeURIComponent(notebookId)}/steps/${encodeURIComponent(stepId)}/confidence`,
      { rating },
    ),
  // The one LLM step: a formative grade on the M5 grounded lane. Slow by web standards (~5–20s), so
  // callers show a thinking state; never a 500 — a claude hiccup returns ok=false + a calm error.
  gradeBridge: (notebookId: string, stepId: string, answer: string) =>
    post<BridgeGradeResponse>(
      `/paths/${encodeURIComponent(notebookId)}/steps/${encodeURIComponent(stepId)}/bridge`,
      { answer },
    ),
  // M8 the on-demand Designer: compose a path over a topic's real artifacts on the claude lane —
  // slow by web standards (~1–3 min, a real authoring call), so callers show a busy state. Never a
  // 500: a hiccup, unparseable output, or a fabricated artifact id all return ok:false (nothing written).
  generatePath: (notebookId: string) =>
    post<PathGenerateResponse>(`/paths/${encodeURIComponent(notebookId)}/generate`),
  // M8 #12: every composed path + its resume point (coverage + next step) — the Plan Continue lane.
  // Non-empty day one via the bundled example; independent of the review minute budget.
  paths: () => get<PathsResponse>("/paths"),
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
  // M2 remainder: flashcard decks + per-card review state. A self-graded card advances the same
  // per-course SM-2 scheduler the quizzes use (again/hard/good).
  courseFlashcards: (slug: string) =>
    get<CourseFlashcardsResponse>(`/courses/${encodeURIComponent(slug)}/flashcards`),
  courseFlashcardState: (slug: string, path: string) =>
    get<CourseFlashcardStateResponse>(
      `/courses/${encodeURIComponent(slug)}/flashcards/state?path=${encodeURIComponent(path)}`,
    ),
  reviewFlashcard: (slug: string, path: string, body: FlashcardReviewRequest) =>
    post<FlashcardCardState>(
      `/courses/${encodeURIComponent(slug)}/flashcards/review?path=${encodeURIComponent(path)}`,
      body,
    ),
  // Course quizzes live on disk; prepare stashes a keyed copy server-side and returns the same
  // answer-key-free player view as a NotebookLM quiz. Graded via the shared gradeQuiz().
  prepareCourseQuiz: (slug: string, path: string) =>
    post<QuizPrepareResponse>(
      `/courses/${encodeURIComponent(slug)}/quiz/prepare?path=${encodeURIComponent(path)}`,
    ),
  // M3: the course's ranked "what to do next" (due reviews → continue → practice → project).
  courseNext: (slug: string) =>
    get<CourseNextResponse>(`/courses/${encodeURIComponent(slug)}/next`),
  // M3: save a rubric self-assessment for a project/capstone material.
  assessProject: (slug: string, path: string, body: CourseAssessmentRequest) =>
    post<CourseAssessment>(
      `/courses/${encodeURIComponent(slug)}/assess?path=${encodeURIComponent(path)}`,
      body,
    ),
  // M5 authoring loop: structural edits ride the backend's transactional writer — ok:false
  // means validation bounced and the course rolled back untouched.
  editLessonObjectives: (slug: string, lessonId: string, body: CourseObjectivesUpdate) =>
    put<CourseEditResponse>(
      `/courses/${encodeURIComponent(slug)}/lessons/${encodeURIComponent(lessonId)}/objectives`,
      body,
    ),
  reorderCourse: (slug: string, body: CourseOrderUpdate) =>
    put<CourseEditResponse>(`/courses/${encodeURIComponent(slug)}/order`, body),
  // M5: regenerate ONE material on the headless claude lane — slow by web standards (a real
  // authoring call, ~1–3 min), so callers show a busy state and sequence multiple materials.
  regenerateMaterial: (slug: string, lessonId: string, body: CourseRegenRequest) =>
    post<CourseRegenResponse>(
      `/courses/${encodeURIComponent(slug)}/lessons/${encodeURIComponent(lessonId)}/regenerate`,
      body,
    ),
  // M5: the whole course dir as a zip — a plain URL for an <a download>, not a fetch.
  courseExportUrl: (slug: string) => `${API_BASE}/courses/${encodeURIComponent(slug)}/export`,
};
