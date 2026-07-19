"""M5 POST /api/brief/chat — one grounded follow-up answer per served brief item.

House rules under test: the runner is always injected (a real ``claude`` is never spawned);
the prompt actually carries the served item + the question (the model can't answer well on
context it never received); the item is resolved on the SERVED day only, so a stale tab's
date-scoped id 404s after rollover; every exchange — including failures — lands in the chat
ledger under the backend data dir; and chat never writes anything under the sweeps dir
(the read-only invariant M1 established).
"""

from __future__ import annotations

import json

from app.chat import BriefChatClient, ChatResult, _scrubbed_env

VALID_BRIEF = {
    "topic": "ai-llms",
    "date": "2026-07-14",
    "as_of": "2026-07-14 07:05 CDT",
    "top_line": "One release actually worth your time.",
    "context_note": None,
    "items": [
        {
            "headline": "OpenAI lifts caps",
            "attribution": "Bleeping Computer, July 13, 2026",
            "digest": "OpenAI removed the rolling 5-hour cap.",
            "why_it_matters": "Shapes your agent session budget.",
            "sources": [{"title": "Bleeping Computer", "url": "https://example.com/a"}],
        }
    ],
}

PILOT_ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
]


def _envelope(answer="Because the cap shaped session budgets.", cost=0.0123, dur=4200) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": answer,
            "total_cost_usd": cost,
            "duration_ms": dur,
            "usage": {"input_tokens": 900, "output_tokens": 120},
        }
    )


def _fake_runner(stdout=None, code=0, stderr=""):
    """A canned claude: records every args list it was invoked with."""
    calls: list[list[str]] = []

    def run(args):
        calls.append(list(args))
        return ChatResult(list(args), stdout if stdout is not None else _envelope(), stderr, code)

    run.calls = calls
    return run


def _client(runner):
    from fastapi.testclient import TestClient

    from app.deps import get_brief_chat_client
    from app.main import app

    app.dependency_overrides[get_brief_chat_client] = lambda: BriefChatClient(
        model="sonnet", runner=runner
    )
    return TestClient(app), app


def _env(tmp_path, monkeypatch, name: str):
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    roster_file = tmp_path / name / "topics.json"
    roster_file.write_text(json.dumps(PILOT_ROSTER), encoding="utf-8")
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("ROSTER_FILE", str(roster_file))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    return sweeps


def _write_day(sweeps, date: str, files: dict[str, str]):
    day = sweeps / date
    day.mkdir(parents=True, exist_ok=True)
    for fname, text in files.items():
        (day / fname).write_text(text, encoding="utf-8")
    return day


def _served_item_id(client) -> str:
    body = client.get("/api/brief").json()
    return body["topics"][0]["items"][0]["id"]


def _chat(client, item_id, question="Why does this matter for my agent budget?", slug="ai-llms"):
    return client.post(
        "/api/brief/chat",
        json={"item_id": item_id, "topic_slug": slug, "question": question},
    )


def _teardown(app):
    from app.config import get_settings

    app.dependency_overrides.clear()
    get_settings.cache_clear()


# -- happy path --------------------------------------------------------------------


def test_chat_answers_and_prompt_carries_item_and_question(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "happy")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        r = _chat(client, _served_item_id(client))
        assert r.status_code == 200
        assert r.json() == {"answer": "Because the cap shaped session budgets."}
        assert len(runner.calls) == 1
        args = runner.calls[0]
        assert args[0] == "-p"
        prompt = args[1]
        # The model must receive the served item, the question, and the honesty framing.
        for needle in (
            "OpenAI lifts caps",
            "OpenAI removed the rolling 5-hour cap.",
            "Shapes your agent session budget.",
            "https://example.com/a",
            "Why does this matter for my agent budget?",
            "AI / LLMs",
            "NO web or tool access",
        ):
            assert needle in prompt
        assert args[args.index("--model") + 1] == "sonnet"
        assert args[args.index("--output-format") + 1] == "json"
    finally:
        _teardown(app)


