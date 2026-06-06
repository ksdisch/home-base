"""CLI that backs the ``/episode-review`` skill — the deterministic, persistable half of the
conversational review→quiz→log workflow.

Why a CLI (not just skill prose): the *score* must come from the verified offline grader
(:func:`app.quiz.grading.grade_quiz`), never from the model eyeballing answers — so score
history stays reproducible and trustworthy. The skill orchestrates the conversation; this
module owns fetching, the answer key, grading, and every DB write.

Integrity property enforced here: ``prepare`` emits a **player view** with the answer key AND
the per-option rationales stripped out (a rationale gives the answer away). The full keyed quiz
is written to a session file under the hub cache that only ``grade`` reads — so the model
administering the quiz literally cannot leak the answer.

Subcommands (all speak JSON on stdout for the skill to parse):
  prepare  --notebook ID --quiz ARTIFACT_ID [--episode ARTIFACT_ID] [--from-file PATH]
  grade    --session SESSION_ID --answers JSON [--hints JSON] [--mark-listened]
  reflect  --notebook ID --body TEXT [--episode ARTIFACT_ID] [--grasp N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..config import get_settings
from ..nlm.client import NlmClient
from ..nlm.errors import NlmError
from ..store import init_db, record_attempt, save_reflection
from .grading import QuizValidationError, grade_quiz, load_quiz


def _sessions_dir() -> Path:
    d = get_settings().cache_dir / "review-sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def question_key(text: str) -> str:
    """Stable per-question identity for mastery tracking (survives reordering / re-downloads)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# -- prepare -------------------------------------------------------------------

def cmd_prepare(
    notebook_id: str,
    quiz_artifact_id: str,
    *,
    episode_artifact_id: Optional[str] = None,
    from_file: Optional[str] = None,
    client: Optional[NlmClient] = None,
) -> Dict[str, Any]:
    """Fetch + validate the quiz, stash the keyed copy, return an answer-key-free player view.

    ``client`` lets the HTTP layer inject a DI-overridable ``NlmClient`` (and tests a fake one);
    the CLI leaves it ``None`` and gets a fresh real client.
    """
    if from_file:  # offline / tests — no nlm, no network
        raw = json.loads(Path(from_file).read_text(encoding="utf-8"))
    else:
        raw = (client or NlmClient()).download_quiz(notebook_id, quiz_artifact_id)

    quiz = load_quiz(raw)  # raises QuizValidationError on a contract violation

    session_id = uuid.uuid4().hex
    (_sessions_dir() / f"{session_id}.json").write_text(
        json.dumps(
            {
                "notebook_id": notebook_id,
                "quiz_artifact_id": quiz_artifact_id,
                "episode_artifact_id": episode_artifact_id,
                "raw": raw,  # the KEYED quiz — only `grade` reads this file
            }
        ),
        encoding="utf-8",
    )

    # Player view: question + option TEXT + hint only. No isCorrect, no rationale.
    player_questions = [
        {
            "index": q.index,
            "question": q.question,
            "options": [o.text for o in q.options],
            "hint": q.hint,
        }
        for q in quiz.questions
    ]
    return {
        "session_id": session_id,
        "title": quiz.title,
        "total": quiz.total,
        "notebook_id": notebook_id,
        "quiz_artifact_id": quiz_artifact_id,
        "episode_artifact_id": episode_artifact_id,
        "questions": player_questions,
    }


# -- grade ---------------------------------------------------------------------

def _coerce_int_keys(m: Mapping[Any, Any]) -> Dict[int, Any]:
    """JSON object keys are strings; quiz indices are ints."""
    return {int(k): v for k, v in m.items()}


