"""Visit-source attribution (docs/ideas/builder-vs-reader-metric.md) — the v1 habit check
must judge reader-Kyle, not builder-Kyle plus the robots.

``brief_visits`` stored only (day, visited_at), so every localhost dev-server load, every
Playwright run, and every "8/8 clean" verify pass during July's build blitz counted as a
"morning visit" toward the ~08-03 ≥5-mornings/week criterion. Verified here: the coarse
origin buckets (tailnet CGNAT → phone, loopback → mac-localhost, the Vite dev origin → dev,
TestClient → test), the v14 additive migration on a pre-v14 store, the write path threading
FastAPI's ``Request``, and the two reads (mirror + habit) reporting phone-sourced distinct
days BESIDE the raw count.

The v1 criterion itself is deliberately NOT changed here — both numbers are reported and
which one certifies v1 is Kyle's call. The tests below pin that: ``mornings`` keeps counting
every source.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.store.db import (
    brief_habit_weeks,
    init_db,
    list_brief_visit_day_sources,
    list_brief_visit_days,
    record_brief_visit,
)
from app.visit_source import (
    DEV,
    LAN,
    MAC_LOCALHOST,
    OTHER,
    PHONE,
    TEST,
    UNKNOWN,
    classify_source,
    source_from_request,
)

# Same fixed local "now" as test_brief_habit.py: Thursday 2026-07-16 → current week starts
# Monday 2026-07-13, and a 4-week window covers Mondays 06-22 · 06-29 · 07-06 · 07-13.
NOW = datetime(2026, 7, 16, 9, 30)


# -- the buckets ------------------------------------------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        # Tailscale hands every node a 100.64.0.0/10 (RFC 6598 CGNAT) address — the phone
        # reaching the hub over the tailnet is the ONE signal that means reader-Kyle.
        ("100.64.0.5", PHONE),
        ("100.101.102.103", PHONE),
        ("100.127.255.255", PHONE),  # last address in /10
        # 100.x that is NOT in the CGNAT block is ordinary public space, not a tailnet peer.
        ("100.0.0.1", OTHER),
        ("100.63.255.255", OTHER),  # one below the /10
        ("100.128.0.1", OTHER),  # one above the /10
        # Builder-Kyle and the robots.
        ("127.0.0.1", MAC_LOCALHOST),
        ("::1", MAC_LOCALHOST),
        ("localhost", MAC_LOCALHOST),
        ("testclient", TEST),  # starlette's TestClient peer literal
        # Home Wi-Fi is neither loopback nor tailnet — its own honest bucket, never 'phone'.
        ("192.168.1.50", LAN),
        ("10.0.0.5", LAN),
        ("172.16.0.9", LAN),
        # Anything else.
        ("8.8.8.8", OTHER),
        ("not-an-ip", OTHER),
        ("", UNKNOWN),
        (None, UNKNOWN),
    ],
)
def test_client_host_buckets(host, expected):
    assert classify_source(host) == expected


def test_ipv6_tailnet_is_phone_not_lan():
    """Tailscale also assigns fd7a:115c:a1e0::/48. It is ULA space, so a plain is_private
    check would file the phone under 'lan' and silently undercount the honest number —
    exactly the failure this build exists to prevent."""
    assert classify_source("fd7a:115c:a1e0:ab12:4843:cd96:6265:3f01") == PHONE
    # An unrelated ULA address is still just a private peer.
    assert classify_source("fd00::1") == LAN


def test_ipv4_mapped_ipv6_is_unwrapped():
    """A dual-stack socket can report ::ffff:100.64.0.5 for a tailnet peer; unmapped or
    not, it is the same phone."""
    assert classify_source("::ffff:100.64.0.5") == PHONE
    assert classify_source("::ffff:127.0.0.1") == MAC_LOCALHOST


# -- the dev origin ---------------------------------------------------------------


def test_vite_dev_origin_wins_over_the_client_ip():
    """The Vite dev server (frontend/vite.config.ts port 5173) proxies /api to FastAPI, so
    a dev load arrives from 127.0.0.1 — but so does a real read of the deployed build on
    :8000. The Origin header is what separates them, and it must beat the IP: browsing the
    dev server over the tailnet is still build traffic, not a morning read."""
    assert classify_source("127.0.0.1", "http://localhost:5173") == DEV
    assert classify_source("100.64.0.5", "http://100.64.0.5:5173") == DEV
    assert classify_source("192.168.1.50", "http://192.168.1.50:5173") == DEV


def test_deployed_origin_is_not_dev():
    """M6 serves the built frontend from FastAPI on :8000 — the real read path."""
    assert classify_source("100.64.0.5", "http://100.64.0.5:8000") == PHONE
    assert classify_source("127.0.0.1", "http://localhost:8000") == MAC_LOCALHOST
    assert classify_source("127.0.0.1", "") == MAC_LOCALHOST
    assert classify_source("127.0.0.1", "garbage-not-a-url") == MAC_LOCALHOST


# -- Request threading ------------------------------------------------------------


class _FakeRequest:
    """The two fields the classifier reads off FastAPI's Request."""

    def __init__(self, host, headers=None):
        self.client = None if host is None else type("C", (), {"host": host})()
        self.headers = headers or {}


