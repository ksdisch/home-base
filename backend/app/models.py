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

class CourseAssessment(BaseModel):
    """A learner's self-assessment of a project/capstone against its rubric (M3). ``ratings`` maps
    each rubric criterion name to the chosen level label; ``self_rating`` is an optional 1–5 overall.
    Read from ``course_rubric_assessment`` and merged onto the owning material in the course detail."""

    self_rating: Optional[int] = None
    ratings: Dict[str, str] = {}
    note: str = ""
    updated_at: Optional[str] = None


class CourseNotebookRef(BaseModel):
    """The sidecar catalog's view of a ``notebooklm`` material's linked notebook (M4).
    ``found=False`` when the referenced notebook isn't in this machine's catalog — the UI
    degrades to the material's note. Merged in by the course-detail endpoint; read-only."""

    notebook_id: str
    found: bool = False
    title: Optional[str] = None
    topic_url: Optional[str] = None
    notebooklm_url: Optional[str] = None
    counts: Dict[str, int] = {}


class CourseMaterial(BaseModel):
    """One material attached to a lesson. ``type`` drives rendering; the other fields vary by
    type (file-backed ones carry ``path``; ``reading`` carries ``url``; ``notebooklm`` carries
    ``notebook_id``). Extra fields are preserved so the format can grow without a model change.

    M3: ``rubric`` (a ``rubrics/<id>.json`` path) makes an exercise/project/capstone self-assessable;
    ``assessment`` is the learner's saved self-assessment, merged in by the course-detail endpoint.
    M4: ``notebook`` is the catalog join for a ``notebooklm`` material's ``notebook_id`` — the
    course page cross-links to the real topic surfaces instead of rendering a dead note."""

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
    rubric: Optional[str] = None
    assessment: Optional[CourseAssessment] = None
    notebook: Optional[CourseNotebookRef] = None


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
    editable: bool = False  # a user copy exists under COURSES_DIR, so M5 edits can land


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


class CourseFlashcardDeck(BaseModel):
    """A course flashcard deck + the learner's SM-2 review state (read-only, derived from the
    shared store under ``course:<slug>`` exactly like a course quiz). ``path`` doubles as the
    deck id."""

    path: str
    lesson_id: str
    module_id: str
    title: str
    card_count: int = 0
    tracked_cards: int = 0   # cards reviewed at least once (they carry SM-2 state)
    due_cards: int = 0       # of those, how many are due for review now


class CourseFlashcardsResponse(BaseModel):
    slug: str
    generated_at: str
    decks: List[CourseFlashcardDeck] = []


class FlashcardCardState(BaseModel):
    """One card's review state, aligned by ``index`` to the deck file's order. A card with no
    SM-2 row yet is ``tracked=False`` — never reviewed, so the review page treats it as new."""

    index: int
    tracked: bool = False
    due: bool = False
    reps: int = 0
    lapses: int = 0
    due_at: Optional[str] = None
    last_review_at: Optional[str] = None


class CourseFlashcardStateResponse(BaseModel):
    slug: str
    path: str
    generated_at: str
    cards: List[FlashcardCardState] = []


class FlashcardReviewRequest(BaseModel):
    """The body of ``POST /courses/{slug}/flashcards/review`` — one self-graded card. ``index``
    is the card's position in the deck file; the server derives the stable card key from the
    card's front text, so identity never comes from the client."""

    index: int
    rating: str  # "again" | "hard" | "good"


class CourseAssessmentRequest(BaseModel):
    """The body of ``POST /courses/{slug}/assess`` — a rubric self-assessment. All fields optional;
    an empty ratings map with a note is fine (it still records that the project was attempted)."""

    self_rating: Optional[int] = None
    ratings: Dict[str, str] = {}
    note: str = ""


class CourseNextItem(BaseModel):
    """One ranked "what to do next" action for a course (M3). ``kind`` drives the CTA:
    ``quiz_review``/``quiz_new`` link to the player (``path``); ``lesson``/``project`` point at the
    lesson card (``lesson_id``)."""

    kind: str  # "quiz_review" | "flashcards_review" | "lesson" | "quiz_new" | "project"
    title: str
    reason: str
    module_id: Optional[str] = None
    lesson_id: Optional[str] = None
    path: Optional[str] = None


