"""POST /api/paths/{notebook_id}/generate — the on-demand path Designer (M8, design decision 9).

Pins the M0 no-fabrication bar at the endpoint boundary: the Designer runs on the M5
subscription lane (the runner is always injected — a real ``claude`` is never spawned), reads the
topic's REAL sidecar artifacts, and asks the model to ARRANGE them. The endpoint writes the path
sidecar ONLY when the whole composition is clean; ANY failure — a fabricated/mismatched artifact
id, unparseable output, a structural problem, or a claude hiccup — must come back as a calm
``ok=False`` (HTTP 200, never a 500) with NOTHING written to disk. Every run (success or failure)
lands a usage row in ``<LEARNING_HUB_DATA>/paths-generate.jsonl``.

Oracle discipline: the synthetic sidecar is the source of truth for which artifact ids exist and
what type each is (one ``audio``, one ``quiz`` — see ``_write_topic``). The fake designer output is
crafted against those exact ids, so "valid" vs "fabricated" vs "type-mismatch" are genuine catalog
distinctions, not string coincidences. The valid case round-trips through disk (a follow-up GET
returns the same steps), proving the write actually landed the composition it claims.
"""

from __future__ import annotations

import json

import pytest

from app.chat import BriefChatClient, ChatResult

from .conftest import uid, write_notebook

# -- synthetic topic (the catalog oracle) --------------------------------------
# A notebook whose README yields exactly one audio artifact and one quiz artifact, with ids we
# know — so a path step can cite a REAL id (valid), a made-up id (fabricated), or the wrong-typed
# real id (mismatch), and the M0 cross-check can actually tell them apart.
NB_ID = uid("pathnb")
AUDIO_ID = uid("pathaud")
QUIZ_ID = uid("pathquiz")
FAKE_ID = uid("nothere")  # a well-formed UUID that is NOT an artifact of this topic


def _write_topic(root):
    """A synthetic NotebookLM sidecar: 1 audio + 1 quiz, ids known to the test. NO study guide, so
    the designer's structure check never demands a bridge step for our happy-path composition."""
    write_notebook(
        root,
        "demo-topic",
        f"""---
notebook_id: {NB_ID}
title: Demo Topic
template: learning-topic
---

# Demo Topic

### Audio season
| Ep | Title | Status | Artifact ID |
|----|-------|--------|-------------|
| 1 | Ep 1 — Intro | done | {AUDIO_ID} |

### Quizzes
| Ep | Title | Status | Quiz ID |
|----|-------|--------|---------|
| 1 | Ep 1 — Quiz | done | {QUIZ_ID} |
""",
    )


def _path_json(audio_id: str = AUDIO_ID, quiz_id: str = QUIZ_ID) -> str:
    """A structurally valid path over the topic; callers swap in a bad id to exercise the M0 bar."""
    return json.dumps(
        {
            "title": "A Path",
            "topic": "demo",
            "steps": [
                {"id": "intro", "kind": "intro", "title": "Start", "body": "orient"},
                {
                    "id": "ep1",
                    "kind": "audio",
                    "title": "Listen",
                    "artifact_id": audio_id,
                    "artifact_type": "audio",
                    "focus": "the core idea",
                    "estimated_minutes": 8,
                },
                {
                    "id": "quiz",
                    "kind": "quiz",
                    "title": "Test",
                    "artifact_id": quiz_id,
                    "artifact_type": "quiz",
                },
                {"id": "reflect", "kind": "reflect", "title": "Reflect", "body": "think"},
            ],
        }
    )


# -- fakes: the claude envelope whose .result is the designer's output ----------

def _envelope(result: str) -> str:
    """A success claude JSON envelope. ``result`` is the STRING the designer parses — set it to a
    path-JSON string (good/bad) to simulate the model's composition."""
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": result,
            "total_cost_usd": 0.02,
            "duration_ms": 9000,
            "usage": {"input_tokens": 800, "output_tokens": 400},
        }
    )


def _fake_runner(*, result: str | None = None, stdout: str | None = None, code: int = 0, stderr=""):
    def run(args):
        out = stdout if stdout is not None else _envelope(result if result is not None else _path_json())
        return ChatResult(list(args), out, stderr, code)

    return run


