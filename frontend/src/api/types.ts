// Mirrors backend/app/models.py — the backend↔frontend contract.

export interface AuthState {
  ok: boolean;
  message?: string | null;
}

export interface Episode {
  n?: number | null;
  title: string;
  artifact_id: string;
  fmt?: string | null;
  length?: string | null;
  status?: string | null;
  listened: boolean;
  source: string;
}

export interface ArtifactRef {
  n?: number | null;
  title: string;
  artifact_id: string;
  type: string;
  status?: string | null;
  source: string;
}

export interface QuizRef extends ArtifactRef {
  takeable: boolean;
}

export interface NotebookCard {
  notebook_id: string;
  alias: string;
  title: string;
  group: string;
  group_label: string;
  template?: string | null;
  tags: string[];
  archived: boolean;
  notebooklm_url: string;
  topic_url: string;
  counts: Record<string, number>;
  progress_pct?: number | null;
  mastery?: number | null;
  due_for_review: boolean;
  last_touched?: string | null;
}

export interface Group {
  key: string;
  label: string;
  notebooks: NotebookCard[];
}

export interface CatalogResponse {
  generated_at: string;
  groups: Group[];
  auth: AuthState;
  warnings: string[];
  notebooklm_root: string;
}

export interface TopicDetail {
  notebook_id: string;
  alias: string;
  title: string;
  group: string;
  group_label: string;
  template?: string | null;
  tags: string[];
  archived: boolean;
  merged_into?: string | null;
  source_count?: number | null;
  notebooklm_url: string;
  episodes: Episode[];
  standalones: Episode[];
  study_guides: ArtifactRef[];
  quizzes: QuizRef[];
  other_artifacts: ArtifactRef[];
  counts: Record<string, number>;
  auth: AuthState;
  live: boolean;
  warnings: string[];
}

// Mirrors backend StudyGuideResponse — the in-hub study guide reader. Like QuizPrepareResponse,
// auth/download failures arrive as ok=false + a banner-ready message, never an HTTP error.
export interface StudyGuideResponse {
  notebook_id: string;
  artifact_id: string;
  ok: boolean;
  auth: AuthState;
  title?: string | null;
  notebooklm_url: string;
  markdown?: string | null;
  error?: string | null;
}

// Answer-key-FREE by construction — mirrors backend QuizPlayerQuestion.
export interface QuizPlayerQuestion {
  index: number;
  question: string;
  options: string[];
  hint?: string | null;
}

export interface QuizPrepareResponse {
  notebook_id: string;
  quiz_artifact_id: string;
  episode_artifact_id?: string | null;
  ok: boolean;
  auth: AuthState;
  session_id?: string | null;
  title?: string | null;
  total: number;
  questions: QuizPlayerQuestion[];
  error?: string | null;
}

export interface QuizGradeRequest {
  session_id: string;
  answers: Record<number, number | null>;
  hints?: Record<number, boolean>;
  mark_listened?: boolean;
}

export interface QuizReviewItem {
  index: number;
  question: string;
  options: string[];
  chosen_index?: number | null;
  chosen_text?: string | null;
  correct_index: number;
  correct_text: string;
  is_correct: boolean;
  used_hint: boolean;
  chosen_rationale?: string | null;
  correct_rationale: string;
}

export interface QuizGradeResponse {
  attempt_id: number;
  score: number;
  total: number;
  pct: number;
  episode_marked_listened: boolean;
  review: QuizReviewItem[];
}

// Mirrors backend ProgressResponse + friends.
export interface AttemptPoint {
  finished_at?: string | null;
  pct: number;
}

export interface TopicProgress {
  notebook_id: string;
  title: string;
  group?: string | null;
  group_label?: string | null;
  topic_url?: string | null;
  attempts: number;
  last_pct: number;
  best_pct: number;
  avg_pct: number;
  last_practiced?: string | null;
  points: AttemptPoint[];
}

export interface ShakyQuiz {
  notebook_id: string;
  title: string;
  topic_url?: string | null;
  quiz_artifact_id: string;
  total_misses: number;
  shaky_questions: number;
  last_review_at?: string | null;
}

export interface ActivityDay {
  day: string;
  count: number;
}

export interface ProgressSummary {
  attempts_total: number;
  topics_practiced: number;
  avg_pct: number;
  current_streak: number;
  longest_streak: number;
  last_activity?: string | null;
}

export interface ProgressResponse {
  generated_at: string;
  has_data: boolean;
  summary: ProgressSummary;
  topics: TopicProgress[];
  shaky: ShakyQuiz[];
  activity: ActivityDay[];
}

