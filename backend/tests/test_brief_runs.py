"""runs_summary + GET /api/brief/runs/summary — the sweep cost/health readout.

``sweeps/envelope.py`` has appended a row per topic run to ``data/sweeps/.runs.jsonl`` since
M3 (its own docstring calls the file "the durable answer to what do the sweeps cost"), and
nobody ever wrote the totaler — so the one place sweep pathology shows up mechanically is
grep-only on the Mac (docs/ideas/sweep-ledger-readout.md).

The two shapes that matter are both real in the live ledger: a day **missing entirely**
(07-24) and a day that ran but cost $1-2 against a ~$10 norm (07-23, 07-25). Skipping absent
days would hide the first and averaging would bury the second, so the window is calendar-dense
(a day with no rows is present and ``ran: false``) and a thin day is flagged against the
window's own median. Zero LLM, read-only, tolerant of a hand-mangled line.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.sweeps import runs_summary


def _row(date: str, topic: str, *, cost=1.0, ms=60_000, error=False) -> dict:
    """A ledger row in envelope.py's shape (only the fields the summary reads)."""
    return {
        "ts": f"{date}T11:30:00Z",
        "date": date,
        "topic": topic,
        "model": "claude-opus-5",
        "is_error": error,
        "total_cost_usd": cost,
        "duration_ms": ms,
        "num_turns": 7,
    }