def test_chat_appends_a_success_ledger_row(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "ledger")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    client, app = _client(_fake_runner())
    try:
        item_id = _served_item_id(client)
        assert _chat(client, item_id).status_code == 200
        from app.config import get_settings

        rows = [
            json.loads(line)
            for line in get_settings().brief_chat_ledger.read_text(encoding="utf-8").splitlines()
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row["is_error"] is False
        assert row["brief_date"] == "2026-07-14"
        assert row["topic"] == "ai-llms"
        assert row["item_id"] == item_id
        assert row["total_cost_usd"] == 0.0123
        assert row["input_tokens"] == 900
    finally:
        _teardown(app)


# -- request validation (the runner must never fire) --------------------------------


def test_chat_rejects_empty_question_without_running_claude(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "emptyq")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        assert _chat(client, _served_item_id(client), question="   ").status_code == 400
        assert runner.calls == []
    finally:
        _teardown(app)


def test_chat_rejects_oversized_question(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "bigq")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        assert _chat(client, _served_item_id(client), question="x" * 2001).status_code == 400
        assert runner.calls == []
    finally:
        _teardown(app)


def test_chat_404s_on_unknown_item_and_on_no_sweeps(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "missing")
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        assert _chat(client, "deadbeef1234").status_code == 404  # no sweeps at all
        _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
        assert _chat(client, "deadbeef1234").status_code == 404  # day exists, id doesn't
        assert runner.calls == []
    finally:
        _teardown(app)


def test_chat_404s_a_stale_days_item_id_after_rollover(tmp_path, monkeypatch):
    """Ids are date-scoped, so yesterday's tab asking about yesterday's item must 404 once a
    newer day is served — never silently answer against the wrong morning."""
    sweeps = _env(tmp_path, monkeypatch, "stale")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    runner = _fake_runner()
    client, app = _client(runner)
    try:
        stale_id = _served_item_id(client)  # served day is 07-13 right now
        _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
        assert _chat(client, stale_id).status_code == 404
        assert runner.calls == []
    finally:
        _teardown(app)


# -- failure contract ----------------------------------------------------------------


def test_chat_502_on_nonzero_exit_and_logs_an_error_row(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "boom")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    client, app = _client(_fake_runner(stdout="", code=1, stderr="boom"))
    try:
        r = _chat(client, _served_item_id(client))
        assert r.status_code == 502
        from app.config import get_settings

        row = json.loads(get_settings().brief_chat_ledger.read_text(encoding="utf-8"))
        assert row["is_error"] is True
        assert "boom" in row["error"]
    finally:
        _teardown(app)


def test_chat_502_on_error_envelope_and_on_unparseable_output(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "badenv")
    _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    err_env = json.dumps({"type": "result", "is_error": True, "result": "overloaded"})
    for stdout in (err_env, "not json at all"):
        client, app = _client(_fake_runner(stdout=stdout))
        try:
            assert _chat(client, _served_item_id(client)).status_code == 502
        finally:
            _teardown(app)


def test_chat_never_writes_under_the_sweeps_dir(tmp_path, monkeypatch):
    sweeps = _env(tmp_path, monkeypatch, "readonly")
    day = _write_day(sweeps, "2026-07-14", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    client, app = _client(_fake_runner())
    try:
        before = sorted(p.name for p in day.iterdir())
        assert _chat(client, _served_item_id(client)).status_code == 200
        assert sorted(p.name for p in day.iterdir()) == before
        assert sorted(p.name for p in sweeps.iterdir()) == ["2026-07-14"]
    finally:
        _teardown(app)


# -- lane guard ----------------------------------------------------------------------


def test_scrubbed_env_drops_the_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-oops")
    env = _scrubbed_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert env  # everything else survives


# -- newest-dir servability (P1 bug #1) ---------------------------------------------


def test_chat_resolves_item_past_empty_newest_dir(tmp_path, monkeypatch):
    """The wake-window empty day dir must not 404 chat for the brief actually on the
    page — the served day is the newest day with renderable content."""
    sweeps = _env(tmp_path, monkeypatch, "emptynewest")
    _write_day(sweeps, "2026-07-13", {"ai-llms.json": json.dumps(VALID_BRIEF)})
    (sweeps / "2026-07-14").mkdir()
    client, app = _client(_fake_runner())
    try:
        body = client.get("/api/brief").json()
        assert body["has_data"] is True  # the wake window must not blank the brief
        item_id = body["topics"][0]["items"][0]["id"]
        assert _chat(client, item_id).status_code == 200
    finally:
        _teardown(app)
