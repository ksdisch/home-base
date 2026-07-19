"""M5 regenerate-material — the headless claude lane over the transactional writer.

House rules under test: the runner is always injected (a real ``claude`` is never spawned);
the prompt carries the course/lesson context, the per-type output contract, and the current
material; validation is the gate (invalid model output rolls the course back byte-identical
and reports ``ok=False``); every run — success, rollback, or failure — lands a ledger row;
and the lane guard scrubs ``ANTHROPIC_API_KEY`` from the child env.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.courses.regen import CourseRegenClient, _scrubbed_env

EXAMPLE_SLUG = "learning-how-to-learn"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fresh SQLite store + a writable COURSES_DIR holding one regenerable course."""
    d = tmp_path / "courses"
    d.mkdir()
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("COURSES_DIR", str(d))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    _course(d)
    try:
        yield d
    finally:
        get_settings.cache_clear()


def _write_course(base: Path, slug: str, manifest: dict, files: dict | None = None) -> Path:
    cdir = base / slug
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "course.json").write_text(json.dumps(manifest), encoding="utf-8")
    for rel, content in (files or {}).items():
        p = cdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return cdir


def _quiz_json(n: int = 2, correct_per_q: int = 1) -> dict:
    qs = []
    for i in range(n):
        opts = [
            {"text": f"opt{j}", "isCorrect": j < correct_per_q, "rationale": f"because {j}"}
            for j in range(3)
        ]
        qs.append({"question": f"Q{i}?", "answerOptions": opts, "hint": "think"})
    return {"title": "Regen Quiz", "questions": qs}


def _course(base: Path) -> Path:
    manifest = {
        "title": "C",
        "topic": "testing",
        "level": "intermediate",
        "modules": [
            {
                "id": "m1",
                "title": "Module One",
                "lessons": [
                    {
                        "id": "m1l1",
                        "title": "Lesson One",
                        "objectives": ["Explain the writer", "Apply the validator"],
                        "materials": [
                            {"type": "lesson", "title": "Body", "path": "lessons/m1l1.md"},
                            {
                                "type": "flashcards",
                                "title": "Deck",
                                "path": "flashcards/m1l1.json",
                                "count": 2,
                            },
                            {
                                "type": "quiz",
                                "title": "Check",
                                "path": "quizzes/m1l1.json",
                                "count": 1,
                            },
                            {"type": "project", "title": "Build it", "path": "projects/m1l1.md"},
                        ],
                    }
                ],
            }
        ],
    }
    files = {
        "lessons/m1l1.md": "old lesson body\n",
        "flashcards/m1l1.json": json.dumps(
            [{"front": "F1", "back": "B1"}, {"front": "F2", "back": "B2"}]
        ),
        "quizzes/m1l1.json": json.dumps(_quiz_json(1)),
        "projects/m1l1.md": "build the thing\n",
    }
    return _write_course(base, "c", manifest, files)


def _envelope(answer: str, cost: float = 0.02, dur: int = 45000) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": answer,
            "total_cost_usd": cost,
            "duration_ms": dur,
            "usage": {"input_tokens": 2100, "output_tokens": 900},
        }
    )


def _fake_runner(stdout=None, code=0, stderr=""):
    """A canned claude: records every args list it was invoked with."""
    from app.courses.regen import RegenResult

    calls: list[list[str]] = []

    def run(args):
        calls.append(list(args))
        out = stdout if stdout is not None else _envelope("new lesson body\n")
        return RegenResult(list(args), out, stderr, code)

    run.calls = calls
    return run


def _client(runner):
    from fastapi.testclient import TestClient

    from app.deps import get_course_regen_client
    from app.main import app

    app.dependency_overrides[get_course_regen_client] = lambda: CourseRegenClient(
        model="sonnet", runner=runner
    )
    return TestClient(app), app


def _teardown(app):
    from app.config import get_settings

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _regen(client, path, lesson="m1l1", slug="c", guidance=""):
    return client.post(
        f"/api/courses/{slug}/lessons/{lesson}/regenerate",
        json={"path": path, "guidance": guidance},
    )


def _ledger_rows():
    from app.config import get_settings

    text = get_settings().course_regen_ledger.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


# -- happy paths ---------------------------------------------------------------


def test_regen_lesson_replaces_file_and_prompt_carries_the_contract(env):
    runner = _fake_runner(stdout=_envelope("## Fresh section\n\nNew explanation."))
    client, app = _client(runner)
    try:
        r = _regen(client, "lessons/m1l1.md", guidance="Make it more rigorous")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["rolled_back"] is False
        assert body["duration_ms"] == 45000 and body["total_cost_usd"] == 0.02
        text = (env / "c" / "lessons" / "m1l1.md").read_text(encoding="utf-8")
        assert text == "## Fresh section\n\nNew explanation.\n"

        assert len(runner.calls) == 1
        args = runner.calls[0]
        assert args[0] == "-p"
        prompt = args[1]
        for needle in (
            "Lesson One",                       # lesson context
            "Module One",                       # module context
            "Explain the writer",               # objectives are the contract
            "old lesson body",                  # current content included
            "no leading '# Title' H1",          # per-type output rule
            "Make it more rigorous",            # Kyle's guidance
            "NO web or tool access",            # honesty framing
            "intermediate-level",               # course level reaches the prompt
        ):
            assert needle in prompt
        assert args[args.index("--model") + 1] == "sonnet"
        assert args[args.index("--output-format") + 1] == "json"

        rows = _ledger_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["is_error"] is False and row["rolled_back"] is False
        assert row["slug"] == "c" and row["material_path"] == "lessons/m1l1.md"
        assert row["material_type"] == "lesson" and row["total_cost_usd"] == 0.02
    finally:
        _teardown(app)


