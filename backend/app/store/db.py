"""Thin stdlib ``sqlite3`` access layer. Dependency-free; one connection per call."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..config import get_settings
from ..visit_source import PHONE
from . import scheduler
from .schema import MIGRATIONS, SCHEMA_VERSION, STATEMENTS


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _safe_alter(conn: sqlite3.Connection, stmt: str) -> None:
    """Run an additive ``ALTER TABLE ADD COLUMN``, treating "already there" as success.

    Fresh DBs already have the column (it's in STATEMENTS), so the ALTER would raise a duplicate-
    column error — that's the idempotent no-op case, not a failure. Anything else re-raises.
    """
    try:
        conn.execute(stmt)
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise


_SNAPSHOT_KEEP_DAYS = 5
_DAY_LEN = len("YYYYMMDD")


def _snapshot_now() -> datetime:
    """The snapshot clock, as a local-time instant. A seam so tests can walk days."""
    return datetime.now(timezone.utc).astimezone()


def _snapshot_day(path: Path, bak: Path) -> str:
    """The local-day bucket a ``.bak-`` sibling belongs to — the stamp's leading date."""
    start = len(f"{path.name}.bak-")
    return bak.name[start : start + _DAY_LEN]


def _snapshot_before_migrations(path: Path) -> None:
    """Copy the store's bytes before any migration can touch them (HA11,
    docs/ideas/pre-migration-snapshot.md). One Mac, one file, no managed-DB restore —
    a typo'd or shape-drifted ALTER must leave something to copy back. Unconditional,
    deliberately NOT gated on the schema_migrations ledger: the 2026-07-16 drift
    incident is exactly the case where the ledger lies about what's on disk. Only a
    missing/empty store (fresh DB) skips; a failed copy never blocks startup.
    Restore is manual by design: copy the .bak back over the store.

    Retention is DAY-BUCKETED (docs/ideas/day-bucketed-store-snapshots.md): the first
    snapshot of each local day, newest ``_SNAPSHOT_KEEP_DAYS`` days. Keeping the newest
    N *files* defeated the guard under its own scenario — the LaunchAgent runs
    KeepAlive=true and this fires on every start, so a crash loop burned all N slots
    with post-damage copies in minutes and rotated away the last clean store. The
    first copy of a day is the most pre-damage one, so once today has one we take no
    more; a later same-day snapshot would only be worse and would cost a day's slot.
    Stamps are local time so the leading date IS the bucket (pre-existing UTC-stamped
    siblings simply bucket by their UTC date, which is harmless)."""
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return
        now = _snapshot_now()
        today = now.strftime("%Y%m%d")
        siblings = sorted(path.parent.glob(f"{path.name}.bak-*"))
        if not any(_snapshot_day(path, b) == today for b in siblings):
            stamp = now.strftime("%Y%m%dT%H%M%S%f")
            shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
            siblings = sorted(path.parent.glob(f"{path.name}.bak-*"))
        days = sorted({_snapshot_day(path, b) for b in siblings})
        expired = set(days[:-_SNAPSHOT_KEEP_DAYS])
        for old in siblings:
            if _snapshot_day(path, old) in expired:
                old.unlink(missing_ok=True)
    except OSError:
        pass


def init_db(db_path: Optional[Path] = None) -> None:
    _snapshot_before_migrations(Path(db_path or get_settings().db_path))
    conn = connect(db_path)
    try:
        for stmt in STATEMENTS:
            conn.execute(stmt)
        # Apply every forward migration unconditionally — the actual table shape, not the
        # schema_migrations ledger, decides whether a column gets added (_safe_alter treats
        # "already there" as success). A ledger row can outlive the columns it records: the
        # 2026-07-16 incident had question_mastery dropped/recreated in its Phase-1 shape
        # outside the app while the ledger still said v3, so the gated version of this loop
        # skipped the ALTERs and every SM-2 surface 500'd. The ledger stays as a record of
        # when each version was first seen; it is no longer a gate.
        for version in sorted(MIGRATIONS):
            for alter in MIGRATIONS[version]:
                _safe_alter(conn, alter)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)", (version,)
            )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    finally:
        conn.close()


def _local_day(now_dt: datetime) -> str:
    """The LOCAL calendar day of a (naive-UTC or aware) instant — ``activity.day`` buckets
    match ``brief_visits``: a 7pm CDT session belongs to today, not tomorrow's UTC date
    (the hazard store/schema.py documents). Timestamps stay UTC; only day buckets are local.
    """
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    return now_dt.astimezone().date().isoformat()


