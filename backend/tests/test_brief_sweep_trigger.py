"""FR2 POST /api/brief/sweep — the stale morning's recovery becomes a phone tap.

M6 put the 6:30am read on a keyboard-less iPhone; assumption 2 guarantees the served
brief is sometimes a day old (Mac asleep, catch-up not yet fired) — and the only recovery
the UI offered was a terminal command. The endpoint re-invokes the same ./sweep.sh
pipeline launchd runs, detached, behind a single in-process lock.

House rules under test: the child env is scrubbed (sweep.sh REFUSES to start with
ANTHROPIC_API_KEY set — the phone lane must stay on the subscription) and carries
SWEEP_SKIP_DONE=1 (a tap on an already-fresh day is a per-topic no-op, and SWEEP_FORCE is
deliberately absent so the HA2 note-detach guard keeps refusing non-tty re-sweeps); a tap
while a sweep runs is an honest no-op; a missing runner is a 503, never a hang.

Sandbox rules (test_sweep_runner.py's): sweep.sh runs only as a COPY inside a tmp box
with a stub ``claude`` on PATH, the endpoint's script path injected via SWEEP_SCRIPT —
the real repo pipeline, data/sweeps, and the real claude CLI are never touched.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

GOOD_BRIEF = {
    "top_line": "One release worth your time.",
    "context_note": None,
    "items": [
        {
            "headline": "OpenAI lifts caps",
            "attribution": "Bleeping Computer, July 12, 2026",
            "digest": "OpenAI lifted the cap.",
            "why_it_matters": "Budget math changes.",
            "sources": [{"title": "Bleeping Computer", "url": "https://example.com/a"}],
        }
    ],
}


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _sandbox(tmp_path: Path) -> Path:
    """A mini repo tree sweep.sh treats as ROOT — real envelope.py + real (frozen)
    renderer, stub claude, no-op audio, one-topic roster (full-roster mode: the endpoint
    passes no TOPIC)."""
    box = tmp_path / "box"
    (box / "sweeps" / "prompts").mkdir(parents=True)
    (box / "bin").mkdir()
    shutil.copyfile(REPO / "sweep.sh", box / "sweep.sh")
    shutil.copyfile(REPO / "sweeps" / "envelope.py", box / "sweeps" / "envelope.py")
    shutil.copyfile(REPO / "sweeps" / "render_brief.py", box / "sweeps" / "render_brief.py")
    (box / "sweeps" / "audio_brief.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    (box / "sweeps" / "topics.json").write_text(
        json.dumps([{"slug": "ai-llms", "title": "AI / LLMs", "paused": False}]),
        encoding="utf-8",
    )
    (box / "sweeps" / "prompts" / "ai-llms.md").write_text("Sweep ai/llms.", encoding="utf-8")
    (box / "envelope.json").write_text(
        json.dumps({"result": json.dumps(GOOD_BRIEF), "is_error": False}), encoding="utf-8"
    )
    claude = box / "bin" / "claude"
    claude.write_text(
        f'#!/bin/sh\necho called >> "{box}/claude-called.txt"\ncat "{box}/envelope.json"\n',
        encoding="utf-8",
    )
    claude.chmod(0o755)
    return box


def _env(tmp_path, monkeypatch, name: str, *, script: Path, sweeps_dir: Path, roster: Path):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps_dir))
    monkeypatch.setenv("ROSTER_FILE", str(roster))
    monkeypatch.setenv("SWEEP_SCRIPT", str(script))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()


def _wait_for_trigger(timeout: float = 60) -> int:
    """Block on the endpoint's own detached-process handle — deterministic, no polling."""
    import app.api.brief as brief_api

    assert brief_api._sweep_proc is not None
    return brief_api._sweep_proc.wait(timeout=timeout)


