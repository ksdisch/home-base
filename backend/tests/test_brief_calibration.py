"""Calibrated Doubt v0 (docs/ideas/calibrated-doubt.md) — the brief that bets, then
grades itself.

House rules under test: the optional prediction+confidence pair rides a sweep item from
<topic>.json into the served brief (read-time pass-through mirroring the write-time
normalize()); grading is deterministic — a call wagers that its story shows fresh
movement by the topic's NEXT readable sweep, resolved by the developing badge's own
identity-key join, so the ledger and the badge can never disagree; a pipeline failure
(no later readable sweep of that topic) leaves a call open, never graded false; the
jsonl append is idempotent across serves; the summary rides only the LIVE brief.
Assumption-4 gate: ``trial`` stays true until a week of graded mornings is on the books.
"""

import json
import time

TODAY = "2026-07-16"

ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "celtics", "title": "Boston Celtics", "paused": False},
    {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False},
]

TITLES = {t["slug"]: t["title"] for t in ROSTER}


def _env(tmp_path, monkeypatch, name: str):
    """Fresh store + sweeps dir + roster + an isolated calibration ledger under tmp_path."""
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    roster_file = tmp_path / name / "topics.json"
    roster_file.write_text(json.dumps(ROSTER), encoding="utf-8")
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("ROSTER_FILE", str(roster_file))
    from app.config import get_settings
    from app.store import init_db

    get_settings.cache_clear()
    init_db()
    return sweeps, tmp_path / name / "hub" / "calibration.jsonl"


def _teardown():
    from app.config import get_settings

    get_settings.cache_clear()


def _item(headline: str, url: str, prediction=None, confidence=None) -> dict:
    item = {
        "headline": headline,
        "attribution": "Source, July 2026",
        "digest": f"digest of {headline}",
        "why_it_matters": "w",
        "sources": [{"title": "S", "url": url}],
    }
    if prediction is not None:
        item["prediction"] = prediction
    if confidence is not None:
        item["confidence"] = confidence
    return item


def _write_day(sweeps, day: str, slug: str, items: list[dict]) -> None:
    d = sweeps / day
    d.mkdir(exist_ok=True)
    payload = {
        "topic": slug,
        "date": day,
        "as_of": f"{day} 07:05 CDT",
        "top_line": "Top line.",
        "context_note": None,
        "items": items,
    }
    (d / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")


def _build(sweeps, ledger, date: str = TODAY):
    from app.sweeps import build_calibration, load_brief_topics

    topics = load_brief_topics(sweeps, date, ROSTER)
    return build_calibration(sweeps, date, topics, TITLES, ledger), topics


# -- the read-time pass-through ------------------------------------------------


def test_wager_pair_survives_to_served_items(tmp_path, monkeypatch):
    """A wager in <topic>.json rides its item into the served brief; a malformed pair on
    a hand-edited file is re-checked at read time and dropped, never served as garbage."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "pass")
    try:
        _write_day(
            sweeps,
            TODAY,
            "ai-llms",
            [
                _item("OpenAI lifts caps", "https://x.com/a", "Anthropic answers with a cut", 70),
                _item("Quiet item", "https://x.com/q"),
                _item("Hand-edited junk", "https://x.com/j", "call", "high"),
            ],
        )
        _, topics = _build(sweeps, ledger)
        items = topics[0]["items"]
        assert items[0]["prediction"] == "Anthropic answers with a cut"
        assert items[0]["confidence"] == 70
        assert "prediction" not in items[1] and "confidence" not in items[1]
        assert "prediction" not in items[2] and "confidence" not in items[2]
    finally:
        _teardown()


# -- deterministic grading -----------------------------------------------------


def test_grades_yesterdays_hit(tmp_path, monkeypatch):
    """The full read: yesterday's 70% call on a story that reappears this morning (URL
    identity — headline changed) grades TRUE into the ledger and the summary."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "hit")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers within a day", 70)],
        )
        _write_day(
            sweeps,
            TODAY,
            "ai-llms",
            [_item("Anthropic cuts prices after caps move", "https://x.com/a")],
        )

        c, _ = _build(sweeps, ledger)

        assert c["generated_at"]
        assert c["window_days"] == 7
        assert c["resolved"] == 1
        assert c["hits"] == 1
        assert c["brier"] == 0.09  # (0.70 - 1)²
        assert c["days"] == 1
        assert c["trial"] is True
        assert [
            (
                y["day"],
                y["slug"],
                y["title"],
                y["headline"],
                y["prediction"],
                y["confidence"],
                y["outcome"],
            )
            for y in c["yesterday"]
        ] == [
            (
                "2026-07-15",
                "ai-llms",
                "AI / LLMs",
                "OpenAI lifts caps",
                "A rival answers within a day",
                70,
                True,
            )
        ]

        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1
        assert rows[0]["day"] == "2026-07-15"
        assert rows[0]["comparator"] == TODAY
        assert rows[0]["outcome"] is True
        assert rows[0]["brier"] == 0.09
    finally:
        _teardown()