def _ledger(tmp_path: Path, rows) -> Path:
    sweeps = tmp_path / "sweeps"
    sweeps.mkdir(parents=True, exist_ok=True)
    body = "".join(
        (r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows
    )
    (sweeps / ".runs.jsonl").write_text(body, encoding="utf-8")
    return sweeps


# -- the totaler -------------------------------------------------------------------


def test_a_days_rows_total_into_one_line(tmp_path):
    sweeps = _ledger(
        tmp_path,
        [
            _row("2026-07-26", "ai-llms", cost=3.5, ms=400_000),
            _row("2026-07-26", "chicago", cost=2.5, ms=300_000),
            _row("2026-07-26", "markets", cost=2.12, ms=560_000),
        ],
    )

    summary = runs_summary(sweeps, days=7, today="2026-07-26")

    latest = summary["latest"]
    assert latest["date"] == "2026-07-26"
    assert latest["topics"] == 3
    assert latest["cost_usd"] == pytest.approx(8.12)
    assert latest["duration_ms"] == 1_260_000  # 21 minutes
    assert latest["errors"] == 0
    assert latest["ran"] is True


def test_error_runs_are_counted_but_still_cost_money(tmp_path):
    """envelope.py logs a failed run deliberately — it burned tokens. The line must say so."""
    sweeps = _ledger(
        tmp_path,
        [
            _row("2026-07-26", "ai-llms", cost=1.0),
            _row("2026-07-26", "chicago", cost=0.4, error=True),
        ],
    )

    latest = runs_summary(sweeps, days=7, today="2026-07-26")["latest"]

    assert latest["topics"] == 2
    assert latest["errors"] == 1
    assert latest["cost_usd"] == pytest.approx(1.4)


def test_one_topic_swept_twice_counts_once(tmp_path):
    """A re-sweep appends a second row for the same topic; "9 topics" must stay a topic
    count, not a row count — while the cost of both runs still totals."""
    sweeps = _ledger(
        tmp_path,
        [_row("2026-07-26", "ai-llms", cost=1.0), _row("2026-07-26", "ai-llms", cost=1.0)],
    )

    latest = runs_summary(sweeps, days=7, today="2026-07-26")["latest"]

    assert latest["topics"] == 1
    assert latest["cost_usd"] == pytest.approx(2.0)


# -- the anomalies the live ledger is carrying right now ---------------------------


def test_a_missing_day_is_present_in_the_window_not_skipped(tmp_path):
    """The 07-24 shape. A day with no rows at all is the loudest signal in the file and
    the easiest one to lose — the window is calendar-dense so the gap has somewhere to
    show up."""
    sweeps = _ledger(
        tmp_path,
        [_row("2026-07-23", "ai-llms"), _row("2026-07-25", "ai-llms")],
    )

    summary = runs_summary(sweeps, days=3, today="2026-07-25")

    assert [d["date"] for d in summary["days"]] == ["2026-07-25", "2026-07-24", "2026-07-23"]
    gap = summary["days"][1]
    assert gap["ran"] is False and gap["topics"] == 0 and gap["cost_usd"] == 0
    assert summary["missing_days"] == 1


def test_a_day_far_under_the_norm_is_flagged_thin(tmp_path):
    """The 07-23/07-25 shape: it ran, so nothing is "missing" — but $1-2 against a ~$10
    norm is the mechanical shadow of a thin or half-failed sweep.

    The tell sits on a PAST day, not on ``today``: a day is only comparable to the norm
    once it is over (see ``test_the_in_flight_morning_is_not_flagged_thin``)."""
    rows = [_row(f"2026-07-{d:02d}", f"t{n}", cost=2.5) for d in (18, 19, 21, 22) for n in range(4)]
    rows += [_row("2026-07-20", "ai-llms", cost=1.20)]  # the tell
    sweeps = _ledger(tmp_path, rows)

    days = {d["date"]: d for d in runs_summary(sweeps, days=5, today="2026-07-22")["days"]}

    assert days["2026-07-20"]["thin"] is True
    assert days["2026-07-21"]["thin"] is False
    assert days["2026-07-20"]["ran"] is True  # thin is not missing


def test_the_in_flight_morning_is_not_flagged_thin(tmp_path):
    """sweeps/envelope.py appends one row per topic AS EACH FINISHES, so between 06:04 and
    06:20 CT today's ``cost_usd`` is a partial sum — and a partial sum measured against a
    full day's norm reads as "thin or half-failed" on the one strip whose entire job is
    honest trust reporting, during exactly the window Kyle is reading it.

    ``end`` is the only day whose incompleteness is knowable (the ledger carries no
    completion sentinel), so it is never judged. The day is still reported in full — it
    just doesn't get compared to a norm it can't be compared to yet."""
    rows = [_row(f"2026-07-{d:02d}", f"t{n}", cost=2.5) for d in (18, 19, 20, 21) for n in range(4)]
    rows += [_row("2026-07-22", "ai-llms", cost=1.86)]  # first topic in; five still running

    summary = runs_summary(_ledger(tmp_path, rows), days=5, today="2026-07-22")
    days = {d["date"]: d for d in summary["days"]}

    assert days["2026-07-22"]["thin"] is False
    assert days["2026-07-22"]["ran"] is True  # it ran — the line still reports it
    assert days["2026-07-22"]["cost_usd"] == pytest.approx(1.86)
    assert summary["cost_usd"] == pytest.approx(41.86)  # and it still totals into the rollup


def test_a_partial_today_cannot_drag_the_norm_down_and_mask_a_thin_day(tmp_path):
    """The other half of the same defect: an in-flight day is not a sample of what a day
    costs, so letting it into the median biases the norm toward zero — here a $0.50 today
    pulls the norm from $9.00 to $2.00 and silently un-flags two genuinely thin days."""
    rows = [_row(f"2026-07-{d:02d}", f"t{n}", cost=8.0) for d in (20, 21) for n in range(2)]
    rows += [_row("2026-07-18", "ai-llms", cost=2.0), _row("2026-07-19", "ai-llms", cost=2.0)]
    rows += [_row("2026-07-22", "ai-llms", cost=0.5)]  # today, one topic in

    days = {d["date"]: d for d in runs_summary(_ledger(tmp_path, rows), days=5, today="2026-07-22")["days"]}

    assert days["2026-07-18"]["thin"] is True
    assert days["2026-07-19"]["thin"] is True
    assert days["2026-07-20"]["thin"] is False


def test_a_normal_week_flags_nothing(tmp_path):
    """The guard against a readout that cries wolf every morning."""
    rows = [
        _row(f"2026-07-{d:02d}", f"t{n}", cost=2.5 + n * 0.1)
        for d in (20, 21, 22, 23, 24)
        for n in range(4)
    ]
    sweeps = _ledger(tmp_path, rows)

    summary = runs_summary(sweeps, days=5, today="2026-07-24")

    assert not any(d["thin"] for d in summary["days"])
    assert summary["missing_days"] == 0


# -- honesty + tolerance -----------------------------------------------------------


def test_a_mangled_line_is_skipped_never_fatal(tmp_path):
    sweeps = _ledger(
        tmp_path,
        [
            _row("2026-07-26", "ai-llms", cost=1.0),
            "{not json at all",
            "[]",  # valid JSON, wrong shape
            json.dumps({"date": "2026-07-26"}),  # no topic: unusable
            _row("2026-07-26", "chicago", cost=1.0),
        ],
    )

    latest = runs_summary(sweeps, days=7, today="2026-07-26")["latest"]

    assert latest["topics"] == 2
    assert latest["cost_usd"] == pytest.approx(2.0)


def test_a_null_cost_row_still_counts_as_a_topic(tmp_path):
    """envelope.py writes null when the envelope had no cost — the run happened."""
    sweeps = _ledger(
        tmp_path,
        [
            _row("2026-07-26", "ai-llms", cost=None, ms=None),
            _row("2026-07-26", "chicago", cost=2.0),
        ],
    )

    latest = runs_summary(sweeps, days=7, today="2026-07-26")["latest"]

    assert latest["topics"] == 2
    assert latest["cost_usd"] == pytest.approx(2.0)


def test_no_ledger_yet_is_an_honest_empty_readout(tmp_path):
    sweeps = tmp_path / "sweeps"
    sweeps.mkdir()

    summary = runs_summary(sweeps, days=7, today="2026-07-26")

    assert summary["latest"] is None
    assert summary["cost_usd"] == 0 and summary["errors"] == 0
    assert len(summary["days"]) == 7 and all(d["ran"] is False for d in summary["days"])


def test_latest_is_the_newest_day_that_actually_ran(tmp_path):
    """If this morning hasn't swept yet, the line must name the day it IS reporting rather
    than label a stale total "this morning"."""
    sweeps = _ledger(tmp_path, [_row("2026-07-24", "ai-llms", cost=9.0)])

    latest = runs_summary(sweeps, days=7, today="2026-07-26")["latest"]

    assert latest["date"] == "2026-07-24"  # the caller compares it to today and says so


# -- the endpoint ------------------------------------------------------------------


def _client(tmp_path, monkeypatch, rows):
    sweeps = _ledger(tmp_path, rows)
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    from app.config import get_settings

    get_settings.cache_clear()


def test_endpoint_serves_the_summary(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        [_row("2026-07-26", "ai-llms", cost=3.0, ms=600_000), _row("2026-07-26", "chicago", cost=5.12)],
    )

    body = client.get("/api/brief/runs/summary").json()

    assert body["latest"]["topics"] == 2
    assert body["latest"]["cost_usd"] == pytest.approx(8.12)
    assert body["window_days"] == 7
    assert len(body["days"]) == 7  # calendar-dense, so a gap is visible


def test_endpoint_clamps_the_window(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, [_row("2026-07-26", "ai-llms")])

    assert len(client.get("/api/brief/runs/summary?days=999").json()["days"]) <= 90
    assert len(client.get("/api/brief/runs/summary?days=0").json()["days"]) >= 1


def test_endpoint_without_a_ledger_is_200_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEEPS_DIR", str(tmp_path / "nothing-here"))
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / "hub"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()

    resp = TestClient(app).get("/api/brief/runs/summary")

    assert resp.status_code == 200
    assert resp.json()["latest"] is None