def test_tap_runs_the_sandboxed_sweep_end_to_end_scrubbed(tmp_path, monkeypatch):
    """POST → detached sweep.sh (the real script, sandbox copy) → stub claude → real
    envelope/renderer → GET /api/brief serves the fresh day. ANTHROPIC_API_KEY is set in
    the server env on purpose: sweep.sh refuses to start when it leaks through, so the
    served fresh brief doubles as proof the endpoint scrubbed the child env (bug #10's
    guarantee extends to the phone lane)."""
    box = _sandbox(tmp_path)
    _env(
        tmp_path,
        monkeypatch,
        "e2e",
        script=box / "sweep.sh",
        sweeps_dir=box / "data" / "sweeps",
        roster=box / "sweeps" / "topics.json",
    )
    monkeypatch.setenv("PATH", f"{box / 'bin'}:{os.environ['PATH']}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-must-not-leak")
    from app.config import get_settings

    try:
        client = _client()
        r = client.post("/api/brief/sweep")
        assert r.status_code == 200
        assert r.json() == {"started": True, "already_running": False}
        assert _wait_for_trigger() == 0
        body = client.get("/api/brief").json()
        assert body["date"] == date.today().isoformat()
        assert body["topics"][0]["items"][0]["headline"] == "OpenAI lifts caps"
        assert (box / "claude-called.txt").exists()  # the stub, not the real CLI
    finally:
        get_settings.cache_clear()


def test_second_tap_while_running_is_an_honest_noop(tmp_path, monkeypatch):
    """The double-fire footgun: one in-process lock, one sweep. The second tap reports
    already_running instead of stacking a concurrent pipeline; a finished run unlocks."""
    slow = tmp_path / "slow.sh"
    slow.write_text("#!/bin/sh\nsleep 2\n", encoding="utf-8")
    slow.chmod(0o755)
    sweeps_dir = tmp_path / "sweeps-data"
    sweeps_dir.mkdir()
    roster = tmp_path / "topics.json"
    roster.write_text("[]", encoding="utf-8")
    _env(tmp_path, monkeypatch, "lock", script=slow, sweeps_dir=sweeps_dir, roster=roster)
    from app.config import get_settings

    try:
        client = _client()
        assert client.post("/api/brief/sweep").json() == {
            "started": True,
            "already_running": False,
        }
        assert client.post("/api/brief/sweep").json() == {
            "started": False,
            "already_running": True,
        }
        assert _wait_for_trigger(timeout=30) == 0
        assert client.post("/api/brief/sweep").json()["started"] is True
        assert _wait_for_trigger(timeout=30) == 0
    finally:
        get_settings.cache_clear()


def test_missing_runner_is_a_503_not_a_hang(tmp_path, monkeypatch):
    sweeps_dir = tmp_path / "sweeps-data"
    sweeps_dir.mkdir()
    roster = tmp_path / "topics.json"
    roster.write_text("[]", encoding="utf-8")
    _env(
        tmp_path,
        monkeypatch,
        "missing",
        script=tmp_path / "does-not-exist.sh",
        sweeps_dir=sweeps_dir,
        roster=roster,
    )
    from app.config import get_settings

    try:
        assert _client().post("/api/brief/sweep").status_code == 503
    finally:
        get_settings.cache_clear()


def test_child_env_is_scrubbed_and_carries_skip_done_but_never_force(tmp_path, monkeypatch):
    """The explicit env contract: the full bug-#10 lane set is dropped, SWEEP_SKIP_DONE=1
    rides along (idempotent tap), and SWEEP_FORCE is absent — the HA2 note-detach guard
    must keep its power to refuse the non-tty phone lane."""
    dump = tmp_path / "envdump.txt"
    script = tmp_path / "dump.sh"
    script.write_text(f'#!/bin/sh\nenv > "{dump}"\n', encoding="utf-8")
    script.chmod(0o755)
    sweeps_dir = tmp_path / "sweeps-data"
    sweeps_dir.mkdir()
    roster = tmp_path / "topics.json"
    roster.write_text("[]", encoding="utf-8")
    _env(tmp_path, monkeypatch, "scrub", script=script, sweeps_dir=sweeps_dir, roster=roster)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://elsewhere.example")
    from app.config import get_settings

    try:
        assert _client().post("/api/brief/sweep").json()["started"] is True
        assert _wait_for_trigger(timeout=30) == 0
        text = dump.read_text(encoding="utf-8")
        assert "ANTHROPIC_API_KEY" not in text
        assert "ANTHROPIC_BASE_URL" not in text
        assert "SWEEP_SKIP_DONE=1" in text
        assert "SWEEP_FORCE" not in text
    finally:
        get_settings.cache_clear()