// Mirrors backend ReviewItem + ReviewResponse — the Phase-4 "Review next" queue.
export interface ReviewItem {
  notebook_id: string;
  title: string;
  group?: string | null;
  group_label?: string | null;
  topic_url?: string | null;
  mastery: number;
  decayed: number;
  due: boolean;
  priority: number;
  days_since_review?: number | null;
  total_misses: number;
  shaky_questions: number;
  last_review_at?: string | null;
  reason: string;
}

export interface ReviewResponse {
  generated_at: string;
  has_data: boolean;
  due_count: number;
  items: ReviewItem[];
}

// Mirrors backend StudyPlan* — the Phase-6 daily, time-boxed, interleaved review session.
export interface StudyPlanSegment {
  notebook_id: string;
  title: string;
  quiz_artifact_id: string;
  topic_url?: string | null;
  item_count: number;
  due_count: number;
  minutes: number;
  priority: number;
}

export interface StudyPlanResponse {
  generated_at: string;
  has_data: boolean;
  has_due: boolean;
  requested_minutes: number;
  total_minutes: number;
  total_items: number;
  due_items: number;
  segments: StudyPlanSegment[];
}

// Mirrors backend Reflection* — the post-episode reflection journal (Phase 6).
export interface ReflectionItem {
  id: number;
  notebook_id: string;
  title: string;
  episode_artifact_id?: string | null;
  body: string;
  grasp_rating?: number | null;
  created_at?: string | null;
  topic_url?: string | null;
}

export interface ReflectionsResponse {
  generated_at: string;
  has_data: boolean;
  count: number;
  avg_grasp?: number | null;
  items: ReflectionItem[];
}

// Mirrors backend CustomTopic + friends — non-NotebookLM interests (Phase 5).
export interface CustomTopic {
  id: number;
  title: string;
  notes: string;
  progress_pct: number;
  created_at: string;
  updated_at: string;
}

export interface CustomTopicsResponse {
  generated_at: string;
  topics: CustomTopic[];
}

export interface CustomTopicCreate {
  title: string;
  notes?: string;
  progress_pct?: number;
}

export interface CustomTopicUpdate {
  title?: string;
  notes?: string;
  progress_pct?: number;
}

export interface HealthResponse {
  ok: boolean;
  nlm_available: boolean;
  nlm_version?: string | null;
  notebooklm_root: string;
  root_exists: boolean;
}

// A learner's self-assessment of a project/capstone against its rubric (M3). Mirrors backend
// CourseAssessment. `ratings` maps each rubric criterion name to the chosen level label.
export interface CourseAssessment {
  self_rating?: number | null;
  ratings: Record<string, string>;
  note: string;
  updated_at?: string | null;
}

// Mirrors backend Course* models (Phase 6) — generated courses read from on-disk sidecars.
export interface CourseMaterial {
  type: string;
  title?: string | null;
  path?: string | null;
  url?: string | null;
  note?: string | null;
  format?: string | null;
  count?: number | null;
  notebook_id?: string | null;
  artifact?: string | null;
  rubric?: string | null; // M3: a rubrics/<id>.json path (exercise/project/capstone)
  assessment?: CourseAssessment | null; // M3: merged saved self-assessment, if any
}

// Rubric file content (fetched via courseMaterial for a material's `rubric` path).
export interface RubricLevel {
  label: string;
  description: string;
}
export interface RubricCriterion {
  name: string;
  levels: RubricLevel[];
}
export interface CourseRubric {
  criteria: RubricCriterion[];
}

export interface CourseLesson {
  id: string;
  title: string;
  objectives: string[];
  estimated_minutes?: number | null;
  materials: CourseMaterial[];
  completed: boolean;
}

export interface CourseModule {
  id: string;
  title: string;
  summary: string;
  lessons: CourseLesson[];
}

export interface CourseSummary {
  slug: string;
  title: string;
  topic: string;
  level: string;
  summary: string;
  prerequisites: string[];
  estimated_hours?: number | null;
  created_at: string;
  generator: string;
  module_count: number;
  lesson_count: number;
  material_counts: Record<string, number>;
  completed_lessons: number;
  progress_pct: number;
}

export interface CourseDetail extends CourseSummary {
  modules: CourseModule[];
}

export interface CoursesResponse {
  generated_at: string;
  courses: CourseSummary[];
}

export interface CourseMaterialResponse {
  path: string;
  kind: string; // "text" | "json"
  text?: string | null;
  data?: unknown;
}

export interface LessonCompleteResponse {
  lesson_id: string;
  completed: boolean;
  progress_pct: number;
  completed_lessons: number;
}

// Course quiz + the learner's attempt/SM-2 state (M2). Mirrors backend CourseQuizState.
export interface CourseQuizState {
  path: string; // also the quiz id
  lesson_id: string;
  module_id: string;
  title: string;
  question_count: number;
  attempts: number;
  last_score?: number | null;
  last_total?: number | null;
  last_pct?: number | null;
  last_attempt_at?: string | null;
  tracked_questions: number;
  due_questions: number;
}

