"""The scheduled sweep waits for the network before it fires (docs/ideas/sweep-network-preflight.md).

The pmset wake lands at 06:00 and launchd starts the wrapper in the seconds before Wi-Fi
re-associates. Every topic's `claude` call then fails — and because the scheduled fire
technically *happened*, launchd's missed-time on-wake re-fire never triggers, so the brief
stays empty until Kyle re-sweeps by hand. On exactly the sleep-wake mornings the unattended
pipeline exists for.

The wrapper now probes the network first and only then runs `./sweep.sh`. House rules under
test: an abort never invokes the sweep (no topic state written, so the next wake or a
phone-triggered sweep finishes the day), the abort is honest — nonzero and named in the
dated log — and `SWEEP_SKIP_DONE=1` still reaches the sweep so a retry finishes only what's
missing.

Every test copies run-scheduled.sh into a sandbox tree (its ROOT is derived from the
script's own location) with stub `curl`/`claude` on PATH and a stub sweep.sh — the real
network, the real claude CLI, and the real data/sweeps are never touched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Fails with curl's "couldn't connect" until the Nth call, then succeeds. Records every
# invocation so the probe's URL and flags are assertable.
CURL_STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "{box}/curl-args"
n=$(cat "{box}/curl-count" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "{box}/curl-count"
if [ "$n" -ge "${{CURL_OK_ON:-1}}" ]; then exit 0; fi
exit 7
"""

# Stands in for the real sweep: records that it ran, and what it inherited.
SWEEP_STUB = """#!/usr/bin/env bash
echo "ran" > "{box}/sweep-ran.txt"
echo "SWEEP_SKIP_DONE=${{SWEEP_SKIP_DONE:-}}" >> "{box}/sweep-ran.txt"
exit 0
"""


def _sandbox(tmp_path: Path) -> Path:
    box = tmp_path / "box"
    (box / "sweeps" / "schedule").mkdir(parents=True)
    (box / "bin").mkdir()
    shutil.copyfile(
        REPO / "sweeps" / "schedule" / "run-scheduled.sh",
        box / "sweeps" / "schedule" / "run-scheduled.sh",
    )
    sweep = box / "sweep.sh"
    sweep.write_text(SWEEP_STUB.format(box=box), encoding="utf-8")
    sweep.chmod(0o755)
    for name, body in (("curl", CURL_STUB.format(box=box)), ("claude", "#!/bin/sh\nexit 0\n")):
        stub = box / "bin" / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    return box


def _run(box: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{box / 'bin'}:{os.environ['PATH']}"}
    # Keep the suite quick: the shipped 90s/5s defaults are what the LaunchAgent uses.
    env.setdefault("SWEEP_NET_WAIT_SECONDS", "2")
    env.setdefault("SWEEP_NET_PROBE_INTERVAL", "1")
    env.update(extra_env)
    return subprocess.run(
        ["bash", str(box / "sweeps" / "schedule" / "run-scheduled.sh")],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _log(box: Path) -> str:
    return (box / "data" / "sweeps" / "logs" / f"{date.today().isoformat()}.log").read_text(
        encoding="utf-8"
    )


def test_network_already_up_runs_the_sweep_immediately(tmp_path):
    box = _sandbox(tmp_path)

    proc = _run(box)

    assert proc.returncode == 0, _log(box)
    assert (box / "sweep-ran.txt").exists()
    assert (box / "curl-count").read_text(encoding="utf-8").strip() == "1"  # no needless wait


def test_a_dead_network_aborts_without_ever_invoking_the_sweep(tmp_path):
    """The whole point: no topic state is written, so the next wake (or a phone-triggered
    sweep) still finishes the day instead of finding a half-poisoned morning."""
    box = _sandbox(tmp_path)

    proc = _run(box, CURL_OK_ON="9999")

    assert proc.returncode != 0  # honest: launchd and the log both see a failure
    assert not (box / "sweep-ran.txt").exists()
    assert "network" in _log(box).lower()


def test_it_waits_and_then_sweeps_when_wifi_associates(tmp_path):
    """The sleep-wake morning itself — Wi-Fi shows up a few seconds late."""
    box = _sandbox(tmp_path)

    proc = _run(box, CURL_OK_ON="3", SWEEP_NET_WAIT_SECONDS="10", SWEEP_NET_PROBE_INTERVAL="1")

    assert proc.returncode == 0, _log(box)
    assert (box / "sweep-ran.txt").exists()
    assert int((box / "curl-count").read_text(encoding="utf-8").strip()) == 3
    assert "waiting for network" in _log(box).lower()  # the ticks are in the dated log


def test_the_probe_is_https_with_a_short_timeout(tmp_path):
    """HTTPS, not HTTP: a captive portal can answer a plain GET with a 200 and look like
    the internet, but it cannot complete someone else's TLS handshake."""
    box = _sandbox(tmp_path)

    _run(box)

    args = (box / "curl-args").read_text(encoding="utf-8")
    assert "https://" in args
    assert "http://" not in args.replace("https://", "")
    assert " -m " in f" {args} " or "--max-time" in args  # never hangs on a black hole


def test_the_skip_done_lane_still_reaches_the_sweep(tmp_path):
    """SWEEP_SKIP_DONE=1 is what makes an aborted morning's retry cheap — the preflight
    must not disturb it."""
    box = _sandbox(tmp_path)

    _run(box)

    assert "SWEEP_SKIP_DONE=1" in (box / "sweep-ran.txt").read_text(encoding="utf-8")