def set_episode_listened(
    notebook_id: str, artifact_id: str, listened: bool, db_path: Optional[Path] = None
) -> bool:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO episode_progress (notebook_id, artifact_id, listened, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(notebook_id, artifact_id)
            DO UPDATE SET listened = excluded.listened, updated_at = datetime('now')
            """,
            (notebook_id, artifact_id, 1 if listened else 0),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), ?, ?)",
            (notebook_id, "episode_listened" if listened else "episode_unlistened"),
        )
        conn.commit()
    finally:
        conn.close()
    return listened


def save_reflection(
    notebook_id: str,
    body: str,
    *,
    episode_artifact_id: Optional[str] = None,
    grasp_rating: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist a post-episode reflection (+ an activity row for streaks). Returns its id."""
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO reflections (notebook_id, episode_artifact_id, body, grasp_rating)
            VALUES (?, ?, ?, ?)
            """,
            (notebook_id, episode_artifact_id, body, grasp_rating),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), ?, ?)",
            (notebook_id, "reflection"),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_reflections(
    notebook_id: Optional[str] = None,
    *,
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Most-recent-first reflections (optionally for one notebook).

    The `/episode-review` skill *writes* these via :func:`save_reflection`; until Phase 6 nothing
    read them back. This is that read path — newest first, capped by ``limit``.
    """
    limit = max(1, min(500, int(limit)))
    conn = connect(db_path)
    try:
        if notebook_id is not None:
            rows = conn.execute(
                "SELECT id, notebook_id, episode_artifact_id, body, grasp_rating, created_at "
                "FROM reflections WHERE notebook_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (notebook_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, notebook_id, episode_artifact_id, body, grasp_rating, created_at "
                "FROM reflections ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": int(r["id"]),
            "notebook_id": r["notebook_id"],
            "episode_artifact_id": r["episode_artifact_id"],
            "body": r["body"],
            "grasp_rating": r["grasp_rating"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def record_brief_visit(
    source: Optional[str] = None, db_path: Optional[Path] = None
) -> Dict[str, Optional[str]]:
    """Log one Today-page visit (M1's habit metric: opened ≥5 mornings/week = distinct days).

    Uses the LOCAL calendar day — "did I open it this morning" is a local-time question, and
    sqlite's ``datetime('now')`` is UTC (a 7pm CDT visit would land on tomorrow's day).

    ``source`` is the v14 origin bucket (:mod:`app.visit_source` — 'phone' = a tailnet peer,
    'mac-localhost', 'dev', 'test', …) so the v1 check can separate reader-Kyle from
    builder-Kyle plus the robots. None stays None: an unattributed visit is honestly
    unattributed, never guessed.
    """
    now = datetime.now().astimezone()
    day = now.strftime("%Y-%m-%d")
    visited_at = now.isoformat(timespec="seconds")
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO brief_visits (day, visited_at, source) VALUES (?, ?, ?)",
            (day, visited_at, source),
        )
        conn.commit()
    finally:
        conn.close()
    return {"day": day, "visited_at": visited_at, "source": source}


def list_brief_visit_days(db_path: Optional[Path] = None) -> List[str]:
    """Distinct visit days (LOCAL, by contract of record_brief_visit), newest first —
    the Mirror's mornings read."""
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT day FROM brief_visits ORDER BY day DESC").fetchall()
    finally:
        conn.close()
    return [r["day"] for r in rows]


def list_brief_visit_day_sources(
    db_path: Optional[Path] = None,
) -> List[Dict[str, Optional[str]]]:
    """Distinct (day, source) pairs, newest day first — the Mirror's attributed read (v14).

    Pairs rather than a filtered day list because the Mirror needs three things off one
    read: the raw distinct-day count, the phone-sourced count, and whether the window
    carries ANY attribution at all. That last one matters — a window of pre-v14 rows has
    no source on any row, and telling Kyle "0 on your phone" for it would be a fabricated
    accusation rather than a measurement (docs/ideas/builder-vs-reader-metric.md).
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT day, source FROM brief_visits ORDER BY day DESC"
        ).fetchall()
    finally:
        conn.close()
    return [{"day": r["day"], "source": r["source"]} for r in rows]


def brief_habit_weeks(
    weeks: int = 4,
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Per-week habit counts for the kickoff's v1 success check (≥5 mornings/week on the
    visit log, ≥3 notes/week attach — evaluated ~3 weeks in).

    Weeks are Monday-start on the LOCAL calendar, matching how the rows are written:
    ``brief_visits.day`` is already the local day (see :func:`record_brief_visit`), and
    ``brief_notes.created_at`` is sqlite's UTC ``datetime('now')`` so it's converted to
    local before bucketing — a 7pm CDT note belongs to that evening's week, not tomorrow's.
    Returns exactly ``weeks`` entries (clamped 1–12), oldest first, current week last,
    zero-filled — ``mornings`` = distinct visit days, ``notes`` = notes attached. ``now``
    is injectable for deterministic tests. Malformed hand-edited rows are skipped, never
    a 500 (defensive like the rest of the read layer).

    ``mornings_phone`` (v14) is the same distinct-day count restricted to tailnet-sourced
    visits — the honest reader-Kyle number, reported BESIDE ``mornings`` rather than
    replacing it. Changing which one certifies v1 is Kyle's call, not this function's
    (docs/ideas/builder-vs-reader-metric.md); pre-v14 rows have no source and so count
    toward ``mornings`` only.

    ``attributed`` says whether that zero means anything, per week — True once ANY of the
    week's rows carries a non-NULL source. Without it a week of pre-v14 rows is
    indistinguishable from a measured zero, and the strip renders '5m / 0p' for a week
    phone reads were never observable. Same gate, same reason as
    :func:`app.mirror.build_mirror`'s window-level flag (see
    :func:`list_brief_visit_day_sources`); the distinction is live, not hypothetical —
    July's weeks are all-NULL while 08-03 is attributed with genuinely no phone reads. A
    week with no rows at all is unattributed: nothing measured it either.
    """
    weeks = max(1, min(12, int(weeks)))
    now_dt = now or datetime.now().astimezone()
    this_monday = now_dt.date() - timedelta(days=now_dt.date().weekday())
    starts = [this_monday - timedelta(weeks=w) for w in range(weeks - 1, -1, -1)]
    slots: Dict[date, Dict[str, Any]] = {
        s: {
            "week_start": s.isoformat(),
            "mornings": 0,
            "mornings_phone": 0,
            "attributed": False,
            "notes": 0,
        }
        for s in starts
    }

    conn = connect(db_path)
    try:
        visit_rows = conn.execute("SELECT DISTINCT day, source FROM brief_visits").fetchall()
        note_rows = conn.execute("SELECT created_at FROM brief_notes").fetchall()
    finally:
        conn.close()

    # Rows are distinct (day, source) pairs, so a morning read on the phone AND on the Mac
    # arrives twice — the day sets keep both counts "distinct DAYS", never distinct rows.
    week_days: Dict[date, set] = {s: set() for s in starts}
    phone_days: Dict[date, set] = {s: set() for s in starts}
    # Whether the week has any attribution at all — tracked off the SAME rows as the two
    # day sets, so a week can never report a phone count the sources don't back.
    attributed_weeks: set = set()
    for r in visit_rows:
        try:
            d = date.fromisoformat(r["day"])
        except (TypeError, ValueError):
            continue
        monday = d - timedelta(days=d.weekday())
        if monday in slots:
            week_days[monday].add(d)
            if r["source"] is not None:
                attributed_weeks.add(monday)
            if r["source"] == PHONE:
                phone_days[monday].add(d)
    for monday in starts:
        slots[monday]["mornings"] = len(week_days[monday])
        slots[monday]["mornings_phone"] = len(phone_days[monday])
        slots[monday]["attributed"] = monday in attributed_weeks
    for r in note_rows:
        try:
            created = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            continue
        d = created.replace(tzinfo=timezone.utc).astimezone().date()
        monday = d - timedelta(days=d.weekday())
        if monday in slots:
            slots[monday]["notes"] += 1

    return [slots[s] for s in starts]


# -- brief notes (M2) -----------------------------------------------------------
# Inline notes on Today-brief items. ``item_id`` is the read-time anchor derived in
# ``app.sweeps``; the snapshot columns keep a note meaningful after its (gitignored,
# regenerable) sweep file is re-swept or gone. No ``activity`` row — that table feeds
# learning streaks, and brief state deliberately stays out of it (as with brief_visits).


def _row_to_brief_note(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "item_id": r["item_id"],
        "topic_slug": r["topic_slug"],
        "brief_date": r["brief_date"],
        "item_headline": r["item_headline"],
        "body": r["body"],
        "created_at": r["created_at"],
    }


def add_brief_note(
    item_id: str,
    topic_slug: str,
    brief_date: str,
    item_headline: str,
    body: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Attach one flat note to a brief item. Returns the new row as a dict."""
    if not body or not body.strip():
        raise ValueError("body must be a non-empty string")
    for name, value in (
        ("item_id", item_id),
        ("topic_slug", topic_slug),
        ("brief_date", brief_date),
        ("item_headline", item_headline),
    ):
        if not value or not str(value).strip():
            raise ValueError(f"{name} must be a non-empty string")
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO brief_notes (item_id, topic_slug, brief_date, item_headline, body)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item_id.strip(), topic_slug.strip(), brief_date.strip(), item_headline.strip(), body.strip()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM brief_notes WHERE id = ?", (int(cur.lastrowid),)
        ).fetchone()
        return _row_to_brief_note(row)
    finally:
        conn.close()


def list_brief_notes(
    topic_slug: Optional[str] = None,
    brief_date: Optional[str] = None,
    *,
    limit: int = 500,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Newest-first notes, optionally filtered to one topic and/or one brief day."""
    limit = max(1, min(1000, int(limit)))
    where: List[str] = []
    params: List[Any] = []
    if topic_slug is not None:
        where.append("topic_slug = ?")
        params.append(topic_slug)
    if brief_date is not None:
        where.append("brief_date = ?")
        params.append(brief_date)
    clause = f"WHERE {' AND '.join(where)} " if where else ""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM brief_notes {clause}ORDER BY created_at DESC, id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_brief_note(r) for r in rows]


def delete_brief_note(note_id: int, db_path: Optional[Path] = None) -> bool:
    """Delete one note; True if a row was actually removed."""
    conn = connect(db_path)
    try:
        cur = conn.execute("DELETE FROM brief_notes WHERE id = ?", (int(note_id),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def record_attempt(
    notebook_id: str,
    quiz_artifact_id: str,
    *,
    score: int,
    total: int,
    answers: List[Mapping[str, Any]],
    episode_artifact_id: Optional[str] = None,
    mark_listened: bool = False,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Persist a graded quiz attempt and the raw signal the mastery engines read.

    ``answers`` is one mapping per question with keys: ``question_index`` (int),
    ``question_key`` (str|None — stable per-question identity for mastery), ``chosen_index``
    (int|None), ``correct`` (bool), ``used_hint`` (bool).

    Writes ``attempts`` + ``attempt_answers``, the per-question/topic mastery signal (latest
    score + ``last_review_at`` + miss counts that Phase 4's topic decay ranks on) **and** the
    per-question SM-2 state (ease/interval/reps/lapses/``due_at``) that Phase 6's scheduler
    advances, and an ``activity`` row. If ``mark_listened`` and an ``episode_artifact_id`` is
    given, also marks that episode listened in the same transaction. ``now`` is injected for
    deterministic SM-2 scheduling (defaults to UTC now). Returns the attempt id.
    """
    now_dt = now or scheduler.now_utc()
    now_str = scheduler.fmt_ts(now_dt)
    now_date = _local_day(now_dt)  # activity.day is the LOCAL calendar day, timestamps stay UTC
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO attempts (notebook_id, quiz_artifact_id, finished_at, score, total)
            VALUES (?, ?, ?, ?, ?)
            """,
            (notebook_id, quiz_artifact_id, now_str, score, total),
        )
        attempt_id = int(cur.lastrowid)

        for a in answers:
            correct = bool(a["correct"])
            used_hint = bool(a.get("used_hint"))
            conn.execute(
                """
                INSERT INTO attempt_answers
                    (attempt_id, question_index, question_key, chosen_index, correct, used_hint)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    int(a["question_index"]),
                    a.get("question_key"),
                    a.get("chosen_index"),
                    1 if correct else 0,
                    1 if used_hint else 0,
                ),
            )
            qkey = a.get("question_key")
            if qkey is not None:
                # Raw mastery signal: clean-correct=1.0, hinted-correct=0.5, miss=0.0.
                qscore = (0.5 if used_hint else 1.0) if correct else 0.0
                # Advance this question's SM-2 state off whatever it was before.
                prev = conn.execute(
                    "SELECT ease, interval_days, reps, lapses, miss_count FROM question_mastery "
                    "WHERE notebook_id = ? AND quiz_artifact_id = ? AND question_key = ?",
                    (notebook_id, quiz_artifact_id, qkey),
                ).fetchone()
                # miss_count tracks CONSECUTIVE (unresolved) misses — how shaky this question is
                # *now*: a correct answer clears it, a miss bumps it. Accumulating forever would keep
                # a long-since-mastered question flagged shaky and over-ranked for review.
                miss_count = 0 if correct else (prev["miss_count"] if prev else 0) + 1
                state = scheduler.next_state(
                    ease=prev["ease"] if prev else scheduler.INITIAL_EASE,
                    interval_days=prev["interval_days"] if prev else 0.0,
                    reps=prev["reps"] if prev else 0,
                    lapses=prev["lapses"] if prev else 0,
                    quality=scheduler.quality_from_signal(correct, used_hint),
                    now=now_dt,
                )
                conn.execute(
                    """
                    INSERT INTO question_mastery
                        (notebook_id, quiz_artifact_id, question_key, score, miss_count,
                         last_review_at, ease, interval_days, reps, lapses, due_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(notebook_id, quiz_artifact_id, question_key)
                    DO UPDATE SET score = excluded.score,
                                  miss_count = excluded.miss_count,
                                  last_review_at = excluded.last_review_at,
                                  ease = excluded.ease,
                                  interval_days = excluded.interval_days,
                                  reps = excluded.reps,
                                  lapses = excluded.lapses,
                                  due_at = excluded.due_at
                    """,
                    (
                        notebook_id, quiz_artifact_id, qkey, qscore, miss_count, now_str,
                        state.ease, state.interval_days, state.reps, state.lapses,
                        scheduler.fmt_ts(state.due_at),
                    ),
                )

        frac = (score / total) if total else 0.0
        conn.execute(
            """
            INSERT INTO topic_mastery (notebook_id, score, last_review_at)
            VALUES (?, ?, ?)
            ON CONFLICT(notebook_id)
            DO UPDATE SET score = excluded.score, last_review_at = excluded.last_review_at
            """,
            (notebook_id, frac, now_str),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (?, ?, ?)",
            (now_date, notebook_id, "quiz_attempt"),
        )

        if mark_listened and episode_artifact_id:
            conn.execute(
                """
                INSERT INTO episode_progress (notebook_id, artifact_id, listened, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(notebook_id, artifact_id)
                DO UPDATE SET listened = 1, updated_at = excluded.updated_at
                """,
                (notebook_id, episode_artifact_id, now_str),
            )
            conn.execute(
                "INSERT INTO activity (day, notebook_id, kind) VALUES (?, ?, ?)",
                (now_date, notebook_id, "episode_listened"),
            )

        conn.commit()
        return attempt_id
    finally:
        conn.close()


def get_episode_progress(notebook_id: str, db_path: Optional[Path] = None) -> Dict[str, bool]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT artifact_id, listened FROM episode_progress WHERE notebook_id = ?",
            (notebook_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["artifact_id"]: bool(r["listened"]) for r in rows}


# -- course lesson progress ----------------------------------------------------
# Course content lives on disk (see ``app.courses.manifest``); only the "I finished this
# lesson" checkbox lives here. Mirrors ``episode_progress`` for NotebookLM episodes.

def get_course_progress(course_slug: str, db_path: Optional[Path] = None) -> Dict[str, bool]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT lesson_id, completed FROM course_lesson_progress WHERE course_slug = ?",
            (course_slug,),
        ).fetchall()
    finally:
        conn.close()
    return {r["lesson_id"]: bool(r["completed"]) for r in rows}


def set_lesson_completed(
    course_slug: str, lesson_id: str, completed: bool, db_path: Optional[Path] = None
) -> bool:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO course_lesson_progress (course_slug, lesson_id, completed, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(course_slug, lesson_id)
            DO UPDATE SET completed = excluded.completed, updated_at = datetime('now')
            """,
            (course_slug, lesson_id, 1 if completed else 0),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), NULL, ?)",
            ("lesson_completed" if completed else "lesson_uncompleted",),
        )
        conn.commit()
    finally:
        conn.close()
    return completed


# -- learning path progress (M8) -----------------------------------------------
# Path content lives on disk (see ``app.paths.manifest``); only per-step coverage ("I did this
# step") and the learner's per-step confidence self-rating live here. Coverage mirrors
# ``course_lesson_progress``; SM-2 recall stays in ``question_mastery`` under the topic's REAL
# ``notebook_id`` (a path reuses the topic's real quiz/flashcard artifacts, so no synthetic
# namespace like courses). Unlike a course lesson, a path step credits its real ``notebook_id`` on
# the activity row — coverage of a topic *is* activity for that topic.

def get_path_progress(notebook_id: str, db_path: Optional[Path] = None) -> Dict[str, bool]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT step_id, completed FROM path_step_progress WHERE notebook_id = ?",
            (notebook_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["step_id"]: bool(r["completed"]) for r in rows}


def set_step_completed(
    notebook_id: str, step_id: str, completed: bool, db_path: Optional[Path] = None
) -> bool:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO path_step_progress (notebook_id, step_id, completed, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(notebook_id, step_id)
            DO UPDATE SET completed = excluded.completed, updated_at = datetime('now')
            """,
            (notebook_id, step_id, 1 if completed else 0),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), ?, ?)",
            (notebook_id, "path_step" if completed else "path_step_undone"),
        )
        conn.commit()
    finally:
        conn.close()
    return completed


def get_path_confidence(notebook_id: str, db_path: Optional[Path] = None) -> Dict[str, int]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT step_id, rating FROM path_confidence WHERE notebook_id = ?",
            (notebook_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["step_id"]: int(r["rating"]) for r in rows}


def set_step_confidence(
    notebook_id: str, step_id: str, rating: int, db_path: Optional[Path] = None
) -> int:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO path_confidence (notebook_id, step_id, rating, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(notebook_id, step_id)
            DO UPDATE SET rating = excluded.rating, updated_at = datetime('now')
            """,
            (notebook_id, step_id, rating),
        )
        conn.commit()
    finally:
        conn.close()
    return rating


def course_quiz_progress(
    course_slug: str, *, now: Optional[datetime] = None, db_path: Optional[Path] = None
) -> Dict[str, Dict[str, Any]]:
    """Per-quiz attempt + SM-2 stats for a course, keyed by ``quiz_artifact_id`` (the material
    path). Reads the shared store under the course's ``notebook_id`` namespace (``course:<slug>``,
    see ``app.courses.COURSE_NB_PREFIX``): the latest attempt's score/total + attempt count, plus
    how many of the quiz's tracked questions are due now (per the SM-2 ``due_at``). ``now`` is
    injectable for deterministic tests. Pure read — never writes."""
    from . import mastery  # local import: mastery imports db, so defer to avoid a load-time cycle

    notebook_id = f"course:{course_slug}"
    now_dt = now or scheduler.now_utc()

    def _slot() -> Dict[str, Any]:
        return {
            "attempts": 0, "last_score": None, "last_total": None, "last_pct": None,
            "last_attempt_at": None, "tracked_questions": 0, "due_questions": 0,
        }

    conn = connect(db_path)
    try:
        attempt_rows = conn.execute(
            """
            SELECT quiz_artifact_id, score, total, finished_at
            FROM attempts
            WHERE notebook_id = ? AND finished_at IS NOT NULL
            ORDER BY quiz_artifact_id, finished_at, id
            """,
            (notebook_id,),
        ).fetchall()
        qm_rows = conn.execute(
            "SELECT quiz_artifact_id, due_at FROM question_mastery WHERE notebook_id = ?",
            (notebook_id,),
        ).fetchall()
    finally:
        conn.close()

    out: Dict[str, Dict[str, Any]] = {}
    for r in attempt_rows:  # ascending by finished_at → the last seen per quiz is the latest
        slot = out.setdefault(r["quiz_artifact_id"], _slot())
        slot["attempts"] += 1
        slot["last_score"] = r["score"]
        slot["last_total"] = r["total"]
        slot["last_pct"] = round(r["score"] / r["total"] * 100, 1) if r["total"] else 0.0
        slot["last_attempt_at"] = r["finished_at"]
    for r in qm_rows:
        slot = out.setdefault(r["quiz_artifact_id"], _slot())
        slot["tracked_questions"] += 1
        if mastery.item_is_due(r["due_at"], now_dt):
            slot["due_questions"] += 1
    return out


# -- course flashcard reviews (M2 remainder) ------------------------------------
# A flashcard self-grade advances the SAME per-item SM-2 state a quiz answer does — one
# ``question_mastery`` row per card, keyed (course:<slug>, <deck path>, <card key>). No schema
# change, and the notebook surfaces already exclude ``course:%``. Deliberately NOT an attempt:
# grading a card is item recall, not a scored quiz run, so ``attempts``/``topic_mastery`` stay
# untouched.

def record_flashcard_review(
    course_slug: str,
    deck_path: str,
    card_key: str,
    rating: str,
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Advance one card's SM-2 state from a self-grade (``again`` | ``hard`` | ``good``).

    Mirrors the per-question advance inside :func:`record_attempt` — consecutive-miss tracking,
    the same quality trio, an ``activity`` row for the streak — and returns the saved state.
    ``now`` is injected for deterministic scheduling in tests.
    """
    quality = scheduler.FLASHCARD_QUALITY.get(rating)
    if quality is None:
        raise ValueError(f"rating must be one of {sorted(scheduler.FLASHCARD_QUALITY)}")
    now_dt = now or scheduler.now_utc()
    now_str = scheduler.fmt_ts(now_dt)
    notebook_id = f"course:{course_slug}"
    # again=0.0 / hard=0.5 / good=1.0 — the same raw score signal a quiz answer writes.
    qscore = {2: 0.0, 3: 0.5, 5: 1.0}[quality]
    conn = connect(db_path)
    try:
        prev = conn.execute(
            "SELECT ease, interval_days, reps, lapses, miss_count FROM question_mastery "
            "WHERE notebook_id = ? AND quiz_artifact_id = ? AND question_key = ?",
            (notebook_id, deck_path, card_key),
        ).fetchone()
        miss_count = 0 if quality >= scheduler.PASS_QUALITY else (
            (prev["miss_count"] if prev else 0) + 1
        )
        state = scheduler.next_state(
            ease=prev["ease"] if prev else scheduler.INITIAL_EASE,
            interval_days=prev["interval_days"] if prev else 0.0,
            reps=prev["reps"] if prev else 0,
            lapses=prev["lapses"] if prev else 0,
            quality=quality,
            now=now_dt,
        )
        conn.execute(
            """
            INSERT INTO question_mastery
                (notebook_id, quiz_artifact_id, question_key, score, miss_count,
                 last_review_at, ease, interval_days, reps, lapses, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(notebook_id, quiz_artifact_id, question_key)
            DO UPDATE SET score = excluded.score,
                          miss_count = excluded.miss_count,
                          last_review_at = excluded.last_review_at,
                          ease = excluded.ease,
                          interval_days = excluded.interval_days,
                          reps = excluded.reps,
                          lapses = excluded.lapses,
                          due_at = excluded.due_at
            """,
            (
                notebook_id, deck_path, card_key, qscore, miss_count, now_str,
                state.ease, state.interval_days, state.reps, state.lapses,
                scheduler.fmt_ts(state.due_at),
            ),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (?, ?, ?)",
            (_local_day(now_dt), notebook_id, "flashcard_review"),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "reps": state.reps,
        "lapses": state.lapses,
        "ease": state.ease,
        "interval_days": state.interval_days,
        "last_review_at": now_str,
        "due_at": scheduler.fmt_ts(state.due_at),
    }


def course_flashcard_states(
    course_slug: str,
    deck_path: str,
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """One deck's tracked cards, keyed by card key: ``{reps, lapses, due_at, last_review_at,
    due}``. Cards with no row yet simply aren't present (the API treats those as *new*).
    Pure read; ``now`` is injectable like :func:`course_quiz_progress`."""
    from . import mastery  # local import: mastery imports db, so defer to avoid a load-time cycle

    now_dt = now or scheduler.now_utc()
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT question_key, reps, lapses, due_at, last_review_at FROM question_mastery "
            "WHERE notebook_id = ? AND quiz_artifact_id = ?",
            (f"course:{course_slug}", deck_path),
        ).fetchall()
    finally:
        conn.close()
    return {
        r["question_key"]: {
            "reps": int(r["reps"]),
            "lapses": int(r["lapses"]),
            "due_at": r["due_at"],
            "last_review_at": r["last_review_at"],
            "due": mastery.item_is_due(r["due_at"], now_dt),
        }
        for r in rows
    }


# -- course rubric self-assessments (M3) ---------------------------------------
# A project/capstone material can carry a rubric (criteria × levels) on disk; the learner's
# self-assessment against it lives here, keyed by the material's path (its id). Mirrors
# ``course_lesson_progress`` — content on disk, progress in SQLite. ``ratings`` is stored as a JSON
# string (criterion name -> chosen level label) and returned decoded.

def get_course_assessments(
    course_slug: str, db_path: Optional[Path] = None
) -> Dict[str, Dict[str, Any]]:
    """Every saved rubric self-assessment for a course, keyed by ``material_path``. ``ratings`` is
    decoded from JSON (a malformed row degrades to ``{}`` rather than raising — the stored string is
    hub-written, but stay defensive like the rest of the read layer)."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT material_path, self_rating, ratings, note, updated_at "
            "FROM course_rubric_assessment WHERE course_slug = ?",
            (course_slug,),
        ).fetchall()
    finally:
        conn.close()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        try:
            ratings = json.loads(r["ratings"]) if r["ratings"] else {}
        except (json.JSONDecodeError, TypeError):
            ratings = {}
        if not isinstance(ratings, dict):
            ratings = {}
        out[r["material_path"]] = {
            "self_rating": r["self_rating"],
            "ratings": {str(k): str(v) for k, v in ratings.items()},
            "note": r["note"] or "",
            "updated_at": r["updated_at"],
        }
    return out


def set_course_assessment(
    course_slug: str,
    material_path: str,
    self_rating: Optional[int],
    ratings: Mapping[str, str],
    note: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Upsert one rubric self-assessment (logs an ``activity`` row like ``set_lesson_completed``).
    Returns the saved slot. ``ratings`` is JSON-encoded; ``self_rating`` is an optional 1–5 overall."""
    ratings_json = json.dumps({str(k): str(v) for k, v in dict(ratings).items()})
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO course_rubric_assessment
                (course_slug, material_path, self_rating, ratings, note, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(course_slug, material_path)
            DO UPDATE SET self_rating = excluded.self_rating, ratings = excluded.ratings,
                          note = excluded.note, updated_at = datetime('now')
            """,
            (course_slug, material_path, self_rating, ratings_json, note or ""),
        )
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), NULL, ?)",
            ("project_assessed",),
        )
        row = conn.execute(
            "SELECT self_rating, ratings, note, updated_at FROM course_rubric_assessment "
            "WHERE course_slug = ? AND material_path = ?",
            (course_slug, material_path),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    return {
        "self_rating": row["self_rating"],
        "ratings": {str(k): str(v) for k, v in json.loads(row["ratings"]).items()},
        "note": row["note"] or "",
        "updated_at": row["updated_at"],
    }


# -- news feed cache (M7) --------------------------------------------------------
# The news mode's per-category parsed-feed cache (see ``app.news`` for TTL semantics).
# Pure cache: a corrupt payload reads as "no cache" so the next request just refetches.


def get_news_cache(
    category_slug: str, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT payload, fetched_at FROM news_feed_cache WHERE category_slug = ?",
            (category_slug,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        items = json.loads(row["payload"])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(items, list):
        return None
    return {"items": items, "fetched_at": row["fetched_at"]}


def set_news_cache(
    category_slug: str,
    items: List[Dict[str, Any]],
    *,
    fetched_at: str,
    db_path: Optional[Path] = None,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO news_feed_cache (category_slug, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(category_slug)
            DO UPDATE SET payload = excluded.payload, fetched_at = excluded.fetched_at
            """,
            (category_slug, json.dumps(items), fetched_at),
        )
        conn.commit()
    finally:
        conn.close()


# -- news events (M7 Phase 2) ----------------------------------------------------
# The For-You signal log. Item events snapshot headline/source/url — cache payloads roll
# over in minutes, and Phase 3's profile builder needs the headline terms after that.

NEWS_EVENT_KINDS = ("click", "visit", "more_like", "not_interested")
_NEWS_ITEM_KINDS = ("click", "more_like", "not_interested")


def record_news_event(
    kind: str,
    category_slug: str,
    *,
    item_id: Optional[str] = None,
    headline: Optional[str] = None,
    source: Optional[str] = None,
    url: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one interaction row. Item-scoped kinds require the item id + headline
    snapshot (a term-less event is useless to the profile builder); ``visit`` needs only
    the category. Returns the new row's id + created_at."""
    if kind not in NEWS_EVENT_KINDS:
        raise ValueError(f"kind must be one of {sorted(NEWS_EVENT_KINDS)}")
    if not category_slug or not category_slug.strip():
        raise ValueError("category_slug must be a non-empty string")
    if kind in _NEWS_ITEM_KINDS:
        if not item_id or not item_id.strip():
            raise ValueError(f"a '{kind}' event requires item_id")
        if not headline or not headline.strip():
            raise ValueError(f"a '{kind}' event requires the item headline snapshot")
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO news_events (kind, category_slug, item_id, headline, source, url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                category_slug.strip(),
                (item_id or "").strip() or None,
                (headline or "").strip() or None,
                (source or "").strip() or None,
                (url or "").strip() or None,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, created_at FROM news_events WHERE id = ?", (int(cur.lastrowid),)
        ).fetchone()
    finally:
        conn.close()
    return {"id": int(row["id"]), "created_at": row["created_at"]}


def list_news_events(
    *, limit: int = 2000, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Newest-first events — Phase 3's profile builder reads these (and nothing else)."""
    limit = max(1, min(10000, int(limit)))
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, kind, category_slug, item_id, headline, source, url, created_at "
            "FROM news_events ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": int(r["id"]),
            "kind": r["kind"],
            "category_slug": r["category_slug"],
            "item_id": r["item_id"],
            "headline": r["headline"],
            "source": r["source"],
            "url": r["url"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def add_news_dismissal(term: str, db_path: Optional[Path] = None) -> str:
    """Remember a dismissed topic-scout suggestion (M7 Phase 4) — stored lowercased,
    re-dismissing is a no-op. Returns the normalized term."""
    normalized = (term or "").strip().lower()
    if not normalized:
        raise ValueError("term must be a non-empty string")
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO news_topic_dismissals (term) VALUES (?)", (normalized,)
        )
        conn.commit()
    finally:
        conn.close()
    return normalized


def list_news_dismissals(db_path: Optional[Path] = None) -> List[str]:
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT term FROM news_topic_dismissals").fetchall()
    finally:
        conn.close()
    return [r["term"] for r in rows]


# -- custom topics -------------------------------------------------------------
# Non-NotebookLM interests (a book, a YouTube series, a loose thread) tracked loosely with
# manual progress + notes. The first writer for the Phase-5 ``custom_topics`` table; like all
# hub state it lives here in SQLite, never in the NotebookLM sidecars.

def _row_to_topic(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "title": r["title"],
        "notes": r["notes"],
        "progress_pct": int(r["progress_pct"]),
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def _validate_progress(progress_pct: int) -> int:
    if not isinstance(progress_pct, int) or isinstance(progress_pct, bool):
        raise ValueError("progress_pct must be an integer")
    if not 0 <= progress_pct <= 100:
        raise ValueError("progress_pct must be between 0 and 100")
    return progress_pct


def add_custom_topic(
    title: str,
    *,
    notes: str = "",
    progress_pct: int = 0,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a custom topic (+ an activity row for streaks). Returns the new row as a dict."""
    if not title or not title.strip():
        raise ValueError("title must be a non-empty string")
    _validate_progress(progress_pct)
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO custom_topics (title, notes, progress_pct) VALUES (?, ?, ?)",
            (title.strip(), notes, progress_pct),
        )
        topic_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), NULL, ?)",
            ("custom_topic_added",),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM custom_topics WHERE id = ?", (topic_id,)
        ).fetchone()
        return _row_to_topic(row)
    finally:
        conn.close()


def list_custom_topics(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM custom_topics ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_topic(r) for r in rows]


def get_custom_topic(
    topic_id: int, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM custom_topics WHERE id = ?", (topic_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_topic(row) if row else None


def update_custom_topic(
    topic_id: int,
    *,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    progress_pct: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Patch the provided fields (+ an activity row if anything changed). Returns the updated
    row, or ``None`` if no topic has that id. A call with nothing to change is a no-op that
    returns the current row."""
    sets: List[str] = []
    params: List[Any] = []
    if title is not None:
        if not title.strip():
            raise ValueError("title must be a non-empty string")
        sets.append("title = ?")
        params.append(title.strip())
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    if progress_pct is not None:
        _validate_progress(progress_pct)
        sets.append("progress_pct = ?")
        params.append(progress_pct)

    if not sets:  # nothing to change — return current row (None if it doesn't exist)
        return get_custom_topic(topic_id, db_path)

    sets.append("updated_at = datetime('now')")
    conn = connect(db_path)
    try:
        cur = conn.execute(
            f"UPDATE custom_topics SET {', '.join(sets)} WHERE id = ?",
            (*params, topic_id),
        )
        if cur.rowcount == 0:  # no such topic
            conn.rollback()
            return None
        conn.execute(
            "INSERT INTO activity (day, notebook_id, kind) VALUES (date('now','localtime'), NULL, ?)",
            ("custom_topic_updated",),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM custom_topics WHERE id = ?", (topic_id,)
        ).fetchone()
        return _row_to_topic(row)
    finally:
        conn.close()
