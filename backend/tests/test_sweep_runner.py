"""sweep.sh runner guards — Wave 2 batch 1 (docs/bug-hunt/2026-07-19-post-m7.md).

Bug #22: the always-on com.homebase.server reads data/sweeps/<date>/<topic>.json per
request, and the frozen renderer write_text-truncates that exact path — a reader in the
window sees an "unreadable <topic>.json" error card on the morning brief. The runner must
stage the render and rename artifacts into place whole (.md first, then the .json it backs);
render_brief.py itself stays untouched (trust-critical, frozen).

HA2 (docs/ideas/resweep-note-detach-guard.md): a manual same-day re-sweep rewrites
headlines, shifting every item's sha1(date|slug|headline) id — notes Kyle already attached
to today's items silently detach from the Today view. The runner must warn loudly, name the
note count, and refuse a non-interactive overwrite unless SWEEP_FORCE=1.

Every test copies sweep.sh into a sandbox tree (its ROOT is derived from the script's own
location) with a stub `claude` on PATH, the real envelope.py, and a no-op audio step — the
real repo's data/sweeps, cost ledger, store, and the real claude CLI are never touched.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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

# Stand-in renderer that records where the runner pointed it, then writes both artifacts
# there — the probe for the bug-#22 invariant (never rendered directly at the served path).
PROBE_RENDERER = '''#!/usr/bin/env python3
import sys
from pathlib import Path

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
out_dir = Path(args["--out-dir"])
topic = args["--topic"]
(Path(__file__).resolve().parents[1] / "probe-outdir.txt").write_text(str(out_dir))
(out_dir / (topic + ".json")).write_text('{"probe": true}')
(out_dir / (topic + ".md")).write_text("# probe")
'''

# Stand-in for the renderer's failure mode: keep the raw output, exit 1.
FAILING_RENDERER = '''#!/usr/bin/env python3
import sys
from pathlib import Path

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
(Path(args["--out-dir"]) / (args["--topic"] + ".raw.txt")).write_text("kept raw output")
sys.exit(1)
'''


def _today() -> str:
    return date.today().isoformat()


def _sandbox(tmp_path: Path, renderer: str | None) -> Path:
    """A mini repo tree sweep.sh treats as ROOT. renderer=None copies the real (frozen) one."""
    box = tmp_path / "box"
    (box / "sweeps" / "prompts").mkdir(parents=True)
    (box / "bin").mkdir()
    shutil.copyfile(REPO / "sweep.sh", box / "sweep.sh")
    shutil.copyfile(REPO / "sweeps" / "envelope.py", box / "sweeps" / "envelope.py")
    if renderer is None:
        shutil.copyfile(REPO / "sweeps" / "render_brief.py", box / "sweeps" / "render_brief.py")
    else:
        (box / "sweeps" / "render_brief.py").write_text(renderer, encoding="utf-8")
    (box / "sweeps" / "audio_brief.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    (box / "sweeps" / "deliver_brief.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
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


def _run(box: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{box / 'bin'}:{os.environ['PATH']}", "TOPIC": "ai-llms"}
    for var in ("ANTHROPIC_API_KEY", "SWEEP_SKIP_DONE", "SWEEP_FORCE",
                "SWEEP_NOTES_DB", "SWEEP_MAX_TOPICS", "SWEEP_MODEL"):
        env.pop(var, None)
    env.update(extra_env)
    return subprocess.run(
        ["bash", str(box / "sweep.sh")],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


# -- bug #22: atomic artifact placement -------------------------------------------


def test_renderer_writes_land_via_a_stage_dir_never_directly_at_the_served_path(tmp_path):
    box = _sandbox(tmp_path, PROBE_RENDERER)
    live = box / "data" / "sweeps" / _today()

    proc = _run(box)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (live / "ai-llms.json").read_text(encoding="utf-8") == '{"probe": true}'
    assert (live / "ai-llms.md").read_text(encoding="utf-8") == "# probe"
    rendered_into = Path((box / "probe-outdir.txt").read_text(encoding="utf-8"))
    # The bug: renderer write_text-truncated the exact path the server reads per request.
    assert rendered_into.resolve() != live.resolve()
    assert not list(live.glob(".stage*"))  # staging leaves nothing behind


def test_failed_render_still_keeps_raw_txt_and_counts_the_failure(tmp_path):
    box = _sandbox(tmp_path, FAILING_RENDERER)
    live = box / "data" / "sweeps" / _today()

    proc = _run(box)

    assert proc.returncode != 0  # the loud per-topic failure still fails the run
    assert (live / "ai-llms.raw.txt").read_text(encoding="utf-8") == "kept raw output"
    assert not (live / "ai-llms.json").exists()
    assert not (live / "ai-llms.md").exists()
    assert not list(live.glob(".stage*"))


def test_end_to_end_with_the_real_renderer(tmp_path):
    """Stub claude → real envelope.py → real (frozen) render_brief.py → served artifacts."""
    box = _sandbox(tmp_path, None)
    live = box / "data" / "sweeps" / _today()

    proc = _run(box)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    brief = json.loads((live / "ai-llms.json").read_text(encoding="utf-8"))
    assert brief["top_line"] == GOOD_BRIEF["top_line"]
    assert (live / "ai-llms.md").exists()


# -- HA2: same-day re-sweep note-detach guard -------------------------------------


def _seed_note(tmp_path: Path, monkeypatch) -> Path:
    """A real store (real migrations) holding one note attached to today's ai-llms brief."""
    hub = tmp_path / "hub"
    monkeypatch.setenv("LEARNING_HUB_DATA", str(hub))
    from app.config import get_settings
    from app.store import add_brief_note, init_db

    get_settings.cache_clear()
    try:
        init_db()
        add_brief_note(
            item_id="abc123def456",
            topic_slug="ai-llms",
            brief_date=_today(),
            item_headline="OpenAI lifts caps",
            body="check the cap math",
        )
    finally:
        get_settings.cache_clear()
    return hub / "learning-hub.sqlite"


