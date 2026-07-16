"""Pydantic models = the backend↔frontend contract. Mirrored in frontend/src/api/types.ts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class AuthState(BaseModel):
    ok: bool = True
    message: Optional[str] = None


class Episode(BaseModel):
    n: Optional[int] = None
    title: str
    artifact_id: str
    fmt: Optional[str] = None
    length: Optional[str] = None
    status: Optional[str] = None
    listened: bool = False
    source: str = "readme"


class ArtifactRef(BaseModel):
    n: Optional[int] = None
    title: str
    artifact_id: str
    type: str
    status: Optional[str] = None
    source: str = "readme"


class QuizRef(ArtifactRef):
    takeable: bool = False  # Phase 2 flips this on


class NotebookCard(BaseModel):
    notebook_id: str
    alias: str
    title: str
    group: str
    group_label: str
    template: Optional[str] = None
    tags: List[str] = []
    archived: bool = False
    notebooklm_url: str
    topic_url: str
    counts: Dict[str, int] = {}
    # Deferred to later phases — explicit placeholders so the UI can render "—".
    progress_pct: Optional[float] = None
    mastery: Optional[float] = None
    due_for_review: bool = False
    last_touched: Optional[str] = None


class Group(BaseModel):
    key: str
    label: str
    notebooks: List[NotebookCard] = []


class CatalogResponse(BaseModel):
    generated_at: str
    groups: List[Group] = []
    auth: AuthState = AuthState()
    warnings: List[str] = []
    notebooklm_root: str


class TopicDetail(BaseModel):
    notebook_id: str
    alias: str
    title: str
    group: str
    group_label: str
    template: Optional[str] = None
    tags: List[str] = []
    archived: bool = False
    merged_into: Optional[str] = None
    source_count: Optional[int] = None
    notebooklm_url: str
    episodes: List[Episode] = []
    standalones: List[Episode] = []
    study_guides: List[ArtifactRef] = []
    quizzes: List[QuizRef] = []
    other_artifacts: List[ArtifactRef] = []
    counts: Dict[str, int] = {}
    auth: AuthState = AuthState()
    live: bool = False
    warnings: List[str] = []


class StudyGuideResponse(BaseModel):
    """A study guide fetched for the in-hub reader. Like QuizPrepareResponse, never a 500:
    an auth lapse or download failure degrades to ok=False + a banner-ready message."""

    notebook_id: str
    artifact_id: str
    ok: bool = True
    auth: AuthState = AuthState()
    title: Optional[str] = None
    notebooklm_url: str
    markdown: Optional[str] = None
    error: Optional[str] = None


class QuizPlayerQuestion(BaseModel):
    """A single question as the player sees it — answer-key-FREE by construction.

    Carries only what's needed to render and answer: the prompt, the option *texts*, and the
    optional hint. No ``isCorrect``, no ``correct_index``, no per-option ``rationale`` — those
    live only in the keyed session file the grader reads, so the answer can't leak to the client.
    """

    index: int
    question: str
    options: List[str]
    hint: Optional[str] = None


class QuizPrepareResponse(BaseModel):
    notebook_id: str
    quiz_artifact_id: str
    episode_artifact_id: Optional[str] = None
    ok: bool = True
    auth: AuthState = AuthState()
    session_id: Optional[str] = None
    title: Optional[str] = None
    total: int = 0
    questions: List[QuizPlayerQuestion] = []
    error: Optional[str] = None


class QuizGradeRequest(BaseModel):
    session_id: str
    # JSON object keys arrive as strings; pydantic coerces them to the int question indices.
    answers: Dict[int, Optional[int]] = {}
    hints: Dict[int, bool] = {}
    mark_listened: bool = False


class QuizReviewItem(BaseModel):
    index: int
    question: str
    options: List[str]
    chosen_index: Optional[int] = None
    chosen_text: Optional[str] = None
    correct_index: int
    correct_text: str
    is_correct: bool
    used_hint: bool = False
    # Rationale for the chosen option (on a miss) and for the correct one — safe to send now
    # that the attempt is graded and saved.
    chosen_rationale: Optional[str] = None
    correct_rationale: str = ""


class QuizGradeResponse(BaseModel):
    attempt_id: int
    score: int
    total: int
    pct: float
    episode_marked_listened: bool = False
    review: List[QuizReviewItem] = []


class AttemptPoint(BaseModel):
    """One graded attempt in a topic's trend line."""

    finished_at: Optional[str] = None
    pct: float = 0.0


class TopicProgress(BaseModel):
    notebook_id: str
    title: str
    group: Optional[str] = None
    group_label: Optional[str] = None
    topic_url: Optional[str] = None
    attempts: int = 0
    last_pct: float = 0.0
    best_pct: float = 0.0
    avg_pct: float = 0.0
    last_practiced: Optional[str] = None
    points: List[AttemptPoint] = []


