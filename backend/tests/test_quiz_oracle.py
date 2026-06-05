"""Offline quiz oracle — runs entirely against the fixture, zero network/nlm."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.quiz import QuizValidationError, grade_quiz, load_quiz

FIXTURE = Path(__file__).resolve().parent.parent.parent / "docs" / "fixtures" / "sample-quiz.json"


def _fixture():
    return json.loads(FIXTURE.read_text())


def test_fixture_loads_and_matches_verified_invariants():
    quiz = load_quiz(_fixture())
    assert quiz.title == "Ep 1 — Quiz"
    assert quiz.total == 10
    # Exactly one correct option per question; option counts vary (one has 2, not 4).
    for q in quiz.questions:
        assert sum(o.is_correct for o in q.options) == 1
        assert q.hint  # every question has a hint
        for o in q.options:
            assert o.rationale  # every option carries a rationale
    assert any(len(q.options) == 2 for q in quiz.questions)  # the 2-option question
    assert any(len(q.options) == 4 for q in quiz.questions)


def test_all_correct_scores_full():
    quiz = load_quiz(_fixture())
    answers = {q.index: q.correct_index for q in quiz.questions}
    result = grade_quiz(quiz, answers)
    assert result.score == result.total == 10
    assert result.pct == 100.0


def test_misses_expose_rationale_and_hint_tracking():
    quiz = load_quiz(_fixture())
    answers = {q.index: next(i for i, o in enumerate(q.options) if not o.is_correct) for q in quiz.questions}
    result = grade_quiz(quiz, answers, used_hints={0: True})
    assert result.score == 0
    g0 = result.questions[0]
    assert g0.is_correct is False
    assert g0.chosen_rationale  # rationale for the wrong pick (shown on a miss)
    assert g0.correct_rationale  # rationale for the right answer
    assert g0.used_hint is True


def test_unanswered_counts_as_incorrect():
    quiz = load_quiz(_fixture())
    result = grade_quiz(quiz, {})  # nothing answered
    assert result.score == 0
    assert all(g.chosen_index is None for g in result.questions)


def test_out_of_range_choice_is_incorrect():
    quiz = load_quiz(_fixture())
    result = grade_quiz(quiz, {0: 999})
    assert result.questions[0].is_correct is False
    assert result.questions[0].chosen_index is None


def test_validation_rejects_zero_correct():
    bad = {"title": "x", "questions": [{"question": "q", "answerOptions": [
        {"text": "a", "isCorrect": False, "rationale": "r"},
        {"text": "b", "isCorrect": False, "rationale": "r"},
    ], "hint": "h"}]}
    with pytest.raises(QuizValidationError):
        load_quiz(bad)


def test_validation_rejects_multiple_correct():
    bad = {"title": "x", "questions": [{"question": "q", "answerOptions": [
        {"text": "a", "isCorrect": True, "rationale": "r"},
        {"text": "b", "isCorrect": True, "rationale": "r"},
    ], "hint": "h"}]}
    with pytest.raises(QuizValidationError):
        load_quiz(bad)
