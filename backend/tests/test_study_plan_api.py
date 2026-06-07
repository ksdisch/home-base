"""Phase-6 /api/study-plan end-to-end, driving real attempts through the quiz API.

Reuses the `test_review_api` harness (same fake-nlm quiz fixture) so the plan reads exactly the
`question_mastery` rows `record_attempt` writes, then back-dates `due_at` to exercise the
"due" path deterministically.
"""

from __future__ import annotations

import pytest

from .test_review_api import _client, _fresh_store, _take_quiz


def _backdate_due(notebook_id: str, days: float) -> None:
    """Age a notebook's questions' `due_at` so they fall due now."""
    from app.store.db import connect

    conn = connect()
    try:
        conn.execute(
            "UPDATE question_mastery SET due_at = datetime(due_at, ?) WHERE notebook_id = ?",
            (f"-{days} days", notebook_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_study_plan_empty_store_degrades_gracefully(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "plan-empty")
    from app.config import get_settings

    try:
        client = _client()
        try:
            body = client.get("/api/study-plan").json()
            assert body["has_data"] is False
            assert body["has_due"] is False
            assert body["segments"] == []
            assert body["total_items"] == 0
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


def test_study_plan_surfaces_due_questions_after_aging(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "plan-due")
    from app.config import get_settings

    try:
        client = _client()
        try:
            _take_quiz(client, "nb-plan")  # fresh pass → scheduled ahead, nothing due yet
            fresh = client.get("/api/study-plan").json()
            assert fresh["has_data"] is True
            assert fresh["has_due"] is False  # just answered → not due

            _backdate_due("nb-plan", 30)  # age the schedule → now overdue
            due = client.get("/api/study-plan").json()
            assert due["has_due"] is True
            assert due["due_items"] >= 1
            seg = next(s for s in due["segments"] if s["notebook_id"] == "nb-plan")
            assert seg["due_count"] >= 1
            assert seg["title"] == "nb-plan"  # unknown notebook → id fallback
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


def test_study_plan_respects_the_minute_budget(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "plan-budget")
    from app.config import get_settings

    try:
        client = _client()
        try:
            _take_quiz(client, "nb-a")
            _take_quiz(client, "nb-b")
            _backdate_due("nb-a", 30)
            _backdate_due("nb-b", 30)
            body = client.get("/api/study-plan?minutes=5").json()  # clamped floor
            assert body["requested_minutes"] == 5
            assert body["total_minutes"] <= 5 + 1e-6
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()