class CourseNextResponse(BaseModel):
    slug: str
    generated_at: str
    all_done: bool = False  # course has lessons and nothing is currently actionable
    items: List[CourseNextItem] = []


class CourseObjectivesUpdate(BaseModel):
    """The body of ``PUT /courses/{slug}/lessons/{id}/objectives`` (M5). Blank entries are
    dropped server-side; an empty list is allowed (the validator just warns)."""

    objectives: List[str] = []


class CourseOrderModule(BaseModel):
    """One module's place in a reorder: its id + the complete order of its lesson ids."""

    id: str
    lessons: List[str] = []


class CourseOrderUpdate(BaseModel):
    """The body of ``PUT /courses/{slug}/order`` — the COMPLETE desired order: every module id
    exactly once, and per module every one of its lesson ids exactly once (a bijection; moving
    a lesson between modules is out of M5's scope)."""

    modules: List[CourseOrderModule] = []


class CourseEditResponse(BaseModel):
    """The outcome of an M5 structural edit. ``ok=False`` means validation failed and the
    course was rolled back untouched — ``errors`` say why."""

    ok: bool
    errors: List[str] = []
    warnings: List[str] = []


class CourseRegenRequest(BaseModel):
    """The body of ``POST /courses/{slug}/lessons/{id}/regenerate`` — ONE file-backed material
    (``path`` must be declared by that lesson), plus optional free-text guidance for the model.
    The UI sequences multiple materials as separate calls."""

    path: str
    guidance: str = ""


class CourseRegenResponse(BaseModel):
    """The outcome of a regeneration. ``ok=False`` + ``errors`` means the model's output failed
    course validation and was rolled back (files untouched); ``error`` is set when the model
    output itself was unusable. Cost fields come from the claude envelope when available."""

    ok: bool
    path: str
    rolled_back: bool = False
    errors: List[str] = []
    warnings: List[str] = []
    error: Optional[str] = None
    count: Optional[int] = None
    duration_ms: Optional[int] = None
    total_cost_usd: Optional[float] = None


# -- learning paths (M8) -------------------------------------------------------

class PathStep(BaseModel):
    """One step in a generated learning path over a NotebookLM topic. ``kind`` drives rendering +
    which axis it feeds. Artifact-backed kinds (audio/read/flashcards/quiz) carry ``artifact_id``
    (a real topic artifact the player launches via the existing routes); glue kinds (intro/bridge/
    reflect/recap) carry the designer's ``body``/``focus`` text. ``completed`` + ``confidence`` are
    merged from the store at read time. Extra fields are preserved so the format can grow."""

    model_config = ConfigDict(extra="allow")
    id: str
    kind: str
    title: str
    focus: Optional[str] = None
    body: Optional[str] = None
    artifact_id: Optional[str] = None
    artifact_type: Optional[str] = None
    estimated_minutes: Optional[int] = None
    completed: bool = False           # merged from path_step_progress (coverage)
    confidence: Optional[int] = None  # merged from path_confidence (1-5 self-rating)


class PathResponse(BaseModel):
    """A topic's learning path + the learner's merged three axes. ``progress_pct`` is coverage
    (steps done); ``mastery`` is SM-2 recall (decayed, from the shared store — the same read as the
    home card, ``None`` until the topic's quiz/flashcards are practiced); ``confidence`` is the mean
    self-rating so far (``None`` until any step is rated)."""

    notebook_id: str
    title: str
    topic: str = ""
    generated_at: str = ""
    generator: str = ""
    steps: List[PathStep] = []
    step_count: int = 0
    completed_steps: int = 0
    progress_pct: int = 0
    mastery: Optional[float] = None
    confidence: Optional[float] = None


class StepComplete(BaseModel):
    completed: bool


class StepConfidence(BaseModel):
    rating: int  # 1-5


class BridgeGradeRequest(BaseModel):
    answer: str


