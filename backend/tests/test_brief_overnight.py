"""Overnight Chief of Staff v0 (docs/ideas/overnight-chief-of-staff.md) — the draft-only
nightly queue: Today opens with what the night pass prepared, and Kyle approves or
discards each one.

Scope decisions recorded at the 2026-07-20 gate conversation and under test here:
in-repo data ONLY (the vault bridge waits behind its own later gate); every proposal is a
draft — the pass sends and executes nothing, approve is the one real write and it lands
through the EXISTING notes path (a note on the proposal's own item, deletable like any
note); undo = discard the draft. House rules: the ledger read is tolerant (junk lines
skipped, missing file is an empty queue); the queue rides the LIVE view only (?date=
archives are records); resolution is single-shot (a second approve/discard is a 409,
never a double note); the generator reuses the M5 lane guards (five-var billing scrub,
``--tools ""``, scratch cwd, untrusted-item delimiters), reproduces the read-time
sha1(date|slug|headline)[:12] item id exactly, is idempotent per day for launchd's
on-wake re-fires, and validates the model's reply strict-out — an unoffered item_id, an
empty or oversize note, junk entries all drop, never reach the page.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

TODAY = "2026-07-16"

SCRIPT = Path(__file__).resolve().parents[2] / "sweeps" / "actions_queue.py"

ROSTER = [
    {"slug": "ai-llms", "title": "AI / LLMs", "paused": False},
    {"slug": "celtics", "title": "Boston Celtics", "paused": False},
    {"slug": "chiefs", "title": "Kansas City Chiefs", "paused": False},
    {"slug": "market", "title": "Market & tech", "paused": False},
]

TITLES = {t["slug"]: t["title"] for t in ROSTER}

LANE_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
)


def _env(tmp_path, monkeypatch, name: str):
    """Fresh store + sweeps dir + roster + an isolated overnight ledger under tmp_path."""
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
    return sweeps, roster_file, tmp_path / name / "hub" / "overnight.jsonl"


def _teardown():
    from app.config import get_settings

    get_settings.cache_clear()


def _item(headline: str, url: str, digest: str | None = None) -> dict:
    return {
        "headline": headline,
        "attribution": "Source, July 2026",
        "digest": f"digest of {headline}" if digest is None else digest,
        "why_it_matters": "w",
        "sources": [{"title": "S", "url": url}],
    }


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


def _item_id(day: str, slug: str, headline: str) -> str:
    """The read-time anchor, byte-for-byte app.sweeps._structured_topic's formula."""
    return hashlib.sha1(f"{day}|{slug}|{headline}".encode("utf-8")).hexdigest()[:12]


def _proposal_id(day: str, item_id: str) -> str:
    return hashlib.sha1(f"overnight|{day}|{item_id}".encode("utf-8")).hexdigest()[:12]


def _proposal_row(day: str, slug: str, headline: str, body: str) -> dict:
    item_id = _item_id(day, slug, headline)
    return {
        "kind": "proposal",
        "id": _proposal_id(day, item_id),
        "date": day,
        "type": "draft_note",
        "slug": slug,
        "item_id": item_id,
        "item_headline": headline,
        "body": body,
        "created_at": f"{day}T11:05:00Z",
    }


def _write_ledger(ledger: Path, *rows) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write((row if isinstance(row, str) else json.dumps(row)) + "\n")


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


# -- the served queue ------------------------------------------------------------


def test_live_brief_carries_overnight_and_archive_does_not(tmp_path, monkeypatch):
    """Proposals for the served day ride the LIVE payload with roster-resolved titles;
    the same morning fetched as a ?date= archive is a record and never wears the queue."""
    sweeps, _, ledger = _env(tmp_path, monkeypatch, "live")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        _write_ledger(
            ledger,
            _proposal_row(TODAY, "ai-llms", "OpenAI lifts caps", "Draft: what moved and why."),
            _proposal_row(TODAY, "celtics", "Tatum talks", "Draft: extension math."),
        )

        body = _client().get("/api/brief").json()
        overnight = body["overnight"]
        assert overnight is not None
        assert overnight["date"] == TODAY
        assert overnight["generated_at"]
        got = overnight["proposals"]
        assert [p["slug"] for p in got] == ["ai-llms", "celtics"]
        assert got[0]["title"] == "AI / LLMs"
        assert got[0]["type"] == "draft_note"
        assert got[0]["item_headline"] == "OpenAI lifts caps"
        assert got[0]["body"] == "Draft: what moved and why."
        assert got[0]["status"] == "proposed"
        assert got[0]["note_id"] is None
        assert got[0]["item_id"] == _item_id(TODAY, "ai-llms", "OpenAI lifts caps")

        archived = _client().get("/api/brief", params={"date": TODAY}).json()
        assert archived["overnight"] is None
    finally:
        _teardown()


