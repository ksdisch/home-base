"""Pydantic models = the backend↔frontend contract. Mirrored in frontend/src/api/types.ts."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


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