class BridgeGradeResponse(BaseModel):
    """The formative grade of a bridge-check answer. ``ok`` is whether the grade ran (a claude
    hiccup degrades to ok=False + a calm ``error``, never a 500); ``feedback`` is the model's plain
    coaching. The step is marked done on submit regardless (coverage) and a bridge NEVER moves
    mastery; ``path`` is the refreshed three-axis state so the UI updates without a refetch."""

    ok: bool
    feedback: Optional[str] = None
    error: Optional[str] = None
    path: PathResponse


class PathGenerateResponse(BaseModel):
    """The outcome of an on-demand path composition (M8 Designer). ``ok=False`` + a calm ``error``
    means the claude run/parse failed (never a 500); ``errors`` carries validation failures — a
    fabricated artifact id or bad structure — and on ANY failure nothing is written to disk. ``path``
    is the fresh three-axis state on success so the card lights up without a refetch. Cost fields come
    from the claude envelope when available."""

    ok: bool
    error: Optional[str] = None
    errors: List[str] = []
    path: Optional[PathResponse] = None
    total_cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None


class PathSummary(BaseModel):
    """One learning path at a glance for the Plan's **Continue** lane (design decision 6): coverage
    progress + the next step to resume at. ``next_step`` is the first incomplete step (``None`` once
    every step is done). Built from the same coverage store the player writes, so it always agrees
    with the path view. ``confidence`` (the mean self-rating so far, ``None`` until any step is rated)
    isn't used by Continue but feeds Progress's third axis (M8 #13) — kept here so both lanes read one
    list endpoint rather than an N+1 per-path fetch."""

    notebook_id: str
    title: str
    topic: str = ""
    step_count: int = 0
    completed_steps: int = 0
    progress_pct: int = 0
    next_step: Optional[PathStep] = None
    confidence: Optional[float] = None  # mean self-rating so far, from path_confidence (Progress axis)


class PathsResponse(BaseModel):
    """All composed learning paths with their resume point — feeds the Plan **Continue** lane
    (coverage-driven, non-empty day one via the bundled example path). A malformed path file is
    skipped, never a 500 (the manifest-list posture)."""

    generated_at: str
    items: List[PathSummary] = []


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
    # FR13: the digest as this story read on first_seen day, verbatim from that day's sweep
    # file — the deterministic "what changed" comparator behind the badge and in the chat
    # prompt. None when the first appearance had no digest or the lookup failed.
    prior_digest: Optional[str] = None
    # Calibrated Doubt v0: the optional wager lane — a falsifiable call that this story
    # shows fresh movement by the topic's next sweep, with its stated confidence (1–99).
    # Set only when the sweep made a well-formed call; graded the next morning into the
    # calibration ledger. None otherwise (and on pre-calibration SW-cached payloads).
    prediction: Optional[str] = None
    confidence: Optional[int] = None


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


class BriefMissingTopic(BaseModel):
    """An active roster topic that produced no renderable file for the served day (QU12) —
    named on the page so a crashed topic is visible instead of just absent."""

    slug: str
    title: str


class BriefAudioChapter(BaseModel):
    """FR4: one seek chip over the narrated mp3. start_seconds is a deterministic
    word-count estimate from sweeps/audio_brief.py — a landmark, not a measured timing."""

    slug: str
    title: str
    start_seconds: float


class BriefMirrorAttention(BaseModel):
    """One slice of the Mirror's attention split — this topic/category's share of every
    keyed signal (notes + asks + news events) in the window."""

    slug: str
    title: str
    events: int
    share_pct: int


class BriefMirror(BaseModel):
    """Mirror v0 (docs/ideas/the-mirror.md): a deterministic 'You this week' read over the
    last 7 LOCAL days of logged behavior — no LLM, no writes, no stored profile.
    ``sufficient=False`` is the honest cold start: counts still carried, sentence empty,
    nothing extrapolated from a handful of data points."""

    generated_at: str
    window_days: int = 7
    sufficient: bool = False
    sentence: str = ""
    mornings: int = 0
    notes: int = 0
    asks: int = 0
    news_events: int = 0
    attention: List[BriefMirrorAttention] = []
    paused_topics: List[str] = []


