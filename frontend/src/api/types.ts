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