def test_source_from_request_reads_client_and_origin():
    assert source_from_request(_FakeRequest("100.64.0.5")) == PHONE
    assert source_from_request(_FakeRequest("127.0.0.1")) == MAC_LOCALHOST
    assert (
        source_from_request(_FakeRequest("127.0.0.1", {"origin": "http://localhost:5173"})) == DEV
    )
    # No Origin (a bare curl / the SW's fetch): fall back to Referer.
    assert (
        source_from_request(_FakeRequest("127.0.0.1", {"referer": "http://localhost:5173/brief"}))
        == DEV
    )


def test_missing_client_is_unknown_never_phone():
    """request.client is Optional in starlette. An absent peer must degrade to 'unknown' —
    a metric that guesses 'phone' when it doesn't know is the bug, not the fix."""
    assert source_from_request(_FakeRequest(None)) == UNKNOWN


# -- the write path ---------------------------------------------------------------


def _sources(db: Path) -> list:
    conn = sqlite3.connect(str(db))
    try:
        return [r[0] for r in conn.execute("SELECT source FROM brief_visits ORDER BY id")]
    finally:
        conn.close()


def test_record_brief_visit_stores_the_source(tmp_path):
    db = tmp_path / "visits.sqlite"
    init_db(db)
    row = record_brief_visit(source=PHONE, db_path=db)
    assert row["source"] == PHONE
    assert _sources(db) == [PHONE]


def test_record_brief_visit_without_a_source_is_null(tmp_path):
    """The column is nullable on purpose: July's existing rows are unattributed and must
    stay honestly unattributed rather than be back-filled with a guess."""
    db = tmp_path / "visits.sqlite"
    init_db(db)
    row = record_brief_visit(db_path=db)
    assert row["source"] is None
    assert _sources(db) == [None]


# -- the migration (v13 → v14) ----------------------------------------------------


_V13_BRIEF_VISITS = """
CREATE TABLE brief_visits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    day        TEXT NOT NULL,
    visited_at TEXT NOT NULL
)
"""


