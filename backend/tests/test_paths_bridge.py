"""POST /api/paths/{id}/steps/{step}/bridge — formative bridge-check grading (M8 Phase 3b).

The grader runs on the M5 subscription lane; the runner is always injected (a real ``claude`` is
never spawned). Asserts: a graded bridge returns feedback + marks the step done (coverage) but NOT
mastery; a non-bridge step is refused; an empty answer 422s; a claude hiccup degrades to a calm
ok=False (never a 500) while still marking coverage; and every run lands a usage row in the ledger.
"""

from __future__ import annotations

import json

import pytest

from app.chat import BriefChatClient, ChatResult

JACOBIAN = "f84dc873-0dc7-407d-9b2a-dbde7eeb66c4"
BRIDGE_STEP = "bridge-lens"


def _envelope(
    answer="Good — you named the layer-wise Jacobian. Missing: why it beats the logit lens.",
) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": answer,
            "total_cost_usd": 0.004,
            "duration_ms": 3100,
            "usage": {"input_tokens": 300, "output_tokens": 60},
        }
    )


def _fake_runner(stdout=None, code=0, stderr=""):
    def run(args):
        return ChatResult(list(args), stdout if stdout is not None else _envelope(), stderr, code)

    return run


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("PATHS_DIR", str(tmp_path / "hub" / "paths"))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    yield tmp_path
    get_settings.cache_clear()


def _client(runner):
    from fastapi.testclient import TestClient

    from app.deps import get_brief_chat_client
    from app.main import app

    app.dependency_overrides[get_brief_chat_client] = lambda: BriefChatClient(
        model="sonnet", runner=runner
    )
    return TestClient(app), app


def _bridge(client, answer="The Jacobian lens reads reasoning via layer-wise sensitivity."):
    return client.post(f"/api/paths/{JACOBIAN}/steps/{BRIDGE_STEP}/bridge", json={"answer": answer})


def test_graded_bridge_returns_feedback_marks_coverage_not_mastery(env):
    client, app = _client(_fake_runner())
    try:
        b = _bridge(client).json()
        assert b["ok"] is True
        assert "logit lens" in b["feedback"]
        step = next(s for s in b["path"]["steps"] if s["id"] == BRIDGE_STEP)
        assert step["completed"] is True  # coverage moved
        assert b["path"]["mastery"] is None  # but mastery is untouched — formative only
    finally:
        app.dependency_overrides.clear()


def test_non_bridge_step_is_refused(env):
    client, app = _client(_fake_runner())
    try:
        r = client.post(f"/api/paths/{JACOBIAN}/steps/ep1/bridge", json={"answer": "x"})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_empty_answer_is_422(env):
    client, app = _client(_fake_runner())
    try:
        assert _bridge(client, answer="   ").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_claude_hiccup_degrades_not_500_but_still_marks_coverage(env):
    client, app = _client(_fake_runner(code=1, stderr="boom"))  # non-zero -> BriefChatError
    try:
        b = _bridge(client).json()
        assert b["ok"] is False and b["error"]
        assert next(s for s in b["path"]["steps"] if s["id"] == BRIDGE_STEP)["completed"] is True
    finally:
        app.dependency_overrides.clear()


def test_every_run_lands_a_usage_row(env):
    client, app = _client(_fake_runner())
    try:
        _bridge(client)
        ledger = env / "hub" / "paths-grade.jsonl"
        assert ledger.is_file()
        row = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert row["item_id"] == BRIDGE_STEP and row["is_error"] is False
    finally:
        app.dependency_overrides.clear()
