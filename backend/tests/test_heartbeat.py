"""PR12 heartbeat (docs/ideas/heartbeat-outside-the-app.md): the dead-man's switch.

The whole Mac-local stack can stop firing with zero notification — the ledger records
every SUCCESS and nothing ever read it for absence. heartbeat.sh is deliberately
dependency-free (no venv, no node, no claude) so it can't die the same way the sweep
pipeline does; it reads the newest ledger ``ts`` (file-mtime fallback for a mangled row)
and, past the staleness threshold, alerts OUTSIDE the app: a flag file + a notification.

Every test runs the real script in a subprocess with ledger/flag/threshold/notifier all
overridden into tmp — the real ledger, Desktop, and Notification Center are never touched.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HEARTBEAT = Path(__file__).resolve().parents[2] / "sweeps" / "schedule" / "heartbeat.sh"


def _ts(hours_ago: float) -> str:
    stamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(ts: str) -> str:
    return json.dumps({"ts": ts, "date": ts[:10], "topic": "ai-llms", "is_error": False})


def _run(tmp_path, *, ledger_lines=None, ledger_age_days=None, threshold="36", pre_flag=False):
    ledger = tmp_path / "runs.jsonl"
    if ledger_lines is not None:
        ledger.write_text("\n".join(ledger_lines) + "\n", encoding="utf-8")
        if ledger_age_days is not None:
            old = time.time() - ledger_age_days * 86_400
            os.utime(ledger, (old, old))
    flag = tmp_path / "FLAG.txt"
    if pre_flag:
        flag.write_text("stale flag from an earlier death", encoding="utf-8")
    record = tmp_path / "notified.txt"
    notifier = tmp_path / "notifier.sh"
    notifier.write_text(f'#!/bin/sh\necho "$@" >> "{record}"\n', encoding="utf-8")
    notifier.chmod(0o755)

    proc = subprocess.run(
        ["bash", str(HEARTBEAT)],
        env={
            **os.environ,
            "HEARTBEAT_LEDGER": str(ledger),
            "HEARTBEAT_FLAG": str(flag),
            "HEARTBEAT_THRESHOLD_HOURS": threshold,
            "HEARTBEAT_NOTIFIER": str(notifier),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc, flag, record


def test_fresh_ledger_is_quiet_and_clears_a_stale_flag(tmp_path):
    """A living stack: exit 0, no notification — and a flag left by an earlier death
    is removed, so the Desktop can't keep lying after recovery."""
    proc, flag, record = _run(
        tmp_path, ledger_lines=[_row(_ts(40)), _row(_ts(2))], pre_flag=True
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not flag.exists()  # the stale flag was cleared
    assert not record.exists()  # no notification fired


def test_stale_ledger_plants_the_flag_and_notifies(tmp_path):
    proc, flag, record = _run(tmp_path, ledger_lines=[_row(_ts(72))])

    assert proc.returncode != 0
    assert flag.exists()
    body = flag.read_text(encoding="utf-8")
    assert "SILENT" in body
    assert "com.homebase.sweep" in body  # points at what to check
    assert record.exists()  # the out-of-band notification fired
    assert "Home Base" in record.read_text(encoding="utf-8")


def test_missing_ledger_alerts_instead_of_assuming_health(tmp_path):
    """No ledger at all is the silence case, not a pass — the stack may never have
    run here (or the ledger was wiped with the data dir)."""
    proc, flag, record = _run(tmp_path, ledger_lines=None)

    assert proc.returncode != 0
    assert flag.exists()
    assert "no sweep ledger" in flag.read_text(encoding="utf-8")
    assert record.exists()


def test_unparseable_row_falls_back_to_fresh_file_mtime(tmp_path):
    """A mangled last row must not fake a death: the just-written file's mtime is
    still evidence of life, so the heartbeat stays quiet."""
    proc, flag, record = _run(tmp_path, ledger_lines=["{not json at all"])

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not flag.exists()
    assert not record.exists()


def test_unparseable_row_with_old_mtime_still_alerts(tmp_path):
    proc, flag, record = _run(
        tmp_path, ledger_lines=["{not json at all"], ledger_age_days=4
    )

    assert proc.returncode != 0
    assert flag.exists()
    assert record.exists()