def cmd_grade(
    session_id: str,
    answers: Mapping[Any, Any],
    *,
    hints: Optional[Mapping[Any, Any]] = None,
    mark_listened: bool = False,
) -> Dict[str, Any]:
    """Grade with the offline oracle, persist the attempt, return a full review payload."""
    session_path = _sessions_dir() / f"{session_id}.json"
    if not session_path.exists():
        raise FileNotFoundError(f"Unknown review session: {session_id}")
    session = json.loads(session_path.read_text(encoding="utf-8"))

    quiz = load_quiz(session["raw"])
    answer_map: Dict[int, Optional[int]] = {
        k: (int(v) if v is not None else None) for k, v in _coerce_int_keys(answers).items()
    }
    hint_map: Dict[int, bool] = {
        k: bool(v) for k, v in _coerce_int_keys(hints or {}).items()
    }

    result = grade_quiz(quiz, answer_map, used_hints=hint_map)

    # Build the persistence rows + the human-facing review in one pass over the questions.
    attempt_rows = []
    review = []
    for q, g in zip(quiz.questions, result.questions):
        qkey = question_key(q.question)
        attempt_rows.append(
            {
                "question_index": g.index,
                "question_key": qkey,
                "chosen_index": g.chosen_index,
                "correct": g.is_correct,
                "used_hint": g.used_hint,
            }
        )
        review.append(
            {
                "index": g.index,
                "question": q.question,
                "options": [o.text for o in q.options],
                "chosen_index": g.chosen_index,
                "chosen_text": (
                    q.options[g.chosen_index].text if g.chosen_index is not None else None
                ),
                "correct_index": g.correct_index,
                "correct_text": q.options[g.correct_index].text,
                "is_correct": g.is_correct,
                "used_hint": g.used_hint,
                "chosen_rationale": g.chosen_rationale,
                "correct_rationale": g.correct_rationale,
            }
        )

    attempt_id = record_attempt(
        session["notebook_id"],
        session["quiz_artifact_id"],
        score=result.score,
        total=result.total,
        answers=attempt_rows,
        episode_artifact_id=session.get("episode_artifact_id"),
        mark_listened=mark_listened,
    )

    return {
        "attempt_id": attempt_id,
        "score": result.score,
        "total": result.total,
        "pct": round(result.pct, 1),
        "episode_marked_listened": bool(mark_listened and session.get("episode_artifact_id")),
        "review": review,
    }


# -- reflect -------------------------------------------------------------------

def cmd_reflect(
    notebook_id: str,
    body: str,
    *,
    episode_artifact_id: Optional[str] = None,
    grasp_rating: Optional[int] = None,
) -> Dict[str, Any]:
    reflection_id = save_reflection(
        notebook_id,
        body,
        episode_artifact_id=episode_artifact_id,
        grasp_rating=grasp_rating,
    )
    return {"reflection_id": reflection_id}


# -- CLI plumbing --------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="episode-review", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("prepare", help="fetch+validate a quiz, return an answer-key-free view")
    pp.add_argument("--notebook", required=True)
    pp.add_argument("--quiz", required=True, help="quiz artifact id")
    pp.add_argument("--episode", default=None, help="source episode artifact id (for the ✓)")
    pp.add_argument("--from-file", default=None, help="load quiz JSON from a file (offline)")

    pg = sub.add_parser("grade", help="grade answers, persist the attempt, return the review")
    pg.add_argument("--session", required=True)
    pg.add_argument("--answers", required=True, help='JSON {"<q_index>": <option_index|null>}')
    pg.add_argument("--hints", default="{}", help='JSON {"<q_index>": true} for hinted questions')
    pg.add_argument("--mark-listened", action="store_true", help="mark the source episode ✓")

    pr = sub.add_parser("reflect", help="save a post-episode reflection")
    pr.add_argument("--notebook", required=True)
    pr.add_argument("--body", required=True)
    pr.add_argument("--episode", default=None)
    pr.add_argument("--grasp", type=int, default=None, help="optional self-rating 1-5")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    init_db()  # idempotent; guarantees the tables exist before any write
    try:
        if args.cmd == "prepare":
            out = cmd_prepare(
                args.notebook, args.quiz,
                episode_artifact_id=args.episode, from_file=args.from_file,
            )
        elif args.cmd == "grade":
            out = cmd_grade(
                args.session, json.loads(args.answers),
                hints=json.loads(args.hints), mark_listened=args.mark_listened,
            )
        else:  # reflect
            out = cmd_reflect(
                args.notebook, args.body,
                episode_artifact_id=args.episode, grasp_rating=args.grasp,
            )
    except (NlmError, QuizValidationError, FileNotFoundError) as e:
        # Friendly, machine-readable failure (e.g. auth → the skill says "run nlm login").
        kind = type(e).__name__
        print(json.dumps({"error": str(e), "kind": kind}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