def test_overnight_reduce_is_tolerant_and_a_missing_ledger_is_quiet(tmp_path, monkeypatch):
    """No ledger file → an empty queue, never an error; junk lines, wrong-kind rows,
    malformed proposals, and other days' proposals are all skipped."""
    sweeps, _, ledger = _env(tmp_path, monkeypatch, "tolerant")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])

        body = _client().get("/api/brief").json()
        assert body["overnight"] is not None
        assert body["overnight"]["proposals"] == []

        good = _proposal_row(TODAY, "ai-llms", "OpenAI lifts caps", "The one good draft.")
        _write_ledger(
            ledger,
            "not json",
            {"kind": "mystery"},
            {**_proposal_row(TODAY, "celtics", "Tatum talks", "no body"), "body": ""},
            _proposal_row("2026-07-15", "ai-llms", "Old story", "yesterday's draft"),
            good,
        )
        body = _client().get("/api/brief").json()
        got = body["overnight"]["proposals"]
        assert [p["id"] for p in got] == [good["id"]]
    finally:
        _teardown()


def test_no_served_day_no_overnight(tmp_path, monkeypatch):
    """An empty archive has no morning to queue against — the field stays None (the
    page-level no-sweeps story, not an empty strip)."""
    _env(tmp_path, monkeypatch, "empty")
    try:
        body = _client().get("/api/brief").json()
        assert body["has_data"] is False
        assert body["overnight"] is None
    finally:
        _teardown()


# -- approve / discard -----------------------------------------------------------


def test_approve_creates_the_real_note_and_persists(tmp_path, monkeypatch):
    """Approve is the one real write: a note lands through the existing notes path on the
    proposal's own item (so it joins the served brief and /notes), the ledger gets a
    status row, and the resolution survives re-serves. A second approve is a 409 —
    never a double note."""
    sweeps, _, ledger = _env(tmp_path, monkeypatch, "approve")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        row = _proposal_row(TODAY, "ai-llms", "OpenAI lifts caps", "Draft: cap math changed.")
        _write_ledger(ledger, row)
        client = _client()

        res = client.post(f"/api/brief/overnight/{row['id']}/approve")
        assert res.status_code == 200, res.text
        approved = res.json()
        assert approved["status"] == "approved"
        assert isinstance(approved["note_id"], int)
        assert approved["title"] == "AI / LLMs"

        # The note is real: it joins the served item and the /notes browse view.
        body = client.get("/api/brief").json()
        served_item = body["topics"][0]["items"][0]
        assert [n["body"] for n in served_item["notes"]] == ["Draft: cap math changed."]
        notes = client.get("/api/brief/notes").json()["notes"]
        assert [n["id"] for n in notes] == [approved["note_id"]]
        assert notes[0]["item_id"] == row["item_id"]
        assert notes[0]["brief_date"] == TODAY

        # The resolution persists across serves and is single-shot.
        again = client.get("/api/brief").json()["overnight"]["proposals"][0]
        assert again["status"] == "approved"
        assert again["note_id"] == approved["note_id"]
        assert client.post(f"/api/brief/overnight/{row['id']}/approve").status_code == 409
        assert client.post(f"/api/brief/overnight/{row['id']}/discard").status_code == 409
        assert len(client.get("/api/brief/notes").json()["notes"]) == 1

        statuses = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if json.loads(line).get("kind") == "status"
        ]
        assert len(statuses) == 1
        assert statuses[0]["id"] == row["id"]
        assert statuses[0]["status"] == "approved"
        assert statuses[0]["note_id"] == approved["note_id"]
    finally:
        _teardown()


