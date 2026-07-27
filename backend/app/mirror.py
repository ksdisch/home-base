"""Mirror v0 (docs/ideas/the-mirror.md) — 'You this week', the brief reads Kyle.

A deterministic, read-time reflection of the last 7 LOCAL days of Kyle's own logged
behavior: ``brief_visits`` (mornings), ``brief_notes``, ``news_events`` (SQLite), the
brief-chat.jsonl ledger (asks), and the roster's pause flags. No LLM call, no writes, no
stored profile — counts plus one templated framing sentence, assembled fresh on every live
``GET /api/brief``. Below the signal floor the strip says so honestly instead of
extrapolating a pattern from a handful of data points (idea-doc open question 1), and a
broken source zeroes that source only — the mirror can never break the morning read.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import BriefMirror, BriefMirrorAttention
from .store import list_brief_notes, list_brief_visit_day_sources, list_news_events
from .sweeps import topic_title
from .visit_source import PHONE

WINDOW_DAYS = 7
# Below this many total logged signals the week has no honest shape yet — render the
# insufficient state rather than a lean invented from three data points.
MIN_SIGNAL = 5
_ATTENTION_SLICES = 3

# UTC stamp formats at the two sources: sqlite's datetime('now') vs the chat ledger's ts.
_SQLITE_UTC = "%Y-%m-%d %H:%M:%S"
_LEDGER_UTC = "%Y-%m-%dT%H:%M:%SZ"


def _local_day(ts: Any, fmt: str) -> Optional[date]:
    """A UTC timestamp's LOCAL calendar day (the house bucketing rule — an evening ask
    belongs to that evening, not tomorrow); None for anything unparseable."""
    if not isinstance(ts, str):
        return None
    try:
        parsed = datetime.strptime(ts, fmt)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).astimezone().date()


def _ledger_rows(path: Path) -> List[Dict[str, Any]]:
    """brief-chat.jsonl rows, defensively: a missing/unreadable ledger is zero asks and a
    garbled line is skipped — observability exhaust must never take down the mirror."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def build_mirror(
    settings, roster: List[Dict[str, Any]], *, now: Optional[datetime] = None
) -> BriefMirror:
    """Aggregate the window's behavior into the strip's payload. ``now`` is injectable
    for deterministic tests; the roster is the one get_brief already loaded."""
    today = (now or datetime.now().astimezone()).date()
    window = {today - timedelta(days=i) for i in range(WINDOW_DAYS)}
    titles = {t["slug"]: t["title"] for t in roster if t.get("title")}

    mornings = mornings_phone = notes = asks = news = 0
    # v14: False until a visit in the window carries a source. Gates the phone clause in
    # the sentence — see list_brief_visit_day_sources.
    attributed = False
    attention: Dict[str, int] = {}

    def _touch(slug: Any) -> None:
        if isinstance(slug, str) and slug:
            attention[slug] = attention.get(slug, 0) + 1

    # Each source degrades independently: a missing table (store drift) or unreadable
    # file zeroes that source, never the endpoint.
    try:
        # v14: raw days, phone days, and whether the window is attributed at all — all off
        # one read, so a broken brief_visits zeroes them together rather than leaving a raw
        # count beside a phantom phone count.
        in_window: Dict[str, set] = {}
        for row in list_brief_visit_day_sources():
            day = row["day"]
            try:
                d = date.fromisoformat(day)
            except (TypeError, ValueError):
                continue
            if d in window:
                in_window.setdefault(day, set()).add(row["source"])
        mornings = len(in_window)
        mornings_phone = sum(1 for sources in in_window.values() if PHONE in sources)
        # Any non-NULL source anywhere in the window means attribution was running for it.
        attributed = any(s is not None for sources in in_window.values() for s in sources)
    except (sqlite3.Error, OSError):
        pass

    try:
        for n in list_brief_notes(limit=1000):
            if _local_day(n.get("created_at"), _SQLITE_UTC) in window:
                notes += 1
                _touch(n.get("topic_slug"))
    except (sqlite3.Error, OSError):
        pass

    try:
        for e in list_news_events():
            if _local_day(e.get("created_at"), _SQLITE_UTC) in window:
                news += 1
                _touch(e.get("category_slug"))
    except (sqlite3.Error, OSError):
        pass

    for row in _ledger_rows(settings.brief_chat_ledger):
        if _local_day(row.get("ts"), _LEDGER_UTC) in window:
            asks += 1
            _touch(row.get("topic"))

    total_keyed = sum(attention.values())
    slices = [
        BriefMirrorAttention(
            slug=slug,
            title=topic_title(slug, titles),
            events=count,
            share_pct=round(100 * count / total_keyed),
        )
        # Determinism: biggest share first, slug order breaking ties.
        for slug, count in sorted(attention.items(), key=lambda kv: (-kv[1], kv[0]))[
            :_ATTENTION_SLICES
        ]
    ]

    sufficient = (mornings + notes + asks + news) >= MIN_SIGNAL
    sentence = ""
    if sufficient:
        # v14: the phone-sourced count rides BESIDE the raw one — the strip used to recap a
        # "habit" that could be pure localhost/verify traffic. Gated on ``attributed``: a
        # window whose rows all predate attribution gets the original sentence, because
        # "(0 on your phone)" there would be a fabricated accusation, not a measurement.
        phone_clause = f" ({mornings_phone} on your phone)" if attributed else ""
        sentence = (
            f"You showed up {mornings} of the last {WINDOW_DAYS} mornings{phone_clause}, "
            f"left {_count(notes, 'note')}, and asked {_count(asks, 'question')}"
        )
        if slices:
            sentence += f" — attention leaned {slices[0].share_pct}% {slices[0].title}."
        else:
            sentence += "."

    return BriefMirror(
        generated_at=datetime.now(timezone.utc).isoformat(),
        window_days=WINDOW_DAYS,
        sufficient=sufficient,
        sentence=sentence,
        mornings=mornings,
        mornings_phone=mornings_phone,
        notes=notes,
        asks=asks,
        news_events=news,
        attention=slices,
        paused_topics=[topic_title(t["slug"], titles) for t in roster if t.get("paused")],
    )