export interface CourseQuizzesResponse {
  slug: string;
  generated_at: string;
  quizzes: CourseQuizState[];
}

// Course flashcard decks + per-card SM-2 review state (the M2 remainder). Mirrors backend
// CourseFlashcardDeck / FlashcardCardState + friends.
export interface CourseFlashcardDeck {
  path: string; // also the deck id
  lesson_id: string;
  module_id: string;
  title: string;
  card_count: number;
  tracked_cards: number;
  due_cards: number;
}

export interface CourseFlashcardsResponse {
  slug: string;
  generated_at: string;
  decks: CourseFlashcardDeck[];
}

// One card's review state, aligned by index to the deck file's order (tracked=false → new).
export interface FlashcardCardState {
  index: number;
  tracked: boolean;
  due: boolean;
  reps: number;
  lapses: number;
  due_at?: string | null;
  last_review_at?: string | null;
}

export interface CourseFlashcardStateResponse {
  slug: string;
  path: string;
  generated_at: string;
  cards: FlashcardCardState[];
}

export type FlashcardRating = "again" | "hard" | "good";

// Body for POST /courses/{slug}/flashcards/review — an index into the deck file; the card's
// stable key is derived server-side from its front text.
export interface FlashcardReviewRequest {
  index: number;
  rating: FlashcardRating;
}

// Course-level "what to do next" (M3). Mirrors backend CourseNextItem/CourseNextResponse.
export interface CourseNextItem {
  kind: "quiz_review" | "flashcards_review" | "lesson" | "quiz_new" | "project" | string;
  title: string;
  reason: string;
  module_id?: string | null;
  lesson_id?: string | null;
  path?: string | null;
}
export interface CourseNextResponse {
  slug: string;
  generated_at: string;
  all_done: boolean;
  items: CourseNextItem[];
}

// Body for POST /courses/{slug}/assess — a rubric self-assessment.
export interface CourseAssessmentRequest {
  self_rating?: number | null;
  ratings: Record<string, string>;
  note: string;
}

export interface Flashcard {
  front: string;
  back: string;
}

// M1 Today brief — mirrors backend BriefSource/BriefItem/BriefTopic/BriefResponse
// (+ the M2 note models).
export interface BriefSource {
  title: string;
  url: string;
}

// One flat inline note on a brief item (M2). topic_slug/brief_date/item_headline snapshot
// what was annotated so the note outlives the regenerable sweep file; topic_title is
// resolved server-side from the roster.
export interface BriefNote {
  id: number;
  item_id: string;
  topic_slug: string;
  topic_title: string;
  brief_date: string;
  item_headline: string;
  body: string;
  created_at: string;
}

export interface BriefNoteCreate {
  item_id: string;
  topic_slug: string;
  brief_date: string;
  item_headline: string;
  body: string;
}

export interface BriefNotesResponse {
  generated_at: string;
  notes: BriefNote[];
}

export interface BriefNoteDeleteResponse {
  ok: boolean;
}

export interface BriefItem {
  // sha1(date|slug|headline)[:12], derived server-side at read time — the note anchor.
  id: string;
  headline: string;
  attribution: string;
  digest: string;
  why_it_matters: string;
  sources: BriefSource[];
  notes: BriefNote[];
  // M3 read-time dedup: true when this story's headline/source already appeared in the last
  // week for this topic; first_seen is that earliest YYYY-MM-DD. Labelled, never dropped.
  developing: boolean;
  first_seen?: string | null;
}

// One topic section: either structured (top_line/items from <topic>.json) or a raw_markdown
// fallback (legacy md-only day, or an unreadable json carried with `error`) — never dropped.
export interface BriefTopic {
  slug: string;
  title: string;
  as_of?: string | null;
  top_line?: string | null;
  context_note?: string | null;
  items: BriefItem[];
  raw_markdown?: string | null;
  error?: string | null;
}

export interface BriefResponse {
  generated_at: string;
  has_data: boolean;
  date?: string | null; // YYYY-MM-DD of the sweep folder being served
  topics: BriefTopic[];
  // M4: the served day has a narrated brief.mp3 — GET /api/brief/audio streams it.
  audio_available: boolean;
}

export interface BriefVisitResponse {
  ok: boolean;
  day: string;
  visited_at: string;
}

// M5 chat-with-the-brief: one grounded follow-up answer about a served item. item_id is
// date-scoped, so a stale tab's question 404s after the brief rolls to a new day.
export interface BriefChatRequest {
  item_id: string;
  topic_slug: string;
  question: string;
}

export interface BriefChatResponse {
  answer: string; // markdown, grounded in the served item — ephemeral unless saved as a note
}
