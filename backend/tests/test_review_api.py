"""Phase-4 "Review next" queue, end-to-end over the HTTP route.

Drives real attempts through the quiz API (same harness as `test_progress_api`) so the queue
reads the exact rows `record_attempt` writes, then back-dates ``last_review_at`` in the store to
exercise the decay → "due" transition deterministically (no time-travel in the route itself).
Also checks the home catalog badge (`due_for_review` / `mastery`) gets stamped from the store.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import uid, write_notebook

SAMPLE_QUIZ = Path(__file__).resolve().parents[2] / "docs" / "fixtures" / "sample-quiz.json"


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


def _take_quiz(client, notebook_id, *, miss_first=False) -> dict:
    sid = client.post(f"/api/topics/{notebook_id}/quizzes/quiz-1/prepare").json()["session_id"]
    key = _answer_key()
    answers = dict(key)
    if miss_first:
        answers[0] = next(i for i in range(4) if i != key[0])
    return client.post("/api/quiz/grade", json={"session_id": sid, "answers": answers}).json()


def _backdate(notebook_id: str, days: float) -> None:
    """Age a topic's (and its questions') last_review_at by ``days`` in the store."""
    from app.store.db import connect

    conn = connect()
    try:
        shift = f"-{days} days"
        conn.execute(
            "UPDATE topic_mastery SET last_review_at = datetime(last_review_at, ?) "
            "WHERE notebook_id = ?",
            (shift, notebook_id),
        )
        conn.execute(
            "UPDATE question_mastery SET last_review_at = datetime(last_review_at, ?) "
            "WHERE notebook_id = ?",
            (shift, notebook_id),
        )
        conn.commit()
    finally:
        conn.close()


def _fresh_store(tmp_path, monkeypatch, name: str):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()


# -- empty store ---------------------------------------------------------------

def test_review_empty_store_degrades_gracefully(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "empty-hub")
    from app.config import get_settings

    try:
        client = _client()
        try:
            r = client.get("/api/review")
            assert r.status_code == 200
            body = r.json()
            assert body["has_data"] is False
            assert body["due_count"] == 0
            assert body["items"] == []
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


# -- decay → due transition ----------------------------------------------------

def test_fresh_attempt_is_not_due_but_ages_into_the_queue(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "aging-hub")
    from app.config import get_settings
    from app.store import mastery as m

    try:
        client = _client()
        try:
            _take_quiz(client, "nb-aging")  # all correct, reviewed "now"

            body = client.get("/api/review").json()
            assert body["has_data"] is True
            item = next(i for i in body["items"] if i["notebook_id"] == "nb-aging")
            # Aced + just reviewed → high retention, not yet due.
            assert item["mastery"] == pytest.approx(1.0)
            assert item["decayed"] > m.DUE_THRESHOLD
            assert item["due"] is False
            assert item["title"] == "nb-aging"  # unknown notebook → id fallback

            # Let it fade well past the half-life → it should now be due and surface.
            _backdate("nb-aging", 4 * m.HALF_LIFE_DAYS)
            body2 = client.get("/api/review").json()
            item2 = next(i for i in body2["items"] if i["notebook_id"] == "nb-aging")
            assert item2["due"] is True
            assert item2["decayed"] < m.DUE_THRESHOLD
            assert body2["due_count"] >= 1
            assert item2["days_since_review"] == pytest.approx(4 * m.HALF_LIFE_DAYS, abs=1.0)
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


def test_shaky_topic_outranks_a_clean_one_at_equal_age(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch, "rank-hub")
    from app.config import get_settings
    from app.store import mastery as m

    try:
        client = _client()
        try:
            _take_quiz(client, "nb-clean")             # all correct
            _take_quiz(client, "nb-shaky", miss_first=True)  # one miss
            # Age both equally so retention is comparable; misses should be the tiebreaker.
            _backdate("nb-clean", 3 * m.HALF_LIFE_DAYS)
            _backdate("nb-shaky", 3 * m.HALF_LIFE_DAYS)

            items = client.get("/api/review").json()["items"]
            order = [i["notebook_id"] for i in items]
            assert order.index("nb-shaky") < order.index("nb-clean")

            shaky = next(i for i in items if i["notebook_id"] == "nb-shaky")
            assert shaky["total_misses"] >= 1
            assert shaky["shaky_questions"] >= 1
            assert "miss" in shaky["reason"]
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()


# -- home catalog badge --------------------------------------------------------

def test_catalog_stamps_due_and_mastery_from_store(tmp_path, monkeypatch):
    # A crafted sidecar whose notebook_id we also drive a quiz against, so the home card and the
    # mastery row line up. Back-dating the review makes the card read "due".
    root = tmp_path / "NotebookLMs"
    root.mkdir()
    nb = uid("homebadge")
    write_notebook(
        root,
        "home-badge",
        f"""---
notebook_id: {nb}
alias: home-badge
title: Home Badge Topic
template: learning-topic
---

# Home Badge Topic
**NotebookLM:** https://notebooklm.google.com/notebook/{nb}

### Study aids
| Ep | Topic | Study Guide ID | Quiz ID |
|----|-------|----------------|---------|
| 1 | intro | {uid("hbguide")} | {uid("hbquiz")} |
""",
    )
    monkeypatch.setenv("NOTEBOOKLM_ROOT", str(root))
    _fresh_store(tmp_path, monkeypatch, "badge-hub")
    from app.config import get_settings

    try:
        client = _client()
        try:
            _take_quiz(client, nb)  # creates a topic_mastery row for this notebook_id
            _backdate(nb, 6 * 14.0)  # well past several half-lives → due

            groups = client.get("/api/catalog").json()["groups"]
            card = next(
                c for g in groups for c in g["notebooks"] if c["notebook_id"] == nb
            )
            assert card["due_for_review"] is True
            assert card["mastery"] is not None and card["mastery"] < 0.5
            assert card["last_touched"] is not None
        finally:
            client.app.dependency_overrides.clear()
    finally:
        get_settings.cache_clear()
