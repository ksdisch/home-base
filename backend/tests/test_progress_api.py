"""Phase-3 progress dashboard: the pure streak math, the empty-store degrade, and the full
summary→trend→shaky payload driven through real attempts created via the quiz API (so the
read layer is exercised against the same rows `record_attempt` actually writes)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.store.progress import compute_streaks

SAMPLE_QUIZ = Path(__file__).resolve().parents[2] / "docs" / "fixtures" / "sample-quiz.json"


# -- pure streak math ----------------------------------------------------------

def test_streaks_empty_is_zero():
    assert compute_streaks([], date(2026, 6, 6)) == (0, 0)


def test_streak_today_anchored_run_counts_as_current():
    days = ["2026-06-04", "2026-06-05", "2026-06-06"]
    assert compute_streaks(days, date(2026, 6, 6)) == (3, 3)


def test_streak_yesterday_anchored_still_current():
    days = ["2026-06-04", "2026-06-05"]
    assert compute_streaks(days, date(2026, 6, 6)) == (2, 2)


def test_lapsed_streak_has_no_current_but_keeps_longest():
    # Longest run is 3 days but it ended a week before "today".
    days = ["2026-05-28", "2026-05-29", "2026-05-30", "2026-06-02"]
    current, longest = compute_streaks(days, date(2026, 6, 6))
    assert current == 0
    assert longest == 3


def test_streak_dedupes_and_ignores_order():
    days = ["2026-06-06", "2026-06-06", "2026-06-05", "2026-06-04", "2026-06-04"]
    assert compute_streaks(days, date(2026, 6, 6)) == (3, 3)


# -- HTTP route ----------------------------------------------------------------

def _runner_serving_quiz(args):
    from app.nlm import NlmResult

    return NlmResult(
        args=list(args), stdout=SAMPLE_QUIZ.read_text(encoding="utf-8"), stderr="", returncode=0
    )


def _client(runner=_runner_serving_quiz):
    from fastapi.testclient import TestClient

    from app.deps import get_nlm_client
    from app.main import app
    from app.nlm import NlmClient

    app.dependency_overrides[get_nlm_client] = lambda: NlmClient(runner=runner)
    return TestClient(app)


def _answer_key() -> dict[int, int]:
    data = json.loads(SAMPLE_QUIZ.read_text(encoding="utf-8"))
    key = {}
    for qi, q in enumerate(data["questions"]):
        for oi, opt in enumerate(q["answerOptions"]):
            if opt["isCorrect"]:
                key[qi] = oi
    return key


def _take_quiz(client, notebook_id="nb-prog", *, miss_first=False) -> dict:
    """Drive a real prepare→grade cycle so the store gets genuine attempt/activity rows."""
    sid = client.post(
        f"/api/topics/{notebook_id}/quizzes/quiz-1/prepare"
    ).json()["session_id"]
    key = _answer_key()
    answers = dict(key)
    if miss_first:
        answers[0] = next(i for i in range(4) if i != key[0])
    return client.post("/api/quiz/grade", json={"session_id": sid, "answers": answers}).json()


def test_progress_empty_store_degrades_gracefully(tmp_path, monkeypatch):
    # Isolate to a fresh DB so "empty" is real even after other tests in the session.
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "empty-hub"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()  # fresh isolated store — create the schema (empty)
    try:
        client = _client()
        try:
            r = client.get("/api/progress")
            assert r.status_code == 200
            body = r.json()
            assert body["has_data"] is False
            assert body["summary"]["attempts_total"] == 0
            assert body["summary"]["current_streak"] == 0
            assert body["topics"] == []
            assert body["shaky"] == []
            # Activity strip is dense even when empty (one zero cell per day).
            assert len(body["activity"]) == 35
            assert all(a["count"] == 0 for a in body["activity"])
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


def test_progress_reports_attempts_trend_and_shaky(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "live-hub"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()  # fresh isolated store
    try:
        client = _client()
        try:
            full = _take_quiz(client, "nb-prog")  # all correct
            _take_quiz(client, "nb-prog", miss_first=True)  # one miss
            total = full["total"]

            body = client.get("/api/progress").json()
            assert body["has_data"] is True

            s = body["summary"]
            assert s["attempts_total"] == 2
            assert s["topics_practiced"] == 1
            assert s["current_streak"] >= 1  # both attempts are "today"

            topic = next(t for t in body["topics"] if t["notebook_id"] == "nb-prog")
            assert topic["attempts"] == 2
            assert topic["best_pct"] == 100.0
            # Last attempt missed one question → last_pct below best.
            assert topic["last_pct"] == pytest.approx(round(100.0 * (total - 1) / total, 1))
            assert len(topic["points"]) == 2
            # Unknown notebook → label falls back to the id.
            assert topic["title"] == "nb-prog"

            shaky = next(x for x in body["shaky"] if x["notebook_id"] == "nb-prog")
            assert shaky["total_misses"] >= 1
            assert shaky["shaky_questions"] >= 1
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()