def test_discard_is_the_undo_and_resolution_is_single_shot(tmp_path, monkeypatch):
    """Discard resolves the draft with no external effect — no note anywhere; the
    proposal stays in the payload wearing ``discarded`` (the page hides it); approve
    after discard is a 409; an unknown id is a 404 on both verbs."""
    sweeps, _, ledger = _env(tmp_path, monkeypatch, "discard")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        row = _proposal_row(TODAY, "ai-llms", "OpenAI lifts caps", "Draft to toss.")
        _write_ledger(ledger, row)
        client = _client()

        res = client.post(f"/api/brief/overnight/{row['id']}/discard")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "discarded"
        assert res.json()["note_id"] is None
        assert client.get("/api/brief/notes").json()["notes"] == []

        served = client.get("/api/brief").json()["overnight"]["proposals"]
        assert [(p["id"], p["status"]) for p in served] == [(row["id"], "discarded")]

        assert client.post(f"/api/brief/overnight/{row['id']}/approve").status_code == 409
        assert client.post(f"/api/brief/overnight/{row['id']}/discard").status_code == 409
        assert client.post("/api/brief/overnight/feedfacecafe/approve").status_code == 404
        assert client.post("/api/brief/overnight/feedfacecafe/discard").status_code == 404
    finally:
        _teardown()


# -- the nightly generator (sweeps/actions_queue.py, stub claude only) -------------

STUB_TEMPLATE = '''#!/usr/bin/env python3
import json, os, sys
capture = {capture!r}
count_file = capture + ".count"
n = int(open(count_file).read()) if os.path.exists(count_file) else 0
open(count_file, "w").write(str(n + 1))
lane = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"]
with open(capture, "w") as fh:
    json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(),
                "lane_present": [v for v in lane if v in os.environ]}}, fh)
sys.stdout.write({stdout!r})
sys.exit({exit_code})
'''


