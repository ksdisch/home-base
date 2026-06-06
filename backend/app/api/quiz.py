"""Quiz player API — the thin HTTP layer over the verified, integrity-preserving session logic.

`prepare` downloads + validates the quiz, stashes the *keyed* copy server-side, and returns an
**answer-key-free** player view (so the client literally can't see the answers). `grade` runs the
offline oracle against the stashed quiz, persists the attempt, and only THEN returns rationales.
Both delegate to `app.quiz.session` so the answer key never leaves the backend.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_nlm_client
from ..models import (
    QuizGradeRequest,
    QuizGradeResponse,
    QuizPrepareResponse,
)
from ..nlm import NlmAuthError, NlmClient, NlmError
from ..quiz.grading import QuizValidationError
from ..quiz.session import cmd_grade, cmd_prepare

router = APIRouter()


@router.post(
    "/topics/{notebook_id}/quizzes/{artifact_id}/prepare",
    response_model=QuizPrepareResponse,
)
def prepare_quiz(
    notebook_id: str,
    artifact_id: str,
    episode_artifact_id: str | None = None,
    nlm: NlmClient = Depends(get_nlm_client),
) -> QuizPrepareResponse:
    """Fetch + validate a quiz and hand back an answer-key-free player view.

    Never a 500: an `nlm` sign-in lapse degrades to a calm "run `nlm login`" auth banner, and a
    download/contract failure to a calm error string — the player renders the banner, not a crash.
    """
    try:
        out = cmd_prepare(
            notebook_id,
            artifact_id,
            episode_artifact_id=episode_artifact_id,
            client=nlm,
        )
    except NlmAuthError as e:
        return QuizPrepareResponse(
            notebook_id=notebook_id,
            quiz_artifact_id=artifact_id,
            episode_artifact_id=episode_artifact_id,
            ok=False,
            auth={"ok": False, "message": e.user_message},
        )
    except (NlmError, QuizValidationError) as e:
        msg = getattr(e, "user_message", None) or str(e)
        return QuizPrepareResponse(
            notebook_id=notebook_id,
            quiz_artifact_id=artifact_id,
            episode_artifact_id=episode_artifact_id,
            ok=False,
            error=f"Couldn't load this quiz: {msg}",
        )
    return QuizPrepareResponse(ok=True, **out)


@router.post("/quiz/grade", response_model=QuizGradeResponse)
def grade_quiz_attempt(body: QuizGradeRequest) -> QuizGradeResponse:
    """Grade a prepared session, persist the attempt, and return the per-question review."""
    try:
        out = cmd_grade(
            body.session_id,
            body.answers,
            hints=body.hints,
            mark_listened=body.mark_listened,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="This quiz session has expired — reopen the quiz to start a fresh attempt.",
        )
    return QuizGradeResponse(**out)