def _pre_swept(box: Path) -> Path:
    """Today's ai-llms.json already on disk — the same-day re-sweep setup."""
    live = box / "data" / "sweeps" / _today()
    live.mkdir(parents=True)
    (live / "ai-llms.json").write_text('{"sentinel": "existing morning"}', encoding="utf-8")
    return live


def test_non_interactive_resweep_with_attached_notes_warns_and_refuses(tmp_path, monkeypatch):
    """No tty, no SWEEP_FORCE, 1 note attached to today's items → warn naming the count,
    leave the topic untouched, and never reach the expensive claude call."""
    box = _sandbox(tmp_path, PROBE_RENDERER)
    live = _pre_swept(box)
    db = _seed_note(tmp_path, monkeypatch)

    proc = _run(box, SWEEP_NOTES_DB=str(db))

    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "1 note" in out  # names the count
    assert "SWEEP_FORCE" in out  # says how to overwrite deliberately
    sentinel = json.loads((live / "ai-llms.json").read_text(encoding="utf-8"))
    assert sentinel == {"sentinel": "existing morning"}
    assert not (box / "claude-called.txt").exists()


def test_sweep_force_overwrites_after_the_warning(tmp_path, monkeypatch):
    """SWEEP_FORCE=1 is the deliberate overwrite lane: still re-sweeps, notes detach."""
    box = _sandbox(tmp_path, PROBE_RENDERER)
    live = _pre_swept(box)
    db = _seed_note(tmp_path, monkeypatch)

    proc = _run(box, SWEEP_NOTES_DB=str(db), SWEEP_FORCE="1")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (box / "claude-called.txt").exists()
    assert (live / "ai-llms.json").read_text(encoding="utf-8") == '{"probe": true}'


def test_resweep_without_notes_proceeds_silently(tmp_path):
    """No notes attached (store file absent) → today's behavior: overwrite, no ceremony."""
    box = _sandbox(tmp_path, PROBE_RENDERER)
    live = _pre_swept(box)

    proc = _run(box, SWEEP_NOTES_DB=str(tmp_path / "missing.sqlite"))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (box / "claude-called.txt").exists()
    assert (live / "ai-llms.json").read_text(encoding="utf-8") == '{"probe": true}'


# -- Overnight Chief of Staff v0: post-sweep chaining (best-effort) -----------------

# Probe stand-in for sweeps/actions_queue.py — records how the runner invoked it.
PROBE_ACTIONS = '''#!/usr/bin/env python3
import sys
from pathlib import Path

Path(__file__).resolve().parents[1].joinpath("actions-called.txt").write_text(
    " ".join(sys.argv[1:])
)
sys.exit(0)
'''


def test_runner_chains_the_overnight_pass_after_the_sweep(tmp_path):
    """The nightly pass runs after the topic loop with the runner's own date/paths —
    today's briefs, the roster, the backend ledger, and the shared cost ledger."""
    box = _sandbox(tmp_path, None)
    (box / "sweeps" / "actions_queue.py").write_text(PROBE_ACTIONS, encoding="utf-8")

    proc = _run(box)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    called = (box / "actions-called.txt").read_text(encoding="utf-8")
    assert f"--date {_today()}" in called
    assert str(box / "data" / "sweeps") in called
    assert str(box / "sweeps" / "topics.json") in called
    assert str(box / "backend" / "data" / "overnight.jsonl") in called
    assert ".runs.jsonl" in called


def test_a_failed_overnight_pass_never_fails_the_sweep(tmp_path):
    """Best-effort by contract, like the audio brief: the pass crashing (or missing
    entirely) leaves the sweep's own exit code untouched."""
    box = _sandbox(tmp_path, None)
    (box / "sweeps" / "actions_queue.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")

    proc = _run(box)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (box / "data" / "sweeps" / _today() / "ai-llms.json").exists()