def _stub_claude(dir_path: Path, stdout: str, exit_code: int = 0) -> tuple[Path, Path]:
    """A fake claude binary that records how it was invoked — the real CLI never runs."""
    capture = dir_path / "claude-capture.json"
    stub = dir_path / "claude-stub"
    stub.write_text(
        STUB_TEMPLATE.format(capture=str(capture), stdout=stdout, exit_code=exit_code),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub, capture


def _calls(capture: Path) -> int:
    count_file = Path(str(capture) + ".count")
    return int(count_file.read_text()) if count_file.exists() else 0


def _envelope(result, cost: float = 0.01) -> str:
    return json.dumps(
        {
            "is_error": False,
            "result": result if isinstance(result, str) else json.dumps(result),
            "total_cost_usd": cost,
            "duration_ms": 5,
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
    )


def _run_script(sweeps, roster_file, out, runs_log, stub, *extra, date=TODAY, env_extra=None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--date",
            date,
            "--sweeps-dir",
            str(sweeps),
            "--roster",
            str(roster_file),
            "--out",
            str(out),
            "--runs-log",
            str(runs_log),
            "--claude-bin",
            str(stub),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _proposal_lines(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if r.get("kind") == "proposal"]


def test_drafts_proposals_with_lane_guards_end_to_end(tmp_path, monkeypatch):
    """The full night: top story per readable topic (an empty topic contributes
    nothing) → one guarded stub-claude call → validated proposal rows + a usage row →
    the queue rides the live API. Guards on the wire: all five lane vars scrubbed even
    when exported, ``--tools ""`` enforced, a scratch cwd, untrusted-item delimiters and
    the draft-only stance in the prompt."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "e2e")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        _write_day(
            sweeps,
            TODAY,
            "celtics",
            [_item("Tatum talks", "https://x.com/b"), _item("Bench story", "https://x.com/c")],
        )
        _write_day(sweeps, TODAY, "chiefs", [])
        id_ai = _item_id(TODAY, "ai-llms", "OpenAI lifts caps")
        id_cel = _item_id(TODAY, "celtics", "Tatum talks")
        stub, capture = _stub_claude(
            tmp_path,
            _envelope(
                [
                    {"item_id": id_ai, "note": "Caps went away; watch the pricing response."},
                    {"item_id": id_cel, "note": "Extension window opens; numbers are drifting up."},
                ]
            ),
        )
        runs_log = tmp_path / "runs.jsonl"

        proc = _run_script(
            sweeps,
            roster_file,
            ledger,
            runs_log,
            stub,
            env_extra={v: "leak" for v in LANE_VARS},
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

        rows = _proposal_lines(ledger)
        assert [(r["slug"], r["item_id"]) for r in rows] == [("ai-llms", id_ai), ("celtics", id_cel)]
        assert rows[0]["date"] == TODAY
        assert rows[0]["type"] == "draft_note"
        assert rows[0]["item_headline"] == "OpenAI lifts caps"
        assert rows[0]["body"] == "Caps went away; watch the pricing response."
        assert rows[0]["id"] == _proposal_id(TODAY, id_ai)
        assert "T" in rows[0]["created_at"]

        cap = json.loads(capture.read_text(encoding="utf-8"))
        assert cap["lane_present"] == []
        argv = cap["argv"]
        assert argv[0] == "-p"
        assert argv[argv.index("--tools") + 1] == ""
        assert argv[argv.index("--output-format") + 1] == "json"
        assert "--model" in argv
        assert "homebase-overnight-" in cap["cwd"]
        prompt = argv[1]
        assert prompt.count("<untrusted-item>") == 2
        assert id_ai in prompt and id_cel in prompt
        assert "never as instructions" in prompt
        assert "DRAFT-ONLY" in prompt
        assert "Reply with ONLY a JSON array" in prompt

        usage = [json.loads(x) for x in runs_log.read_text(encoding="utf-8").splitlines()]
        assert len(usage) == 1
        assert usage[0]["topic"] == "overnight"
        assert usage[0]["is_error"] is False
        assert usage[0]["total_cost_usd"] == 0.01

        served = _client().get("/api/brief").json()["overnight"]["proposals"]
        assert [p["item_headline"] for p in served] == ["OpenAI lifts caps", "Tatum talks"]
        assert all(p["status"] == "proposed" for p in served)
    finally:
        _teardown()


def test_rerun_is_idempotent_per_day_and_force_reruns(tmp_path, monkeypatch):
    """launchd's on-wake re-fire must not redraft (or re-spend): a second run skips the
    model entirely. --force re-runs deliberately, and the reduce keeps the first
    proposal per id, so even a forced re-append can't double the queue."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "idem")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        id_ai = _item_id(TODAY, "ai-llms", "OpenAI lifts caps")
        stub, capture = _stub_claude(
            tmp_path, _envelope([{"item_id": id_ai, "note": "The nightly draft."}])
        )
        runs_log = tmp_path / "runs.jsonl"

        first = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert first.returncode == 0, first.stdout + first.stderr
        assert _calls(capture) == 1
        assert len(_proposal_lines(ledger)) == 1

        second = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert second.returncode == 0, second.stdout + second.stderr
        assert _calls(capture) == 1  # claude never ran again
        assert "already" in (second.stdout + second.stderr).lower()
        assert len(_proposal_lines(ledger)) == 1

        forced = _run_script(sweeps, roster_file, ledger, runs_log, stub, "--force")
        assert forced.returncode == 0, forced.stdout + forced.stderr
        assert _calls(capture) == 2
        assert len(_proposal_lines(ledger)) == 2  # appended, same deterministic id

        served = _client().get("/api/brief").json()["overnight"]["proposals"]
        assert len(served) == 1  # first proposal per id wins in the reduce
    finally:
        _teardown()


def test_result_validation_is_strict_out(tmp_path, monkeypatch):
    """The model's reply is data, not trusted output: an unoffered item_id, an empty
    note, an oversize note, a junk entry, and a duplicate all drop — only the
    well-formed draft lands. A balanced code fence around the array is tolerated."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "strict")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        id_ai = _item_id(TODAY, "ai-llms", "OpenAI lifts caps")
        reply = [
            {"item_id": "feedfacecafe", "note": "for an item that was never offered"},
            {"item_id": id_ai, "note": "   "},
            {"item_id": id_ai, "note": "x" * 2500},
            "junk entry",
            {"item_id": id_ai, "note": "The good note."},
            {"item_id": id_ai, "note": "Duplicate — must not double the queue."},
        ]
        fenced = "```json\n" + json.dumps(reply) + "\n```"
        stub, _ = _stub_claude(tmp_path, _envelope(fenced))
        runs_log = tmp_path / "runs.jsonl"

        proc = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert proc.returncode == 0, proc.stdout + proc.stderr

        rows = _proposal_lines(ledger)
        assert [(r["item_id"], r["body"]) for r in rows] == [(id_ai, "The good note.")]
    finally:
        _teardown()


def test_zero_valid_proposals_is_a_quiet_success_with_marker(tmp_path, monkeypatch):
    """An empty (or all-dropped) reply is a legitimate quiet night: exit 0, a run
    marker so the next re-fire skips the model, and no proposal rows."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "quiet")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        stub, capture = _stub_claude(tmp_path, _envelope([]))
        runs_log = tmp_path / "runs.jsonl"

        proc = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _proposal_lines(ledger) == []
        rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
        assert [r["kind"] for r in rows] == ["run"]
        assert rows[0]["date"] == TODAY

        second = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert second.returncode == 0
        assert _calls(capture) == 1  # the marker kept the re-fire off the model
    finally:
        _teardown()


def test_claude_failure_leaves_the_ledger_untouched(tmp_path, monkeypatch):
    """A failed or garbled model run is loud (non-zero) and writes no proposals and no
    marker — the next re-fire retries. A valid envelope with a non-JSON result still
    logs its usage row: the cost was real even though nothing landed."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "fail")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("OpenAI lifts caps", "https://x.com/a")])
        runs_log = tmp_path / "runs.jsonl"

        stub, _ = _stub_claude(tmp_path, "", exit_code=1)
        proc = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert proc.returncode != 0
        assert not ledger.exists()

        stub2, _ = _stub_claude(tmp_path, _envelope("this is prose, not a JSON array"))
        proc2 = _run_script(sweeps, roster_file, ledger, runs_log, stub2)
        assert proc2.returncode != 0
        assert not ledger.exists()
        usage = [json.loads(x) for x in runs_log.read_text(encoding="utf-8").splitlines()]
        assert [u["topic"] for u in usage] == ["overnight"]
    finally:
        _teardown()


def test_caps_candidates_at_max_proposals(tmp_path, monkeypatch):
    """Four readable topics, default cap 3: only the first three (roster order) are
    offered, and a reply for the unoffered fourth id is dropped strict-out."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "cap")
    try:
        headlines = {
            "ai-llms": "OpenAI lifts caps",
            "celtics": "Tatum talks",
            "chiefs": "Mahomes rests",
            "market": "Chips rally",
        }
        for slug, headline in headlines.items():
            _write_day(sweeps, TODAY, slug, [_item(headline, f"https://x.com/{slug}")])
        ids = {slug: _item_id(TODAY, slug, h) for slug, h in headlines.items()}
        stub, capture = _stub_claude(
            tmp_path,
            _envelope([{"item_id": ids[s], "note": f"Note for {s}."} for s in headlines]),
        )
        runs_log = tmp_path / "runs.jsonl"

        proc = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert proc.returncode == 0, proc.stdout + proc.stderr

        prompt = json.loads(capture.read_text(encoding="utf-8"))["argv"][1]
        assert prompt.count("<untrusted-item>") == 3
        assert ids["market"] not in prompt
        assert [r["slug"] for r in _proposal_lines(ledger)] == ["ai-llms", "celtics", "chiefs"]
    finally:
        _teardown()


def test_thin_day_skips_claude_entirely(tmp_path, monkeypatch):
    """No candidate worth drafting on (a topic whose top story has no digest) — the
    model is never invoked, and the run marker still closes the night."""
    sweeps, roster_file, ledger = _env(tmp_path, monkeypatch, "thin")
    try:
        _write_day(sweeps, TODAY, "ai-llms", [_item("Bare headline", "https://x.com/a", digest="")])
        stub, capture = _stub_claude(tmp_path, _envelope([]))
        runs_log = tmp_path / "runs.jsonl"

        proc = _run_script(sweeps, roster_file, ledger, runs_log, stub)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _calls(capture) == 0
        rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
        assert [r["kind"] for r in rows] == ["run"]
        assert not runs_log.exists()
    finally:
        _teardown()
