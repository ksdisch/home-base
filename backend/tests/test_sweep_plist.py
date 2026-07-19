"""Bug #19 (docs/bug-hunt/2026-07-19-post-m7.md): launchd replays a missed
StartCalendarInterval fire only after SLEEP — after a shutdown/reboot the 06:00 fire is
simply gone, so with RunAtLoad=false a rebooted Mac serves yesterday's brief all day and
nothing runs until the next 06:00. RunAtLoad=true closes that hole; it is safe because
run-scheduled.sh exports SWEEP_SKIP_DONE=1, so an on-load fire on an already-swept day
no-ops instead of re-sweeping.

The template is parsed exactly the way install-schedule.sh materializes it: fill the
__PLACEHOLDERS__, then plistlib-load the result.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

SCHEDULE_DIR = Path(__file__).resolve().parents[2] / "sweeps" / "schedule"


def _materialized() -> dict:
    text = (SCHEDULE_DIR / "com.homebase.sweep.plist.template").read_text(encoding="utf-8")
    for placeholder, value in {
        "__WRAPPER__": "/tmp/run-scheduled.sh",
        "__NODE_BIN__": "/tmp/bin",
        "__LOG_DIR__": "/tmp/logs",
        "__HOUR__": "6",
        "__MINUTE__": "0",
    }.items():
        text = text.replace(placeholder, value)
    return plistlib.loads(text.encode("utf-8"))


def test_sweep_agent_runs_at_load_to_cover_reboots():
    """A powered-off morning must still get its sweep when the Mac comes back up."""
    assert _materialized()["RunAtLoad"] is True


def test_run_at_load_is_safe_because_the_wrapper_skips_swept_days():
    """The invariant RunAtLoad=true leans on: the scheduled wrapper always sets
    SWEEP_SKIP_DONE=1, so an on-load fire can never re-sweep an already-written day."""
    wrapper = (SCHEDULE_DIR / "run-scheduled.sh").read_text(encoding="utf-8")
    assert "export SWEEP_SKIP_DONE=1" in wrapper