def test_regen_strips_a_wrapping_code_fence(env):
    fenced = "```markdown\n## Body\n\nText.\n```"
    client, app = _client(_fake_runner(stdout=_envelope(fenced)))
    try:
        assert _regen(client, "lessons/m1l1.md").status_code == 200
        text = (env / "c" / "lessons" / "m1l1.md").read_text(encoding="utf-8")
        assert text == "## Body\n\nText.\n"
    finally:
        _teardown(app)


def test_regen_quiz_lands_and_syncs_the_manifest_count(env):
    answer = "```json\n" + json.dumps(_quiz_json(2)) + "\n```"
    client, app = _client(_fake_runner(stdout=_envelope(answer)))
    try:
        r = _regen(client, "quizzes/m1l1.json")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["count"] == 2
        quiz = json.loads((env / "c" / "quizzes" / "m1l1.json").read_text(encoding="utf-8"))
        assert len(quiz["questions"]) == 2
        manifest = json.loads((env / "c" / "course.json").read_text(encoding="utf-8"))
        quiz_mat = manifest["modules"][0]["lessons"][0]["materials"][2]
        assert quiz_mat["count"] == 2  # was 1 — synced to the regenerated file
    finally:
        _teardown(app)


# -- validation is the gate ----------------------------------------------------


def test_regen_invalid_quiz_rolls_back_byte_identical(env):
    bad = json.dumps(_quiz_json(2, correct_per_q=2))  # two isCorrect:true per question
    file_before = (env / "c" / "quizzes" / "m1l1.json").read_bytes()
    manifest_before = (env / "c" / "course.json").read_bytes()
    client, app = _client(_fake_runner(stdout=_envelope(bad)))
    try:
        r = _regen(client, "quizzes/m1l1.json")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False and body["rolled_back"] is True
        assert any("isCorrect" in e for e in body["errors"])
        assert (env / "c" / "quizzes" / "m1l1.json").read_bytes() == file_before
        assert (env / "c" / "course.json").read_bytes() == manifest_before
        assert _ledger_rows()[0]["rolled_back"] is True  # the cost was still paid — record it
    finally:
        _teardown(app)


def test_regen_unparseable_deck_json_writes_nothing(env):
    file_before = (env / "c" / "flashcards" / "m1l1.json").read_bytes()
    client, app = _client(_fake_runner(stdout=_envelope("Here are your cards: F1/B1…")))
    try:
        r = _regen(client, "flashcards/m1l1.json")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False and "invalid JSON" in body["error"]
        assert (env / "c" / "flashcards" / "m1l1.json").read_bytes() == file_before
        assert _ledger_rows()[0]["is_error"] is True
    finally:
        _teardown(app)


# -- request validation (the runner must never fire) ---------------------------


def test_regen_rejects_oversized_guidance_without_running_claude(env):
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        r = _regen(client, "lessons/m1l1.md", guidance="x" * 2001)
        assert r.status_code == 400
        assert runner.calls == []
    finally:
        _teardown(app)


def test_regen_404s_and_422s_without_running_claude(env):
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        assert _regen(client, "lessons/m1l1.md", slug="nope").status_code == 404
        assert _regen(client, "lessons/m1l1.md", lesson="ghost").status_code == 404
        assert _regen(client, "lessons/other.md").status_code == 404  # not declared
        assert _regen(client, "projects/m1l1.md").status_code == 422  # not regenerable
        assert runner.calls == []
    finally:
        _teardown(app)


def test_regen_bundled_example_is_409(env):
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        assert _regen(client, "lessons/m1l1.md", slug=EXAMPLE_SLUG).status_code == 409
        assert runner.calls == []
    finally:
        _teardown(app)


# -- failure contract ----------------------------------------------------------


def test_regen_502_on_claude_failure_and_logs_an_error_row(env):
    client, app = _client(_fake_runner(stdout="", code=1, stderr="boom"))
    try:
        assert _regen(client, "lessons/m1l1.md").status_code == 502
        assert (env / "c" / "lessons" / "m1l1.md").read_text(encoding="utf-8") == (
            "old lesson body\n"
        )
        row = _ledger_rows()[0]
        assert row["is_error"] is True and "boom" in row["error"]
    finally:
        _teardown(app)


# -- lane guard ----------------------------------------------------------------


def test_scrubbed_env_drops_the_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-oops")
    env = _scrubbed_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert env  # everything else survives