def _make_v13_store(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO schema_migrations (version) VALUES (13)")
        conn.execute(_V13_BRIEF_VISITS)
        conn.execute(
            "INSERT INTO brief_visits (day, visited_at) "
            "VALUES ('2026-07-14', '2026-07-14T07:02:00-05:00')"
        )
        conn.commit()
    finally:
        conn.close()


def _columns(db: Path, table: str) -> set:
    conn = sqlite3.connect(str(db))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_pre_v14_store_gains_a_nullable_source_column(tmp_path):
    db = tmp_path / "learning-hub.sqlite"
    _make_v13_store(db)

    init_db(db)

    assert "source" in _columns(db, "brief_visits")
    # July's row survives, still unattributed — no invented attribution.
    assert _sources(db) == [None]
    conn = sqlite3.connect(str(db))
    try:
        assert conn.execute("SELECT day FROM brief_visits").fetchone()[0] == "2026-07-14"
    finally:
        conn.close()


def test_migration_is_idempotent_under_rerun(tmp_path):
    """MIGRATIONS entries are re-run on EVERY init_db (the 2026-07-16 poisoned-ledger
    incident), so the ALTER must survive a second pass."""
    db = tmp_path / "learning-hub.sqlite"
    _make_v13_store(db)
    init_db(db)
    init_db(db)
    assert "source" in _columns(db, "brief_visits")
    assert _sources(db) == [None]


def test_fresh_store_has_the_column_from_the_create(tmp_path):
    db = tmp_path / "fresh.sqlite"
    init_db(db)
    assert "source" in _columns(db, "brief_visits")


# -- the reads: phone-sourced days BESIDE the raw count ---------------------------


def _seed(db: Path, rows: list) -> None:
    conn = sqlite3.connect(str(db))
    try:
        for day, source in rows:
            conn.execute(
                "INSERT INTO brief_visits (day, visited_at, source) VALUES (?, ?, ?)",
                (day, day + "T07:00:00", source),
            )
        conn.commit()
    finally:
        conn.close()


def test_visit_day_sources_carries_every_bucket_per_day(tmp_path):
    """The Mirror's read: distinct (day, source) pairs, so one morning read on the phone AND
    on the Mac stays one day while still showing both origins."""
    db = tmp_path / "visits.sqlite"
    init_db(db)
    _seed(
        db,
        [
            ("2026-07-15", PHONE),
            ("2026-07-15", PHONE),  # two taps, one pair
            ("2026-07-15", MAC_LOCALHOST),  # same morning, also read on the Mac
            ("2026-07-14", MAC_LOCALHOST),
            ("2026-07-13", None),  # a July row, unattributed
        ],
    )
    # The raw day list is untouched by attribution.
    assert list_brief_visit_days(db_path=db) == ["2026-07-15", "2026-07-14", "2026-07-13"]

    pairs = list_brief_visit_day_sources(db_path=db)
    by_day = {}
    for row in pairs:
        by_day.setdefault(row["day"], set()).add(row["source"])
    assert by_day == {
        "2026-07-15": {PHONE, MAC_LOCALHOST},
        "2026-07-14": {MAC_LOCALHOST},
        "2026-07-13": {None},
    }


def test_habit_weeks_reports_phone_days_beside_the_raw_count(tmp_path):
    db = tmp_path / "habit.sqlite"
    init_db(db)
    _seed(
        db,
        [
            # This week (Mon 07-13): 4 distinct days raw, but only 2 of them from the phone.
            ("2026-07-13", MAC_LOCALHOST),
            ("2026-07-14", TEST),
            ("2026-07-15", PHONE),
            ("2026-07-15", MAC_LOCALHOST),  # one morning, two sources → one day each way
            ("2026-07-16", PHONE),
            # Last week (Mon 07-06): 2 distinct days raw, 0 phone — pure build exhaust.
            ("2026-07-07", DEV),
            ("2026-07-09", None),
        ],
    )
    weeks = brief_habit_weeks(4, now=NOW, db_path=db)
    assert [w["week_start"] for w in weeks] == [
        "2026-06-22",
        "2026-06-29",
        "2026-07-06",
        "2026-07-13",
    ]
    # The v1 criterion is UNCHANGED: mornings still counts every source.
    assert [w["mornings"] for w in weeks] == [0, 0, 2, 4]
    # …and the honest number rides beside it.
    assert [w["mornings_phone"] for w in weeks] == [0, 0, 0, 2]
    # Both populated weeks carry a non-NULL source somewhere (DEV counts), so both zeros
    # above are measurements. The two empty weeks measured nothing and say so.
    assert [w["attributed"] for w in weeks] == [False, False, True, True]


def test_habit_weeks_gates_the_phone_count_on_per_week_attribution(tmp_path):
    """A week of pre-v14 rows must not be reported as a measured zero (the live shape).

    ``brief_visits.source`` arrived in v14, so July's rows are all NULL. Reporting
    ``mornings_phone: 0`` for such a week beside ``mornings: 5`` renders '5m / 0p' — the
    same fabricated accusation ``mirror.py`` refuses to make in its sentence. The
    distinction is per-week and real: on the live store the 07-20 week is all-NULL (a
    false zero) while the 08-03 week is attributed with genuinely no phone reads (a true
    zero), and only the first must lose the phone clause.
    """
    db = tmp_path / "habit.sqlite"
    init_db(db)
    _seed(
        db,
        [
            # Last week (Mon 07-06): pre-v14 rows, every source NULL — unattributed.
            ("2026-07-06", None),
            ("2026-07-07", None),
            ("2026-07-08", None),
            # This week (Mon 07-13): attribution running, and it really was all Mac.
            ("2026-07-13", MAC_LOCALHOST),
            ("2026-07-14", MAC_LOCALHOST),
        ],
    )
    weeks = brief_habit_weeks(4, now=NOW, db_path=db)
    unattributed, measured = weeks[2], weeks[3]
    assert unattributed["week_start"] == "2026-07-06"
    assert measured["week_start"] == "2026-07-13"
    # The raw count is untouched in both — attribution never moves the v1 criterion.
    assert (unattributed["mornings"], measured["mornings"]) == (3, 2)
    # Same 0, opposite epistemics: one is "not measured", the other is "measured, zero".
    assert unattributed["mornings_phone"] == 0
    assert unattributed["attributed"] is False
    assert measured["mornings_phone"] == 0
    assert measured["attributed"] is True


def test_habit_weeks_tolerates_malformed_rows(tmp_path):
    db = tmp_path / "habit.sqlite"
    init_db(db)
    _seed(db, [("garbage", PHONE), ("2026-07-15", PHONE)])
    weeks = brief_habit_weeks(4, now=NOW, db_path=db)
    assert weeks[-1]["mornings"] == 1
    assert weeks[-1]["mornings_phone"] == 1


# -- the mirror -------------------------------------------------------------------


def _mirror_for(tmp_path, monkeypatch, name: str, rows: list):
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.mirror import build_mirror
    from app.store import init_db as store_init

    store_init()
    _seed(Path(get_settings().db_path), rows)
    return build_mirror(get_settings(), [], now=NOW)


def test_mirror_reports_phone_mornings_beside_raw(tmp_path, monkeypatch):
    """build_mirror's 'You this week' must carry both numbers so the strip stops recapping
    a habit that may have been verification traffic. The raw count is NOT replaced."""
    try:
        mirror = _mirror_for(
            tmp_path,
            monkeypatch,
            "attributed",
            [
                ("2026-07-12", MAC_LOCALHOST),
                ("2026-07-13", DEV),
                ("2026-07-14", TEST),
                ("2026-07-15", PHONE),
                ("2026-07-16", PHONE),
                ("2026-07-16", MAC_LOCALHOST),  # one morning, two origins → still one day
            ],
        )
        assert mirror.sufficient is True
        assert mirror.mornings == 5  # unchanged: every source counts
        assert mirror.mornings_phone == 2  # …and the honest number beside it
        assert "You showed up 5 of the last 7 mornings (2 on your phone)" in mirror.sentence
    finally:
        from app.config import get_settings

        get_settings.cache_clear()


def test_mirror_omits_the_phone_clause_for_an_unattributed_window(tmp_path, monkeypatch):
    """July's rows carry no source. Telling Kyle "(0 on your phone)" for a window that
    predates attribution would be a fabricated accusation, not a measurement — the clause
    appears only once the window actually carries attribution."""
    try:
        mirror = _mirror_for(
            tmp_path,
            monkeypatch,
            "unattributed",
            [(f"2026-07-{d}", None) for d in (12, 13, 14, 15, 16)],
        )
        assert mirror.sufficient is True
        assert mirror.mornings == 5
        assert mirror.mornings_phone == 0
        assert "on your phone" not in mirror.sentence
        assert mirror.sentence.startswith("You showed up 5 of the last 7 mornings,")
    finally:
        from app.config import get_settings

        get_settings.cache_clear()


def test_mirror_says_zero_phone_once_the_window_is_attributed(tmp_path, monkeypatch):
    """The case the whole build exists to catch: a week that looks healthy on the raw
    number and is entirely build exhaust underneath."""
    try:
        mirror = _mirror_for(
            tmp_path,
            monkeypatch,
            "all-exhaust",
            [(f"2026-07-{d}", DEV) for d in (12, 13, 14, 15, 16)],
        )
        assert mirror.mornings == 5
        assert mirror.mornings_phone == 0
        assert "(0 on your phone)" in mirror.sentence
    finally:
        from app.config import get_settings

        get_settings.cache_clear()


# -- the endpoint -----------------------------------------------------------------


def _env(tmp_path, monkeypatch, name: str):
    sweeps = tmp_path / name / "sweeps"
    sweeps.mkdir(parents=True)
    roster_file = tmp_path / name / "topics.json"
    roster_file.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setenv("LEARNING_HUB_DATA", str(tmp_path / name / "hub"))
    monkeypatch.setenv("SWEEPS_DIR", str(sweeps))
    monkeypatch.setenv("ROSTER_FILE", str(roster_file))
    from app.config import get_settings
    from app.store import init_db as store_init

    get_settings.cache_clear()
    store_init()


def test_visit_endpoint_classifies_the_request(tmp_path, monkeypatch):
    """End-to-end: the endpoint threads Request into the write. Under TestClient the peer
    is 'testclient', so the suite's own traffic files itself as 'test' — the verify passes
    that poisoned the metric are now self-labelling."""
    _env(tmp_path, monkeypatch, "visit-src")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    try:
        body = TestClient(app).post("/api/brief/visit").json()
        assert body["ok"] is True
        assert body["source"] == TEST

        conn = sqlite3.connect(get_settings().db_path)
        try:
            assert conn.execute("SELECT source FROM brief_visits").fetchone()[0] == TEST
        finally:
            conn.close()
    finally:
        get_settings.cache_clear()


def test_visit_endpoint_tags_a_tailnet_read_as_phone(tmp_path, monkeypatch):
    """The one that matters: a real morning read from the phone over the tailnet."""
    _env(tmp_path, monkeypatch, "visit-phone")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    try:
        client = TestClient(app, client=("100.64.0.5", 51000))
        body = client.post("/api/brief/visit").json()
        assert body["source"] == PHONE

        weeks = TestClient(app).get("/api/brief/habit").json()["weeks"]
        assert weeks[-1]["mornings"] == 1
        assert weeks[-1]["mornings_phone"] == 1
    finally:
        get_settings.cache_clear()