def test_grades_a_miss_when_the_next_sweep_ran_quiet(tmp_path, monkeypatch):
    """The topic swept this morning and the story didn't move — an honest FALSE; the
    brier pays the full 0.49 for the 70% call."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "miss")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("Unrelated fresh story", "https://x.com/z")])

        c, _ = _build(sweeps, ledger)

        assert (c["resolved"], c["hits"]) == (1, 0)
        assert c["brier"] == 0.49
        assert c["yesterday"][0]["outcome"] is False
    finally:
        _teardown()


def test_pipeline_failure_leaves_the_call_open(tmp_path, monkeypatch):
    """No readable later sweep of the topic (file missing this morning, or garbled) —
    the call stays open instead of being graded false off the pipeline's own failure."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "open")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "celtics", [_item("Tatum talks", "https://x.com/b")])

        c, _ = _build(sweeps, ledger)
        assert c["resolved"] == 0
        assert c["yesterday"] == []
        assert not ledger.exists()

        # A garbled file this morning is the same story — open, not false.
        (sweeps / TODAY / "ai-llms.json").write_text("{not json", encoding="utf-8")
        c, _ = _build(sweeps, ledger)
        assert c["resolved"] == 0
        assert not ledger.exists()
    finally:
        _teardown()


def test_pipeline_artifacts_are_never_graded_as_topics(tmp_path, monkeypatch):
    """Bug #1's grading lane: the per-day slug listing globbed every *.json stem in the
    day folder, which includes the brief.chapters.json the audio render drops there.

    Today that artifact is a JSON *list*, so ``_topic_day_items`` bails on it and the
    ledger is clean by accident of shape — not by rule. This writes a dict-shaped one to
    take that accident away: the exclusion has to be the dotted stem (the marker
    sweeps/actions_queue.py already reads), or a pipeline artifact can put rows into the
    self-grading trust record and names into 'Yesterday's calls'.
    """
    sweeps, ledger = _env(tmp_path, monkeypatch, "artifactgrading")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("A rival answered", "https://x.com/a")])
        for day in ("2026-07-15", TODAY):
            (sweeps / day / "brief.chapters.json").write_text(
                json.dumps(
                    {
                        "top_line": "Chapter offsets.",
                        "items": [
                            _item("Chapter one", "https://x.com/ch", "chips still work", 60)
                        ],
                    }
                ),
                encoding="utf-8",
            )

        c, _ = _build(sweeps, ledger)

        assert c["resolved"] == 1  # the real topic's call, and only that one
        assert [y["slug"] for y in c["yesterday"]] == ["ai-llms"]
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert [r["slug"] for r in rows] == ["ai-llms"]
    finally:
        _teardown()


