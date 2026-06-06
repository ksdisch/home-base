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


class HealthResponse(BaseModel):
    ok: bool = True
    nlm_available: bool = False
    nlm_version: Optional[str] = None
    notebooklm_root: str
    root_exists: bool


class EpisodeToggle(BaseModel):
    listened: bool
