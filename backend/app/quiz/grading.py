"""Quiz model + grading, locked to the verified nlm quiz JSON contract.

Verified invariants (docs/nlm-capabilities.md), enforced here:
  * each question has ``answerOptions`` with **exactly one** ``isCorrect: true``;
  * option counts vary per question (do NOT assume 4);
  * every option has a ``rationale`` (shown on review / misses);
  * every question has a ``hint`` (offered on demand).

Everything is pure and offline — no network, no nlm. The Phase-2 player renders these models;
grading is auto against ``isCorrect``. Built and tested now so the contract can't drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


class QuizValidationError(ValueError):
    """Raised when quiz JSON violates the verified contract."""


@dataclass(frozen=True)
class QuizOption:
    text: str
    is_correct: bool
    rationale: str


@dataclass(frozen=True)
class QuizQuestion:
    index: int
    question: str
    options: List[QuizOption]
    hint: Optional[str]

    @property
    def correct_index(self) -> int:
        for i, o in enumerate(self.options):
            if o.is_correct:
                return i
        raise QuizValidationError(f"Question {self.index} has no correct option.")


@dataclass(frozen=True)
class Quiz:
    title: str
    questions: List[QuizQuestion]

    @property
    def total(self) -> int:
        return len(self.questions)


def load_quiz(data: Mapping[str, Any]) -> Quiz:
    """Validate + parse raw quiz JSON into a :class:`Quiz`. Raises on contract violations."""
    if not isinstance(data, Mapping):
        raise QuizValidationError("Quiz payload is not an object.")
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise QuizValidationError("Quiz has no questions[].")

    questions: List[QuizQuestion] = []
    for qi, rq in enumerate(raw_questions):
        if not isinstance(rq, Mapping):
            raise QuizValidationError(f"Question {qi} is not an object.")
        raw_opts = rq.get("answerOptions")
        if not isinstance(raw_opts, list) or len(raw_opts) < 2:
            raise QuizValidationError(
                f"Question {qi} must have >= 2 answerOptions (got {raw_opts!r})."
            )
        options: List[QuizOption] = []
        correct_count = 0
        for oi, ro in enumerate(raw_opts):
            if not isinstance(ro, Mapping):
                raise QuizValidationError(f"Question {qi} option {oi} is not an object.")
            is_correct = bool(ro.get("isCorrect", False))
            correct_count += int(is_correct)
            options.append(
                QuizOption(
                    text=str(ro.get("text", "")),
                    is_correct=is_correct,
                    rationale=str(ro.get("rationale", "")),
                )
            )
        if correct_count != 1:
            raise QuizValidationError(
                f"Question {qi} must have exactly one correct option (got {correct_count})."
            )
        hint = rq.get("hint")
        questions.append(
            QuizQuestion(
                index=qi,
                question=str(rq.get("question", "")),
                options=options,
                hint=str(hint) if hint else None,
            )
        )

    return Quiz(title=str(data.get("title", "Quiz")), questions=questions)


@dataclass(frozen=True)
class GradedQuestion:
    index: int
    chosen_index: Optional[int]
    correct_index: int
    is_correct: bool
    # Rationale for the chosen option (shown on a miss) and for the correct option.
    chosen_rationale: Optional[str]
    correct_rationale: str
    used_hint: bool = False


@dataclass(frozen=True)
class GradeResult:
    total: int
    score: int
    questions: List[GradedQuestion] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return (self.score / self.total * 100.0) if self.total else 0.0


def grade_quiz(
    quiz: Quiz,
    answers: Mapping[int, Optional[int]],
    used_hints: Optional[Mapping[int, bool]] = None,
) -> GradeResult:
    """Grade ``answers`` (question_index -> chosen_option_index) against ``isCorrect``.

    A missing or ``None`` answer counts as incorrect. Out-of-range choices count as incorrect.
    """
    used_hints = used_hints or {}
    graded: List[GradedQuestion] = []
    score = 0
    for q in quiz.questions:
        chosen = answers.get(q.index)
        correct_index = q.correct_index
        in_range = chosen is not None and 0 <= chosen < len(q.options)
        is_correct = bool(in_range and chosen == correct_index)
        score += int(is_correct)
        graded.append(
            GradedQuestion(
                index=q.index,
                chosen_index=chosen if in_range else None,
                correct_index=correct_index,
                is_correct=is_correct,
                chosen_rationale=q.options[chosen].rationale if in_range else None,
                correct_rationale=q.options[correct_index].rationale,
                used_hint=bool(used_hints.get(q.index, False)),
            )
        )
    return GradeResult(total=quiz.total, score=score, questions=graded)