# -- fixtures ------------------------------------------------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate all three surfaces the endpoint touches: the SQLite store + generate ledger
    (LEARNING_HUB_DATA), the written-path dir (PATHS_DIR), and the synthetic sidecar root
    (NOTEBOOKLM_ROOT) — so nothing here reads the real data dir or the real NotebookLM sidecars."""
    root = tmp_path / "NotebookLMs"
    root.mkdir()
    _write_topic(root)

    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    monkeypatch.setenv("PATHS_DIR", str(tmp_path / "hub" / "paths"))
    monkeypatch.setenv("NOTEBOOKLM_ROOT", str(root))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    yield tmp_path
    get_settings.cache_clear()


def _client(runner):
    from fastapi.testclient import TestClient

    from app.deps import get_path_designer_client
    from app.main import app

    app.dependency_overrides[get_path_designer_client] = lambda: BriefChatClient(
        model="sonnet", runner=runner
    )
    return TestClient(app), app


def _generate(client):
    return client.post(f"/api/paths/{NB_ID}/generate")


def _paths_file(env):
    return env / "hub" / "paths" / f"{NB_ID}.json"


# -- cases: happy path ---------------------------------------------------------

def test_valid_generation_writes_and_round_trips(env):
    """A clean composition citing REAL ids → ok=True, a fresh path (progress 0), a file on disk, and
    a follow-up GET returns the SAME steps — proving the write landed, not just that the call said so."""
    client, app = _client(_fake_runner())
    try:
        r = _generate(client)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["error"] is None and body["errors"] == []
        assert body["total_cost_usd"] == 0.02 and body["duration_ms"] == 9000

        path = body["path"]
        assert path is not None
        assert path["notebook_id"] == NB_ID
        assert [s["id"] for s in path["steps"]] == ["intro", "ep1", "quiz", "reflect"]
        assert path["progress_pct"] == 0  # fresh — nothing completed yet
        assert path["step_count"] == 4 and path["completed_steps"] == 0
        # the audio step kept its real artifact id + minutes through validation
        ep1 = next(s for s in path["steps"] if s["id"] == "ep1")
        assert ep1["artifact_id"] == AUDIO_ID and ep1["estimated_minutes"] == 8

        # it actually hit disk under PATHS_DIR ...
        assert _paths_file(env).is_file()
        # ... and re-reads identically through the on-disk loader (GET), not just from memory.
        got = client.get(f"/api/paths/{NB_ID}")
        assert got.status_code == 200
        assert [s["id"] for s in got.json()["steps"]] == ["intro", "ep1", "quiz", "reflect"]
    finally:
        app.dependency_overrides.clear()


# -- cases: the M0 no-fabrication bar ------------------------------------------

def test_fabricated_artifact_id_is_rejected_and_nothing_written(env):
    """A step citing an id that is NOT a real artifact of this topic → ok=False, errors name the bad
    id, and no path file is written (a stale GET still 404s)."""
    client, app = _client(_fake_runner(result=_path_json(audio_id=FAKE_ID)))
    try:
        r = _generate(client)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["path"] is None
        assert body["errors"] and any(FAKE_ID in e for e in body["errors"])

        assert not _paths_file(env).exists()  # nothing landed on disk
        assert client.get(f"/api/paths/{NB_ID}").status_code == 404  # so GET still finds no path
    finally:
        app.dependency_overrides.clear()


def test_type_mismatch_is_rejected_and_nothing_written(env):
    """An ``audio`` step citing the quiz's REAL id → the id exists but its type is wrong, so the M0
    cross-check rejects it. ok=False, errors mention the mismatch, nothing written."""
    # audio step points at the quiz artifact (real id, wrong type); quiz step still valid.
    client, app = _client(_fake_runner(result=_path_json(audio_id=QUIZ_ID)))
    try:
        r = _generate(client)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["errors"]
        joined = " ".join(body["errors"]).lower()
        assert "kind" in joined or "audio" in joined  # the mismatch, not a "not a real artifact"

        assert not _paths_file(env).exists()
    finally:
        app.dependency_overrides.clear()


# -- cases: unparseable / hiccup (calm ok=False, never a 500) -------------------

def test_malformed_json_degrades_not_500(env):
    """The designer returns text that isn't JSON → ok=False with a calm ``error``, nothing written."""
    client, app = _client(_fake_runner(result="not json at all"))
    try:
        r = _generate(client)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["error"]  # the parse error, human-readable
        assert not _paths_file(env).exists()
    finally:
        app.dependency_overrides.clear()


def test_claude_hiccup_degrades_not_500(env):
    """A non-zero claude exit (→ BriefChatError) → ok=False + ``error``, nothing written, NOT a 500."""
    client, app = _client(_fake_runner(code=1, stderr="boom"))
    try:
        r = _generate(client)
        assert r.status_code == 200  # the grader posture: a hiccup is calm, never a 500
        body = r.json()
        assert body["ok"] is False and body["error"]
        assert not _paths_file(env).exists()
    finally:
        app.dependency_overrides.clear()


# -- cases: no sidecar ---------------------------------------------------------

def test_no_sidecar_is_404(env):
    """A notebook_id with no sidecar under NOTEBOOKLM_ROOT → 404 (the designer never runs)."""
    client, app = _client(_fake_runner())
    try:
        r = client.post(f"/api/paths/{uid('missing')}/generate")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


# -- cases: the usage ledger (every run, success or failure) -------------------

def test_success_run_lands_a_clean_ledger_row(env):
    client, app = _client(_fake_runner())
    try:
        _generate(client)
        ledger = env / "hub" / "paths-generate.jsonl"
        assert ledger.is_file()
        row = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert row["item_id"] == "generate"
        assert row["is_error"] is False
        assert row["total_cost_usd"] == 0.02  # cost threaded from the envelope
    finally:
        app.dependency_overrides.clear()


def test_failure_run_lands_an_error_ledger_row(env):
    """A rejected composition still records usage — with is_error True (observability never eats a
    failure)."""
    client, app = _client(_fake_runner(result=_path_json(audio_id=FAKE_ID)))
    try:
        _generate(client)
        ledger = env / "hub" / "paths-generate.jsonl"
        assert ledger.is_file()
        row = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert row["item_id"] == "generate"
        assert row["is_error"] is True
    finally:
        app.dependency_overrides.clear()