def test_catchup_grades_gap_days_against_the_next_readable_sweep(tmp_path, monkeypatch):
    """A missed morning doesn't strand a call: the 07-13 wager grades against 07-15 (the
    topic's next readable sweep), the 07-15 wager against today, in one serve. The strip
    shows only the most recent graded morning."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "catchup")
    try:
        _write_day(
            sweeps,
            "2026-07-13",
            "ai-llms",
            [_item("Alpha story", "https://x.com/al", "Alpha develops", 60)],
        )
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [
                _item("Alpha story", "https://x.com/al"),
                _item("Bravo story", "https://x.com/br", "Bravo develops", 80),
            ],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("Charlie story", "https://x.com/ch")])

        c, _ = _build(sweeps, ledger)

        assert (c["resolved"], c["hits"], c["days"]) == (2, 1, 2)
        assert c["brier"] == 0.4  # mean of 0.16 (the 60% hit) and 0.64 (the 80% miss)
        assert [(y["day"], y["headline"], y["outcome"]) for y in c["yesterday"]] == [
            ("2026-07-15", "Bravo story", False)
        ]
        rows = {}
        for line in ledger.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows[row["day"]] = row
        assert rows["2026-07-13"]["comparator"] == "2026-07-15"
        assert rows["2026-07-13"]["outcome"] is True
        assert rows["2026-07-15"]["comparator"] == TODAY
    finally:
        _teardown()


def test_ledger_append_is_idempotent_across_serves(tmp_path, monkeypatch):
    sweeps, ledger = _env(tmp_path, monkeypatch, "idem")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])

        first, _ = _build(sweeps, ledger)
        second, _ = _build(sweeps, ledger)

        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1
        assert second["resolved"] == first["resolved"] == 1
        assert second["hits"] == 1 and second["brier"] == first["brier"]
    finally:
        _teardown()


def test_todays_wagers_stay_open_and_cold_start_is_honest(tmp_path, monkeypatch):
    """A wager made this morning has no comparator yet — nothing graded, no ledger file,
    trial=True; the summary still carries the honest zero record."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "cold")
    try:
        _write_day(
            sweeps,
            TODAY,
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        c, topics = _build(sweeps, ledger)
        assert (c["resolved"], c["hits"], c["days"]) == (0, 0, 0)
        assert c["brier"] is None
        assert c["trial"] is True
        assert c["yesterday"] == []
        assert not ledger.exists()
        assert topics[0]["items"][0]["confidence"] == 70  # the chip still shows the open call
    finally:
        _teardown()


def test_trial_clears_after_a_week_of_graded_mornings(tmp_path, monkeypatch):
    """Seven distinct graded mornings on the books flips trial off; a junk ledger line is
    skipped, never a failure; the record recomputes from confidence+outcome, not stored
    brier bytes."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "trial")
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for i, outcome in enumerate([True, True, True, True, True, False, False]):
            rows.append(
                json.dumps(
                    {
                        "resolved_at": "2026-07-10T12:00:00+00:00",
                        "day": f"2026-07-{i + 1:02d}",
                        "comparator": f"2026-07-{i + 2:02d}",
                        "slug": "ai-llms",
                        "title": "AI / LLMs",
                        "headline": f"Story {i}",
                        "prediction": "p",
                        "confidence": 70,
                        "outcome": outcome,
                        "brier": 999.0,  # deliberately wrong — the summary must not trust it
                    }
                )
            )
        ledger.write_text("\n".join(rows) + "\nnot json\n", encoding="utf-8")

        c, _ = _build(sweeps, ledger)

        assert (c["resolved"], c["hits"], c["days"]) == (7, 5, 7)
        assert c["trial"] is False
        assert c["brier"] == round((5 * 0.09 + 2 * 0.49) / 7, 3)
        assert [y["day"] for y in c["yesterday"]] == ["2026-07-07"]
    finally:
        _teardown()


# -- API wiring ----------------------------------------------------------------


def test_brief_carries_calibration_on_the_live_view_only(tmp_path, monkeypatch):
    """GET /api/brief (no ?date=) grades and carries the summary; a ?date= archive never
    wears it — though the archived day's own wagers still ride its items (they are part
    of that morning's record)."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "api")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(
            sweeps,
            TODAY,
            "ai-llms",
            [_item("Anthropic cuts prices", "https://x.com/a", "Round two tomorrow", 65)],
        )

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        body = client.get("/api/brief").json()
        assert body["calibration"] is not None
        assert body["calibration"]["resolved"] == 1
        assert body["calibration"]["hits"] == 1
        assert body["calibration"]["trial"] is True
        assert [y["headline"] for y in body["calibration"]["yesterday"]] == ["OpenAI lifts caps"]
        # The wager pair rides the served item for the chip.
        served_item = body["topics"][0]["items"][0]
        assert served_item["prediction"] == "Round two tomorrow"
        assert served_item["confidence"] == 65

        archived = client.get("/api/brief", params={"date": "2026-07-15"}).json()
        assert archived["calibration"] is None
        assert archived["topics"][0]["items"][0]["prediction"] == "A rival answers"

        again = client.get("/api/brief").json()  # second serve — the ledger is idempotent
        assert again["calibration"]["resolved"] == 1
    finally:
        _teardown()