class BriefReadinessItem(BaseModel):
    """One projected trajectory on the 'Coming up' strip (readiness v0): a story on the
    served morning that has appeared on prior mornings in the dedup window. Identity is
    the same normalized headline/source-URL match that sets the developing badge, so the
    strip and the badge can never disagree; ``days_seen`` counts distinct mornings
    including the served one, ``item_id`` is the served item's read-time anchor."""

    slug: str
    title: str
    item_id: str
    headline: str
    days_seen: int
    first_seen: str


class BriefReadiness(BaseModel):
    """Readiness v0 (docs/ideas/readiness-brief.md): the deterministic 'Coming up' forward
    projection over in-repo sweep history — which of the morning's stories are still in
    motion. No LLM, no writes; ``sufficient=False`` is the honest cold start (fewer than
    two prior renderable mornings in the window): nothing projected from thin history,
    ``history_days`` says why."""

    generated_at: str
    window_days: int = 7
    history_days: int = 0
    sufficient: bool = False
    items: List[BriefReadinessItem] = []


class BriefCalibrationCall(BaseModel):
    """One graded wager on the 'Yesterday's calls' strip (Calibrated Doubt v0): the
    morning it was made, the falsifiable call, the stated confidence, and the
    deterministic outcome — did the story show fresh movement by the topic's next
    readable sweep (the developing badge's own identity-key join)."""

    slug: str
    title: str
    day: str
    headline: str
    prediction: str
    confidence: int
    outcome: bool


class BriefCalibration(BaseModel):
    """Calibrated Doubt v0 (docs/ideas/calibrated-doubt.md): the running public
    calibration record behind the strip — recomputed each serve from the append-only
    backend/data/calibration.jsonl. ``trial`` is the assumption-4 gate made visible:
    true until a week of distinct graded mornings is on the books, so the new wager
    lane is labelled untrusted instead of silently worn as proven."""

    generated_at: str
    window_days: int = 7
    resolved: int = 0
    hits: int = 0
    days: int = 0
    brier: Optional[float] = None
    trial: bool = True
    yesterday: List[BriefCalibrationCall] = []


class BriefOvernightProposal(BaseModel):
    """One draft-only proposal on the Overnight queue (v0): a note the nightly pass
    drafted onto the served day's item. Nothing was sent or executed — approve lands
    ``body`` through the existing notes path (``note_id`` is the result), discard is
    the undo. Resolution is single-shot: proposed → approved | discarded, never back."""

    id: str
    type: str = "draft_note"
    slug: str
    title: str = ""
    item_id: str
    item_headline: str
    body: str
    status: str = "proposed"
    note_id: Optional[int] = None
    created_at: str = ""


class BriefOvernight(BaseModel):
    """Overnight Chief of Staff v0 (docs/ideas/overnight-chief-of-staff.md): the
    draft-only after-action queue reduced from backend/data/overnight.jsonl — what the
    nightly pass prepared from in-repo data, wearing each proposal's resolution. Scope
    decisions (2026-07-20 gate): in-repo data only, v0 sends/executes nothing, the
    approve/undo queue itself is the acting surface's gate."""

    generated_at: str
    date: str
    proposals: List[BriefOvernightProposal] = []


