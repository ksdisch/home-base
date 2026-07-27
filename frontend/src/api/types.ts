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

// A course that builds on this notebook — the reverse cross-link the catalog stamps on each card.
export interface NotebookCourseRef {
  slug: string;
  title: string;
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
  courses: NotebookCourseRef[]; // courses that reference this notebook (M4 reverse cross-link)
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

// M4: the sidecar catalog's view of a notebooklm material's linked notebook. found=false when
// the notebook isn't in this machine's catalog — the UI degrades to the material's note.
export interface CourseNotebookRef {
  notebook_id: string;
  found: boolean;
  title?: string | null;
  topic_url?: string | null;
  notebooklm_url?: string | null;
  counts: Record<string, number>;
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
  notebook?: CourseNotebookRef | null; // M4: merged catalog join for notebooklm materials
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
  editable: boolean; // M5: a user copy exists under COURSES_DIR, so edits can land
  notebook?: CourseNotebookRef | null; // the source notebook this course builds on (cross-link)
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

// -- M5 authoring loop ------------------------------------------------------------
// Structural edits ride the backend's transactional writer: ok=false means validation
// bounced and the course rolled back untouched (errors say why).

export interface CourseObjectivesUpdate {
  objectives: string[];
}

export interface CourseOrderModule {
  id: string;
  lessons: string[];
}

// The COMPLETE desired order — every module id exactly once, every lesson id exactly once
// inside its own module (cross-module moves are out of M5's scope).
export interface CourseOrderUpdate {
  modules: CourseOrderModule[];
}

export interface CourseEditResponse {
  ok: boolean;
  errors: string[];
  warnings: string[];
}

export interface CourseRegenRequest {
  path: string;
  guidance: string;
}

export interface CourseRegenResponse {
  ok: boolean;
  path: string;
  rolled_back: boolean;
  errors: string[];
  warnings: string[];
  error?: string | null;
  count?: number | null;
  duration_ms?: number | null;
  total_cost_usd?: number | null;
}

export interface Flashcard {
  front: string;
  back: string;
}

// -- learning paths (M8) — mirrors backend PathStep/PathResponse + the write bodies. A path is a
// generated sidecar over a NotebookLM topic (app.paths); the three axes (coverage/recall/
// confidence) are merged onto it at read time. `completed`/`confidence` come from the store.
export interface PathStep {
  id: string;
  kind: string; // intro | audio | read | flashcards | quiz | bridge | reflect | recap
  title: string;
  focus?: string | null;
  body?: string | null;
  artifact_id?: string | null;
  artifact_type?: string | null;
  estimated_minutes?: number | null;
  completed: boolean; // coverage — from path_step_progress
  confidence?: number | null; // 1-5 self-rating — from path_confidence
}

export interface PathResponse {
  notebook_id: string;
  title: string;
  topic: string;
  generated_at: string;
  generator: string;
  steps: PathStep[];
  step_count: number;
  completed_steps: number;
  progress_pct: number; // coverage (steps done)
  mastery?: number | null; // SM-2 recall, decayed — null until the topic's quiz/flashcards are practiced
  confidence?: number | null; // mean self-rating so far — null until any step is rated
}

export interface StepComplete {
  completed: boolean;
}

export interface StepConfidence {
  rating: number; // 1-5
}

export interface BridgeGradeRequest {
  answer: string;
}

// The formative grade of a bridge-check answer. ok=false + a calm error means the grade couldn't
// run (a claude hiccup) — never an HTTP error. The step is marked done on submit regardless
// (coverage), and a bridge NEVER moves mastery; `path` is the refreshed three-axis state.
export interface BridgeGradeResponse {
  ok: boolean;
  feedback?: string | null;
  error?: string | null;
  path: PathResponse;
}

// The outcome of an on-demand path composition (M8 Designer). ok=false + a calm error means the
// claude run/parse failed (never an HTTP error); errors carries validation failures (a fabricated
// artifact id, bad structure) — on any failure nothing is written. path is the fresh three-axis
// state on success so the card lights up without a refetch. Cost fields come from the envelope.
export interface PathGenerateResponse {
  ok: boolean;
  error?: string | null;
  errors: string[];
  path?: PathResponse | null;
  total_cost_usd?: number | null;
  duration_ms?: number | null;
}

// The Plan's Continue lane (M8 #12) — every composed path + its resume point: coverage progress
// and the next incomplete step. `next_step` is null once a path is fully done. Non-empty day one
// via the bundled example path.
export interface PathSummary {
  notebook_id: string;
  title: string;
  topic: string;
  step_count: number;
  completed_steps: number;
  progress_pct: number; // coverage (steps done)
  next_step?: PathStep | null;
  confidence?: number | null; // mean self-rating so far — feeds Progress's confidence axis (#13)
}

export interface PathsResponse {
  generated_at: string;
  items: PathSummary[];
}

// -- study scheduler (v0): opt-in Google Calendar study blocks for a learning path --------------

export interface StudyBlockStep {
  id: string;
  kind: string;
  title: string;
  minutes: number;
}

// One study block the planner proposes — nothing is written until confirm. start/end are RFC3339
// with a CT offset; step_ids are the path steps this session covers. overlaps carries the titles of
// existing calendar events this block double-books (only in double-book mode) so the UI can flag it.
export interface ProposedBlock {
  start: string;
  end: string;
  minutes: number;
  title: string;
  step_ids: string[];
  steps: StudyBlockStep[];
  overlaps?: string[];
}

// An existing calendar event filling the requested window — surfaced so you can see what's booked
// (e.g. a shared "GF: dinner" you can study through) and choose to double-book. start/end are RFC3339.
export interface ConflictEvent {
  start: string;
  end: string;
  title: string;
}

// A study block that WAS written to the calendar — carries the Google event_id + calendar_id that
// keep it cleanly removable.
export interface WrittenBlock {
  id: number;
  step_id: string;
  title: string;
  start: string;
  end: string;
  event_id: string;
  calendar_id: string;
  status: string; // "written" | "removed"
}

// The per-path scheduler state: opt-in flag + session length, whether the calendar is connected,
// the live (written, not removed) blocks, and the learner's persisted window prefs so the panel
// hydrates its controls on load. A pref is null when it has never been set (planner default applies).
// days_of_week uses Python weekday() ints — Mon=0 … Sun=6; null = every day.
// token_age_days is how long ago the Google consent was granted (null when unknowable), so the panel
// can warn before Google's testing-mode ~7-day refresh expiry silently disconnects the calendar.
export interface StudyScheduleState {
  track_kind: string;
  track_id: string;
  enabled: boolean;
  session_minutes: number;
  connected: boolean;
  calendar_id?: string | null;
  blocks: WrittenBlock[];
  day_start_hour?: number | null;
  day_end_hour?: number | null;
  days_of_week?: number[] | null;
  max_blocks?: number | null;
  token_age_days?: number | null;
}

// The effective planner knobs a propose actually used (controls merged with the LLM lane), echoed so
// the panel can reflect them. days_of_week is Mon=0 … Sun=6; [] means every day (no restriction).
export interface AppliedPlan {
  session_minutes: number;
  day_start_hour: number;
  day_end_hour: number;
  days_of_week: number[];
  window_days: number;
  max_blocks: number;
  max_per_day: number;
}

// The proposed set (read-only against the calendar — writes no events). connected=false means the
// calendar isn't wired yet (honest "connect" state, never an HTTP error); message is the optional
// negotiation line; unscheduled_step_ids are steps that didn't fit the window; applied echoes the
// effective knobs.
export interface StudyProposal {
  ok: boolean;
  connected: boolean;
  session_minutes: number;
  blocks: ProposedBlock[];
  unscheduled_step_ids: string[];
  already_scheduled_step_ids?: string[]; // steps left out because a live block already covers them
  message?: string | null;
  error?: string | null;
  applied?: AppliedPlan | null;
  conflicts?: ConflictEvent[]; // events filling the window, flagged when steps didn't fit
  can_double_book?: boolean; // steps went unscheduled because the window is booked → offer to override
  total_cost_usd?: number | null;
  duration_ms?: number | null;
}

export interface StudyOptInRequest {
  enabled: boolean;
  session_minutes?: number | null;
}

// A propose request. preference is free-text for the claude -p negotiation lane; the rest are explicit
// control knobs (an explicit knob wins over anything the LLM suggests for that key). Any knob omitted
// falls back to the persisted pref, then the planner default. days_of_week is Mon=0 … Sun=6; an empty
// list clears the restriction (every day).
export interface StudyProposeRequest {
  preference?: string | null;
  session_minutes?: number | null;
  days?: number | null; // window_days
  day_start_hour?: number | null;
  day_end_hour?: number | null;
  days_of_week?: number[] | null;
  max_blocks?: number | null;
  max_per_day?: number | null;
  allow_double_book?: boolean; // place into the window ignoring free/busy, flagging the overlaps
}

// The reviewed set to write — a subset of the proposal is fine (blocks can be dropped in review).
export interface StudyConfirmRequest {
  blocks: ProposedBlock[];
}

// A subset of live blocks to remove, or null/omitted to remove every live block.
export interface StudyRemoveRequest {
  block_ids?: number[] | null;
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
  // FR13: the digest as this story read on first_seen day, verbatim — shown behind the
  // badge and threaded into chat. Optional for stale pre-FR13 SW-cached payloads.
  prior_digest?: string | null;
  // Calibrated Doubt v0: the optional wager lane — a falsifiable call that this story
  // shows fresh movement by the topic's next sweep, with its stated confidence (1–99).
  // Set only when the sweep made a well-formed call; optional for pre-calibration
  // SW-cached payloads.
  prediction?: string | null;
  confidence?: number | null;
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

// QU12: an active roster topic that produced no renderable file for the served day —
// named on the page so a crashed topic is visible instead of just absent.
export interface BriefMissingTopic {
  slug: string;
  title: string;
}

// FR4: one seek chip over the narrated mp3 — start_seconds is a word-count estimate
// from sweeps/audio_brief.py (a landmark, not a measured timing).
export interface BriefAudioChapter {
  slug: string;
  title: string;
  start_seconds: number;
}

// Mirror v0 (docs/ideas/the-mirror.md): one slice of the attention split — this
// topic/category's share of every keyed signal (notes + asks + news events) in the window.
export interface BriefMirrorAttention {
  slug: string;
  title: string;
  events: number;
  share_pct: number;
}

// The deterministic 'You this week' self-read over the last 7 local days of logged
// behavior — no LLM, no writes. sufficient=false is the honest cold start: counts still
// carried, sentence empty, nothing extrapolated.
export interface BriefMirror {
  generated_at: string;
  window_days: number;
  sufficient: boolean;
  sentence: string;
  mornings: number;
  notes: number;
  asks: number;
  news_events: number;
  attention: BriefMirrorAttention[];
  paused_topics: string[];
}

// Readiness v0 (docs/ideas/readiness-brief.md): one projected trajectory on the 'Coming
// up' strip — a story on the served morning that also appeared on prior mornings in the
// window. Identity is the developing badge's own headline/source-URL match, so strip and
// badge can never disagree; item_id is the served item's read-time anchor.
export interface BriefReadinessItem {
  slug: string;
  title: string;
  item_id: string;
  headline: string;
  days_seen: number;
  first_seen: string;
}

// The deterministic 'Coming up' forward projection over in-repo sweep history — no LLM,
// no writes. sufficient=false is the honest cold start (fewer than two prior renderable
// mornings): nothing projected from thin history, history_days says why.
export interface BriefReadiness {
  generated_at: string;
  window_days: number;
  history_days: number;
  sufficient: boolean;
  items: BriefReadinessItem[];
}

// Calibrated Doubt v0 (docs/ideas/calibrated-doubt.md): one graded wager on the
// 'Yesterday's calls' strip — the morning it was made, the falsifiable call, the stated
// confidence, and the deterministic outcome (did the story show fresh movement by the
// topic's next readable sweep — the developing badge's own identity-key join).
export interface BriefCalibrationCall {
  slug: string;
  title: string;
  day: string;
  headline: string;
  prediction: string;
  confidence: number;
  outcome: boolean;
}

// The running public calibration record behind the strip, recomputed each serve from
// the append-only backend ledger. `trial` is the assumption-4 gate made visible: true
// until a week of distinct graded mornings is on the books, and the strip says so.
export interface BriefCalibration {
  generated_at: string;
  window_days: number;
  resolved: number;
  hits: number;
  days: number;
  brier?: number | null;
  trial: boolean;
  yesterday: BriefCalibrationCall[];
}

// Overnight Chief of Staff v0 (docs/ideas/overnight-chief-of-staff.md): one draft-only
// proposal on the queue — a note the nightly pass drafted onto the served day's item.
// Nothing was sent or executed; approve lands `body` through the existing notes path
// (`note_id` is the result), discard is the undo. Resolution is single-shot.
export interface BriefOvernightProposal {
  id: string;
  type: string;
  slug: string;
  title: string;
  item_id: string;
  item_headline: string;
  body: string;
  status: "proposed" | "approved" | "discarded";
  note_id?: number | null;
  created_at: string;
}

// The draft-only after-action queue reduced from the backend's overnight ledger — what
// the nightly pass prepared from in-repo data, each proposal wearing its resolution.
export interface BriefOvernight {
  generated_at: string;
  date: string;
  proposals: BriefOvernightProposal[];
}

export interface BriefResponse {
  generated_at: string;
  has_data: boolean;
  date?: string | null; // YYYY-MM-DD of the sweep folder being served
  topics: BriefTopic[];
  // M4: the served day has a narrated brief.mp3 — GET /api/brief/audio streams it.
  audio_available: boolean;
  // FR4: chapter seek offsets — only populated beside a real mp3. Optional so a
  // pre-FR4 payload replayed from the service-worker cache stays valid.
  audio_chapters?: BriefAudioChapter[];
  // QU12: active (non-paused) roster topics missing from the served day, roster order.
  // Optional so a pre-QU12 payload replayed from the service-worker cache stays valid.
  missing_topics?: BriefMissingTopic[];
  // QU1: the served day's renderable neighbors — the archive's prev/next walk. Optional
  // for pre-QU1 SW-cached payloads; null at either edge.
  prev_date?: string | null;
  next_date?: string | null;
  // Mirror v0: the live view's 'You this week' self-read. Optional so pre-Mirror
  // SW-cached payloads stay valid; null on ?date= archive views.
  mirror?: BriefMirror | null;
  // Readiness v0: the live morning's 'Coming up' projection. Optional so pre-readiness
  // SW-cached payloads stay valid; null on ?date= archives and no-served-day payloads.
  readiness?: BriefReadiness | null;
  // Calibrated Doubt v0: the graded-wager record ('Yesterday's calls') — grading happens
  // at serve time, so it rides the live view only. Optional so pre-calibration SW-cached
  // payloads stay valid; null on ?date= archives and no-served-day payloads.
  calibration?: BriefCalibration | null;
  // Overnight v0: the draft-only approve/discard queue — live view only (an archived
  // ?date= morning is a record, not a to-do list). Optional so pre-overnight SW-cached
  // payloads stay valid.
  overnight?: BriefOvernight | null;
}

export interface BriefVisitResponse {
  ok: boolean;
  day: string;
  visited_at: string;
}

// FR2: the phone's stale-morning tap — started = a detached sweep.sh was spawned;
// already_running = honest no-op because one is in flight. Never both true.
export interface BriefSweepResponse {
  started: boolean;
  already_running: boolean;
}

// Habit instrumentation for the kickoff's v1 success check (~3 weeks in): mornings =
// distinct local days the Today page was opened (target ≥5/week), notes = brief notes
// attached (target ≥3/week). Weeks are local Monday-start.
export interface BriefHabitWeek {
  week_start: string; // Monday, YYYY-MM-DD, local calendar
  mornings: number;
  notes: number;
}

export interface BriefHabitResponse {
  generated_at: string;
  weeks: BriefHabitWeek[]; // oldest first; the last entry is the current week
  // PR5 sweep-trust gauge: date of the last manual accuracy re-grade (newest dated
  // heading in docs/sweep-trust-log.md); null when there's no grade on record.
  last_graded?: string | null;
}

// Brief archive index — all renderable sweep dates, newest-first.
export interface BriefArchiveEntry {
  date: string; // YYYY-MM-DD
  has_audio: boolean;
}

export interface BriefArchiveResponse {
  dates: BriefArchiveEntry[];
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

// -- news mode (M7) --------------------------------------------------------------

export interface NewsItem {
  id: string; // sha1(link)[:12] — stable across refetches, Phase 2's event anchor
  headline: string;
  url: string; // a Google News redirect link — opens the original article
  source?: string | null;
  published_at?: string | null; // UTC ISO 8601; null when the feed omitted it
}

export interface NewsCategory {
  slug: string;
  title: string;
}

export interface NewsCategoriesResponse {
  generated_at: string;
  categories: NewsCategory[]; // display order = sweeps/news_categories.json order
}

export interface NewsCategoryResponse {
  generated_at: string;
  slug: string;
  title: string;
  fetched_at?: string | null; // when this payload was pulled from Google News
  stale: boolean; // true = refresh failed, serving the expired cache honestly
  items: NewsItem[];
}

// M7 Phase 2: one For-You signal — click | visit | more_like | not_interested. Item kinds
// carry the item snapshot (the feed cache rolls over in minutes, so events are self-contained).
export interface NewsEventCreate {
  kind: "click" | "visit" | "more_like" | "not_interested";
  category_slug: string;
  item_id?: string | null;
  headline?: string | null;
  source?: string | null;
  url?: string | null;
}

export interface NewsEventResponse {
  ok: boolean;
  id: number;
  created_at: string;
}

// M7 Phase 3: a ranked For You item — category_slug is its origin section, or
// "search:<term>" when the profile pulled it from beyond the standard categories.
export interface ForYouItem extends NewsItem {
  category_slug?: string | null;
}

// M7 Phase 4: a topic-scout find — a persistent interest the morning brief doesn't cover.
export interface NewsTopicSuggestion {
  term: string;
  score: number;
  days_seen: number;
  example_headlines: string[];
}

export interface NewsForYouResponse {
  generated_at: string;
  learning: boolean; // cold start: fewer than 20 positive signals so far
  event_count: number;
  items: ForYouItem[];
  suggestions: NewsTopicSuggestion[]; // the Mode-A bridge, dismissible
}

export interface NewsSuggestionActionRequest {
  term: string;
}

export interface NewsSuggestionAddResponse {
  ok: boolean;
  slug: string; // the roster entry tomorrow's sweep picks up
  title: string;
}

export interface NewsSuggestionDismissResponse {
  ok: boolean;
  term: string;
}