def test_brief_without_a_served_day_carries_no_calibration(tmp_path, monkeypatch):
    """An empty archive has nothing to grade or summarize — has_data is false and the
    field stays None (the page-level no-sweeps story, not a zero-record strip)."""
    _env(tmp_path, monkeypatch, "empty")
    try:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        body = client.get("/api/brief").json()
        assert body["has_data"] is False
        assert body["calibration"] is None
    finally:
        _teardown()


# -- calibration integrity: the ledger must be write-once and re-gradeable ----------------
# Two holes in the same file, one theme (report #9 + docs/ideas/regradeable-calibration-ledger.md).
# The ~08-19 re-grade rides on these numbers, so a silently-wrong self-grader is worse than
# no self-grader — it launders a fabricated verdict as a measured one.


def test_concurrent_serves_append_each_grade_once(tmp_path, monkeypatch):
    """#9: build_calibration is check-then-act (read ledger → grade → append) with no
    synchronization, and FastAPI runs sync endpoints on a threadpool. The realistic
    phone+Mac ~06:00 double-load has both serves read an unwritten ledger and both append
    the same wagers — and nothing dedups on read, so the duplicate skews Brier and hit
    rate permanently in an append-only trust record.

    The grading walk is slowed to make the interleaving deterministic rather than hoped
    for; the second serve must block, re-read, and find the work already done.
    """
    import threading

    sweeps, ledger = _env(tmp_path, monkeypatch, "concurrent")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])

        import app.sweeps as sweeps_mod

        real_items = sweeps_mod._topic_day_items

        def slow_items(*a, **kw):
            time.sleep(0.05)  # widen the read→append window both serves race through
            return real_items(*a, **kw)

        monkeypatch.setattr(sweeps_mod, "_topic_day_items", slow_items)

        start = threading.Barrier(2)
        results: list = []

        def serve():
            start.wait()
            results.append(_build(sweeps, ledger)[0])

        threads = [threading.Thread(target=serve) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1, f"the wager was graded {len(rows)}x by two concurrent serves"
        assert all(c["resolved"] == 1 and c["hits"] == 1 for c in results)
    finally:
        _teardown()


def test_duplicate_rows_already_in_the_ledger_are_counted_once(tmp_path, monkeypatch):
    """The second layer, and the only repair for damage already on disk: reads collapse to
    one row per (day, slug, headline). Without it a ledger that already lost the race keeps
    double-counting that wager into Brier and hit rate forever."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "dupes")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("Live story", "https://x.com/live")])
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "resolved_at": "2026-07-16T06:00:00+00:00",
            "day": "2026-07-15",
            "comparator": TODAY,
            "slug": "ai-llms",
            "title": "AI / LLMs",
            "headline": "OpenAI lifts caps",
            "prediction": "A rival answers",
            "confidence": 70,
            "outcome": True,
            "brier": 0.09,
        }
        ledger.write_text(
            "".join(json.dumps(row) + "\n" for _ in range(3)), encoding="utf-8"
        )

        c, _ = _build(sweeps, ledger)

        # resolved/hits sum raw rows and the strip lists them, so those are what a
        # duplicate corrupts. (Brier is a mean, so identical dupes hide inside it — which
        # is exactly why the count is the assertion that matters.)
        assert c["resolved"] == 1
        assert c["hits"] == 1
        assert c["days"] == 1
        assert len(c["yesterday"]) == 1
        assert c["brier"] == 0.09
    finally:
        _teardown()


def test_a_resweep_that_lands_the_story_corrects_a_wrong_miss(tmp_path, monkeypatch):
    """The Harden hole: resweep-from-the-phone rewrites the comparator day's <slug>.json
    AFTER the morning grade, but `if key in graded: continue` meant the row never
    re-checked. A call graded MISS at 06:00 stayed a miss forever even though the 08:00
    resweep carried the story — a permanent mis-grade in the record the ~08-19 re-grade
    reads. Supersede by append: the file stays append-only, the newer row wins."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "regrade")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        # 06:00 — today's sweep ran quiet on that story, so the call grades false.
        _write_day(sweeps, TODAY, "ai-llms", [_item("Unrelated", "https://x.com/z")])
        first, _ = _build(sweeps, ledger)
        assert (first["resolved"], first["hits"]) == (1, 0)
        assert first["brier"] == 0.49

        # 08:00 — Kyle resweeps from the phone and this time the story is there.
        _write_day(
            sweeps,
            TODAY,
            "ai-llms",
            [_item("Anthropic answers the caps move", "https://x.com/a")],
        )
        second, _ = _build(sweeps, ledger)

        assert (second["resolved"], second["hits"]) == (1, 1)
        assert second["brier"] == 0.09
        assert [y["outcome"] for y in second["yesterday"]] == [True]

        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2, "append-only: the wrong row is superseded, never rewritten"
        assert rows[0]["outcome"] is False and "revises_resolved_at" not in rows[0]
        assert rows[1]["outcome"] is True
        assert rows[1]["revises_resolved_at"] == rows[0]["resolved_at"]
    finally:
        _teardown()


def test_a_resweep_that_drops_the_story_corrects_a_wrong_hit(tmp_path, monkeypatch):
    """The same seam in the other direction — proof this is a real recompute against the
    current files, not a one-way upgrade that can only ever flatter the grader."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "regradedown")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        first, _ = _build(sweeps, ledger)
        assert (first["resolved"], first["hits"]) == (1, 1)

        _write_day(sweeps, TODAY, "ai-llms", [_item("Something else", "https://x.com/z")])
        second, _ = _build(sweeps, ledger)

        assert (second["resolved"], second["hits"]) == (1, 0)
        assert second["brier"] == 0.49
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert [r["outcome"] for r in rows] == [True, False]
        assert rows[1]["revises_resolved_at"] == rows[0]["resolved_at"]
    finally:
        _teardown()


def test_an_unchanged_regrade_appends_nothing(tmp_path, monkeypatch):
    """The cost of re-checking must be zero when nothing moved. A recompute that appended
    a row per serve would grow the ledger without bound and make 'resolved' meaningless —
    only an actual outcome FLIP earns a superseding row."""
    sweeps, ledger = _env(tmp_path, monkeypatch, "nochurn")
    try:
        _write_day(
            sweeps,
            "2026-07-15",
            "ai-llms",
            [_item("OpenAI lifts caps", "https://x.com/a", "A rival answers", 70)],
        )
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])

        for _ in range(4):
            c, _ = _build(sweeps, ledger)

        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1
        assert (c["resolved"], c["hits"]) == (1, 1)
    finally:
        _teardown()