class BriefResponse(BaseModel):
    generated_at: str
    has_data: bool = False
    date: Optional[str] = None  # YYYY-MM-DD of the latest sweep folder being served
    topics: List[BriefTopic] = []
    # M4: data/sweeps/<date>/brief.mp3 exists for the served day — GET /brief/audio streams it.
    audio_available: bool = False
    # FR4: seek offsets from the day's brief.chapters.json — only populated when
    # audio_available is true (chapters beside a failed render stay invisible); any file
    # problem degrades to [] — chips are a bonus, never a 500.
    audio_chapters: List[BriefAudioChapter] = []
    # QU12: active (non-paused) roster topics missing from the served day, roster order.
    # Empty when there's no served day at all — has_data=false already tells that story.
    missing_topics: List[BriefMissingTopic] = []
    # QU1: the served day's renderable neighbors — the archive's prev/next walk. None at
    # either edge (or when there's no served day).
    prev_date: Optional[str] = None
    next_date: Optional[str] = None
    # Mirror v0: the 'You this week' self-read — LIVE view only (None on ?date= archive
    # payloads; absent from pre-Mirror SW-cached payloads, so the TS side keeps it optional).
    mirror: Optional[BriefMirror] = None
    # Readiness v0: the 'Coming up' projection for the served morning — LIVE view only
    # (None on ?date= archives and when there's no served day; absent from pre-readiness
    # SW-cached payloads, so the TS side keeps it optional).
    readiness: Optional[BriefReadiness] = None
    # Calibrated Doubt v0: the graded-wager record ('Yesterday's calls') — LIVE view only
    # (grading happens at serve time; an archived ?date= morning is a record, not a
    # grader). Absent from pre-calibration SW-cached payloads, so the TS side keeps it
    # optional.
    calibration: Optional[BriefCalibration] = None
    # Overnight v0: the draft-only approve/discard queue — LIVE view only (an archived
    # ?date= morning is a record, not a to-do list). Absent from pre-overnight SW-cached
    # payloads, so the TS side keeps it optional.
    overnight: Optional[BriefOvernight] = None


class BriefVisitResponse(BaseModel):
    ok: bool = True
    day: str
    visited_at: str


class BriefSweepResponse(BaseModel):
    """FR2: the phone's stale-morning tap. ``started`` = a detached sweep.sh was just
    spawned; ``already_running`` = the tap was an honest no-op because one is in flight
    (the 06:00 lane or an earlier tap). Never both true."""

    started: bool
    already_running: bool


class BriefHabitWeek(BaseModel):
    """One local Monday-start week of the kickoff's habit metrics: ``mornings`` = distinct
    days the Today page was opened (v1 target ≥5/week), ``notes`` = brief notes attached
    (target ≥3/week)."""

    week_start: str  # Monday, YYYY-MM-DD, local calendar
    mornings: int = 0
    notes: int = 0


class BriefHabitResponse(BaseModel):
    generated_at: str
    weeks: List[BriefHabitWeek] = []  # oldest first; the last entry is the current week
    # PR5 sweep-trust gauge: newest `## YYYY-MM-DD` heading in docs/sweep-trust-log.md —
    # the last manual accuracy re-grade. None when the log is missing or has no entries.
    last_graded: Optional[str] = None


class BriefChatRequest(BaseModel):
    """One follow-up question about a served brief item (M5). The item_id is date-scoped
    (sha1(date|slug|headline)), so a stale tab's question naturally 404s after rollover."""

    item_id: str
    topic_slug: str
    question: str


class BriefChatResponse(BaseModel):
    answer: str  # markdown, grounded in the served item — ephemeral unless saved as a note


# -- news mode (M7) --------------------------------------------------------------


class NewsItem(BaseModel):
    """One real article from a Google News RSS feed — ``url`` is a Google redirect link
    that opens the original piece. Text-first: the feeds carry no images."""

    id: str  # sha1(link)[:12] — stable across refetches, Phase 2's event anchor
    headline: str
    url: str
    source: Optional[str] = None
    published_at: Optional[str] = None  # UTC ISO 8601; None when the feed omitted it


class NewsCategory(BaseModel):
    slug: str
    title: str


class NewsCategoriesResponse(BaseModel):
    generated_at: str
    categories: List[NewsCategory] = []  # display order = sweeps/news_categories.json order


class NewsCategoryResponse(BaseModel):
    generated_at: str
    slug: str
    title: str
    fetched_at: Optional[str] = None  # when this payload was pulled from Google News
    stale: bool = False  # True = refresh failed, serving the expired cache honestly
    items: List[NewsItem] = []