class ShakyQuiz(BaseModel):
    """A quiz with accumulated misses. The question text isn't stored (read-only hub), so we
    surface the miss tally + how many distinct questions are shaky — enough to nudge a retake."""

    notebook_id: str
    title: str
    topic_url: Optional[str] = None
    quiz_artifact_id: str
    total_misses: int = 0
    shaky_questions: int = 0
    last_review_at: Optional[str] = None


class ActivityDay(BaseModel):
    day: str
    count: int = 0


class ProgressSummary(BaseModel):
    attempts_total: int = 0
    topics_practiced: int = 0
    avg_pct: float = 0.0
    current_streak: int = 0
    longest_streak: int = 0
    last_activity: Optional[str] = None


class ProgressResponse(BaseModel):
    generated_at: str
    has_data: bool = False
    summary: ProgressSummary = ProgressSummary()
    topics: List[TopicProgress] = []
    shaky: List[ShakyQuiz] = []
    activity: List[ActivityDay] = []


class ReviewItem(BaseModel):
    """One topic in the Phase-4 spaced-repetition "Review next" queue.

    ``mastery`` is the stored fraction; ``decayed`` is that score faded by time since last
    review (the estimated *current* retention). ``due`` / ``priority`` / ``reason`` come from the
    decay model — never invented question prose, just the miss tally + how stale it is.
    """

    notebook_id: str
    title: str
    group: Optional[str] = None
    group_label: Optional[str] = None
    topic_url: Optional[str] = None
    mastery: float = 0.0
    decayed: float = 0.0
    due: bool = False
    priority: float = 0.0
    days_since_review: Optional[float] = None
    total_misses: int = 0
    shaky_questions: int = 0
    last_review_at: Optional[str] = None
    reason: str = ""


class ReviewResponse(BaseModel):
    generated_at: str
    has_data: bool = False
    due_count: int = 0
    items: List[ReviewItem] = []


class StudyPlanSegment(BaseModel):
    """One quiz to retake in a study session, sized by how many of its questions are due."""

    notebook_id: str
    title: str
    quiz_artifact_id: str
    topic_url: Optional[str] = None
    item_count: int = 0
    due_count: int = 0
    minutes: float = 0.0
    priority: float = 0.0


class StudyPlanResponse(BaseModel):
    """A bounded, interleaved review session built from the per-item SM-2 queue (Phase 6).

    ``segments`` are ordered so the same topic isn't back-to-back. ``has_data`` is false when no
    questions have been answered yet; ``has_due`` distinguishes "nothing due" from "nothing at all".
    """

    generated_at: str
    has_data: bool = False
    has_due: bool = False
    requested_minutes: int = 0
    total_minutes: float = 0.0
    total_items: int = 0
    due_items: int = 0
    segments: List[StudyPlanSegment] = []


class ReflectionItem(BaseModel):
    """One saved post-episode reflection — captured by the `/episode-review` skill, surfaced
    (finally) in the hub as of Phase 6."""

    id: int
    notebook_id: str
    title: str
    episode_artifact_id: Optional[str] = None
    body: str = ""
    grasp_rating: Optional[int] = None
    created_at: Optional[str] = None
    topic_url: Optional[str] = None


class ReflectionsResponse(BaseModel):
    generated_at: str
    has_data: bool = False
    count: int = 0
    avg_grasp: Optional[float] = None
    items: List[ReflectionItem] = []


class HealthResponse(BaseModel):
    ok: bool = True
    nlm_available: bool = False
    nlm_version: Optional[str] = None
    notebooklm_root: str
    root_exists: bool


class EpisodeToggle(BaseModel):
    listened: bool


class CustomTopic(BaseModel):
    """A non-NotebookLM interest (a book, a YouTube series, a loose thread) tracked loosely with
    manual progress + notes. Mirrors the ``custom_topics`` store row."""

    id: int
    title: str
    notes: str = ""
    progress_pct: int = 0
    created_at: str
    updated_at: str


class CustomTopicsResponse(BaseModel):
    generated_at: str
    topics: List[CustomTopic] = []


class CustomTopicCreate(BaseModel):
    title: str
    notes: str = ""
    progress_pct: int = 0


class CustomTopicUpdate(BaseModel):
    """All fields optional — only the provided ones are patched (an empty body is a no-op)."""

    title: Optional[str] = None
    notes: Optional[str] = None
    progress_pct: Optional[int] = None


# -- Courses (Phase 6) ---------------------------------------------------------
# A course is a sidecar dir on disk (course.json + material files); these models mirror the
# manifest read by ``app.courses.manifest``. Progress is merged in from the SQLite store.