class NewsEventCreate(BaseModel):
    """One For-You signal (M7 Phase 2): click | visit | more_like | not_interested.
    Item-scoped kinds carry the item snapshot — the feed cache rolls over in minutes,
    so the profile builder can't join back to it later."""

    kind: str
    category_slug: str
    item_id: Optional[str] = None
    headline: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None


class NewsEventResponse(BaseModel):
    ok: bool = True
    id: int
    created_at: str


class ForYouItem(NewsItem):
    """A ranked item plus where it came from — a section slug, or ``search:<term>``
    when the profile pulled it from beyond the standard categories (M7 Phase 3)."""

    category_slug: Optional[str] = None


class NewsTopicSuggestion(BaseModel):
    """A topic-scout find (M7 Phase 4): a persistent interest the morning brief doesn't
    cover yet, with the evidence the card shows."""

    term: str
    score: float
    days_seen: int
    example_headlines: List[str] = []


class NewsForYouResponse(BaseModel):
    generated_at: str
    learning: bool  # cold start: fewer than the threshold of positive signals so far
    event_count: int  # positive signals collected — the page shows progress toward warm
    items: List[ForYouItem] = []
    suggestions: List[NewsTopicSuggestion] = []  # the Mode-A bridge, dismissible


class NewsSuggestionActionRequest(BaseModel):
    term: str


class NewsSuggestionAddResponse(BaseModel):
    ok: bool = True
    slug: str  # the roster entry the next 06:00 sweep will pick up
    title: str


class NewsSuggestionDismissResponse(BaseModel):
    ok: bool = True
    term: str  # normalized (lowercased) — never suggested again


# -- study scheduler (v0) ------------------------------------------------------

class StudyBlockStep(BaseModel):
    """One path step packed inside a proposed study block (for display in the review view)."""

    id: str
    kind: str = ""
    title: str = ""
    minutes: int = 0


class ProposedBlock(BaseModel):
    """One study block the planner proposes (nothing is written until confirm). ``start``/``end`` are
    RFC3339 with a CT offset; ``step_ids`` are the path steps this session covers. Echoed back
    verbatim on confirm (the client may drop some) so the write is exactly what Kyle reviewed."""

    start: str
    end: str
    minutes: int
    title: str = ""
    step_ids: List[str] = []
    steps: List[StudyBlockStep] = []


class WrittenBlock(BaseModel):
    """A study block that WAS written to the calendar — carries its Google ``event_id`` +
    ``calendar_id`` so it stays cleanly removable (the feature's one hard rule)."""

    id: int
    step_id: str
    title: str
    start: str
    end: str
    event_id: str
    calendar_id: str
    status: str = "written"


class StudyScheduleState(BaseModel):
    """The per-path scheduler state: the opt-in flag + session length, whether the calendar is
    connected, and the live (written, not removed) blocks."""

    track_kind: str = "path"
    track_id: str
    enabled: bool = False
    session_minutes: int = 45
    connected: bool = False
    calendar_id: Optional[str] = None
    blocks: List[WrittenBlock] = []


class StudyProposal(BaseModel):
    """The proposed set of blocks (read-only — writes nothing). ``connected=False`` means the
    calendar isn't wired yet (honest 'connect' state, never a 500); ``message`` is the optional
    negotiation line; ``unscheduled_step_ids`` are steps that didn't fit the window."""

    ok: bool
    connected: bool
    session_minutes: int
    blocks: List[ProposedBlock] = []
    unscheduled_step_ids: List[str] = []
    message: Optional[str] = None
    error: Optional[str] = None
    total_cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None


class StudyOptInRequest(BaseModel):
    enabled: bool
    session_minutes: Optional[int] = None  # kept if omitted


class StudyProposeRequest(BaseModel):
    preference: Optional[str] = None  # free-text -> the claude -p negotiation lane
    session_minutes: Optional[int] = None
    days: Optional[int] = None


class StudyConfirmRequest(BaseModel):
    blocks: List[ProposedBlock] = []  # the reviewed set to write (a subset of the proposal is fine)


class StudyRemoveRequest(BaseModel):
    block_ids: Optional[List[int]] = None  # a subset, or None to remove every live block