class CourseMaterial(BaseModel):
    """One material attached to a lesson. ``type`` drives rendering; the other fields vary by
    type (file-backed ones carry ``path``; ``reading`` carries ``url``; ``notebooklm`` carries
    ``notebook_id``). Extra fields are preserved so the format can grow without a model change."""

    model_config = ConfigDict(extra="allow")
    type: str
    title: Optional[str] = None
    path: Optional[str] = None
    url: Optional[str] = None
    note: Optional[str] = None
    format: Optional[str] = None
    count: Optional[int] = None
    notebook_id: Optional[str] = None
    artifact: Optional[str] = None


class CourseLesson(BaseModel):
    id: str
    title: str
    objectives: List[str] = []
    estimated_minutes: Optional[int] = None
    materials: List[CourseMaterial] = []
    completed: bool = False  # merged from course_lesson_progress


class CourseModule(BaseModel):
    id: str
    title: str
    summary: str = ""
    lessons: List[CourseLesson] = []


class CourseSummary(BaseModel):
    slug: str
    title: str
    topic: str = ""
    level: str = "beginner"
    summary: str = ""
    prerequisites: List[str] = []
    estimated_hours: Optional[float] = None
    created_at: str = ""
    generator: str = ""
    module_count: int = 0
    lesson_count: int = 0
    material_counts: Dict[str, int] = {}
    completed_lessons: int = 0
    progress_pct: int = 0


class CourseDetail(CourseSummary):
    modules: List[CourseModule] = []


class CoursesResponse(BaseModel):
    generated_at: str
    courses: List[CourseSummary] = []


class CourseMaterialResponse(BaseModel):
    """One material file's content: markdown/mermaid as ``text``, JSON decks/quizzes as ``data``."""

    path: str
    kind: str  # "text" | "json"
    text: Optional[str] = None
    data: Optional[Any] = None


class LessonComplete(BaseModel):
    completed: bool


class CourseQuizState(BaseModel):
    """A course quiz material + the learner's attempt/SM-2 state (read-only, derived from the
    shared store under the ``course:<slug>`` namespace). ``path`` doubles as the quiz id."""

    path: str
    lesson_id: str
    module_id: str
    title: str
    question_count: int = 0
    attempts: int = 0
    last_score: Optional[int] = None
    last_total: Optional[int] = None
    last_pct: Optional[float] = None
    last_attempt_at: Optional[str] = None
    tracked_questions: int = 0   # questions with SM-2 state (answered at least once)
    due_questions: int = 0       # of those, how many are due for review now


class CourseQuizzesResponse(BaseModel):
    slug: str
    generated_at: str
    quizzes: List[CourseQuizState] = []


class BriefSource(BaseModel):
    title: str
    url: str


class BriefNote(BaseModel):
    """One flat inline note on a brief item (M2). ``topic_slug``/``brief_date``/
    ``item_headline`` snapshot what was annotated so the note stays meaningful after its
    (gitignored, regenerable) sweep file is re-swept or gone; ``topic_title`` is resolved
    from the roster at read time."""

    id: int
    item_id: str
    topic_slug: str
    topic_title: str = ""
    brief_date: str
    item_headline: str
    body: str
    created_at: str


class BriefNoteCreate(BaseModel):
    item_id: str
    topic_slug: str
    brief_date: str
    item_headline: str
    body: str


class BriefNotesResponse(BaseModel):
    generated_at: str
    notes: List[BriefNote] = []


class BriefNoteDeleteResponse(BaseModel):
    ok: bool = True


class BriefItem(BaseModel):
    # sha1(date|slug|headline)[:12], derived at read time in app.sweeps (M2) — the anchor
    # notes attach to. Empty only for hand-built instances; the API always sets it.
    id: str = ""
    headline: str
    attribution: str = ""
    digest: str = ""
    why_it_matters: str = ""
    sources: List[BriefSource] = []
    notes: List[BriefNote] = []
    # M3 read-time dedup (app.sweeps._annotate_developing): set when this story's headline or a
    # source URL already appeared in the last week for this topic. Labels a developing story —
    # first_seen is that earliest date — and the item is never dropped.
    developing: bool = False
    first_seen: Optional[str] = None


class BriefTopic(BaseModel):
    """One topic section of the Today brief. Either structured (top_line/items, from
    <topic>.json) or a ``raw_markdown`` fallback (md-only legacy day, or a json that
    wouldn't parse — carried with ``error`` rather than silently dropped)."""

    slug: str
    title: str
    as_of: Optional[str] = None
    top_line: Optional[str] = None
    context_note: Optional[str] = None
    items: List[BriefItem] = []
    raw_markdown: Optional[str] = None
    error: Optional[str] = None


class BriefResponse(BaseModel):
    generated_at: str
    has_data: bool = False
    date: Optional[str] = None  # YYYY-MM-DD of the latest sweep folder being served
    topics: List[BriefTopic] = []


class BriefVisitResponse(BaseModel):
    ok: bool = True
    day: str
    visited_at: str
