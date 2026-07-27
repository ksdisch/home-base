"""Read the sweep engine's output for the Today brief (M1) + the topic roster (M2).

The sweep runner (sweep.sh → sweeps/render_brief.py) writes data/sweeps/<date>/ with one
validated <topic>.json + one gradeable <topic>.md per topic. This module finds the latest
day and shapes it for GET /api/brief, with titles + display order from the config-file
roster (sweeps/topics.json). Honesty rules: an md-only day (the pre-JSON era) or a json
that won't parse degrades to a raw-markdown fallback with an error note — a topic is never
silently dropped. Strictly read-only; the backend never writes under data/sweeps.

M3 adds read-time ``developing``/``first_seen`` labels: an item whose normalized headline or
a source URL already appeared in the last week's briefs for its topic is flagged (never
dropped) — a repeated story on a morning brief is usually a real update.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_roster(roster_file: Path) -> List[Dict[str, Any]]:
    """Ordered topic roster from sweeps/topics.json: [{slug, title, paused}] (M2).

    The roster file is the config UI for adding/pausing topics, so it's read fresh per
    request (tiny file; edits apply without a restart). A missing or invalid file degrades
    to an empty roster — humanized titles, alphabetical order — never a failed brief.
    """
    try:
        data = json.loads(roster_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    roster: List[Dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            continue
        title = entry.get("title")
        roster.append(
            {
                "slug": slug.strip(),
                "title": title.strip() if isinstance(title, str) and title.strip() else None,
                "paused": bool(entry.get("paused")),
            }
        )
    return roster


def topic_title(slug: str, titles: Dict[str, str]) -> str:
    return titles.get(slug) or slug.replace("-", " ").capitalize()


def _is_topic_stem(stem: str) -> bool:
    """True for a topic slug, false for a pipeline artifact sharing the day folder.

    The sweep writes <topic>.json / <topic>.md per topic; the audio render drops
    brief.chapters.json in beside them. Roster slugs never contain a dot, so the dotted
    stem is the marker that separates the two — the same guard sweeps/actions_queue.py
    applies (bug #1: without it brief.chapters was loaded as a topic, failed validation,
    and rendered a phantom "this topic's sweep didn't validate" card every audio morning).
    """
    return "." not in stem


def _has_renderable_content(day_dir: Path) -> bool:
    """True when the day folder holds at least one servable brief file (*.json / *.md).

    sweep.sh mkdir-p's the day folder minutes before the first topic lands, and a fully
    failed sweep leaves only .raw.txt — neither may count as a servable day, or the
    morning wake window hides yesterday's complete brief behind has_data=false. A day
    holding only pipeline artifacts (an orphan brief.chapters.json) is the same story:
    nothing to read, so not a morning.
    """
    try:
        return any(
            p.is_file() and p.suffix in (".json", ".md") and _is_topic_stem(p.stem)
            for p in day_dir.iterdir()
        )
    except OSError:
        return False


def latest_sweep_date(sweeps_dir: Path) -> Optional[str]:
    """Newest YYYY-MM-DD folder with renderable content, or None when none exists yet.

    An in-progress or fully-failed day dir (empty, or .raw.txt only) is skipped, so the
    brief, audio, and chat surfaces all serve the newest day that can actually render.
    """
    if not sweeps_dir.is_dir():
        return None
    dates = sorted(
        (p.name for p in sweeps_dir.iterdir() if p.is_dir() and _DATE_DIR.match(p.name)),
        reverse=True,
    )
    for d in dates:
        if _has_renderable_content(sweeps_dir / d):
            return d
    return None


def sweep_dates(sweeps_dir: Path) -> List[str]:
    """Every renderable YYYY-MM-DD day, oldest→newest — the archive QU1 walks.

    Same renderability bar as latest_sweep_date; the newest entry IS the latest served
    day, so callers get prev/next neighbors and the latest from one listing."""
    if not sweeps_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in sweeps_dir.iterdir()
        if p.is_dir() and _DATE_DIR.match(p.name) and _has_renderable_content(p)
    )


def _split_md_header(text: str) -> tuple[Optional[str], str]:
    """Pull the runner's honest ``# <topic> — as of <stamp>`` header off a legacy .md brief."""
    lines = text.splitlines()
    if lines and lines[0].startswith("# ") and " — as of " in lines[0]:
        as_of = lines[0].split(" — as of ", 1)[1].strip()
        return as_of or None, "\n".join(lines[1:]).strip("\n")
    return None, text


def _wager_pair(item: Dict[str, Any]) -> Dict[str, Any]:
    """Calibrated Doubt v0: the optional prediction+confidence pair, re-checked at read
    time with the same lenient-in/strict-out rules as the write side
    (sweeps/render_brief.py ``_wager_pair`` — kept in lockstep by hand, like the schema
    itself): both fields together or neither, prediction a non-empty string, confidence
    an integer 1–99 (never clamped into range). A hand-edited or pre-calibration file
    degrades to no wager, never to garbage on the page.
    """
    prediction, confidence = item.get("prediction"), item.get("confidence")
    if not isinstance(prediction, str) or not prediction.strip():
        return {}
    if isinstance(confidence, bool):
        return {}
    if isinstance(confidence, str):
        try:
            confidence = int(confidence.strip())
        except ValueError:
            return {}
    if isinstance(confidence, float):
        if 0 < confidence < 1:
            confidence = round(confidence * 100)
        elif confidence.is_integer():
            confidence = int(confidence)
        else:
            return {}
    if not isinstance(confidence, int) or not 1 <= confidence <= 99:
        return {}
    return {"prediction": prediction.strip(), "confidence": confidence}


def _structured_topic(slug: str, data: Any, titles: Dict[str, str], date: str) -> Dict[str, Any]:
    """Shape one parsed <topic>.json; raises on anything malformed (caller falls back).

    Each item gets a stable id derived at read time — sha1(date|slug|headline)[:12] — the
    anchor inline notes attach to (M2). Derived, not stored in the file: data/sweeps is
    regenerable and the pre-M2 days have no ids, so the file format stays frozen. Identical
    headlines within one brief (rare) get a ``-2``/``-3`` suffix in item order.
    """
    items: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in data["items"]:
        headline = str(item["headline"])
        base = hashlib.sha1(f"{date}|{slug}|{headline}".encode("utf-8")).hexdigest()[:12]
        item_id, n = base, 2
        while item_id in seen_ids:
            item_id = f"{base}-{n}"
            n += 1
        seen_ids.add(item_id)
        items.append(
            {
                "id": item_id,
                "headline": headline,
                "attribution": str(item.get("attribution", "")),
                "digest": str(item.get("digest", "")),
                "why_it_matters": str(item.get("why_it_matters", "")),
                "sources": [
                    {"title": str(s["title"]), "url": str(s["url"])}
                    for s in item.get("sources", [])
                ],
                # Calibrated Doubt v0: the wager lane rides the item to the page.
                **_wager_pair(item),
            }
        )
    note = data.get("context_note")
    return {
        "slug": slug,
        "title": topic_title(slug, titles),
        "as_of": str(data["as_of"]) if data.get("as_of") is not None else None,
        "top_line": str(data["top_line"]),
        "context_note": str(note) if note else None,
        "items": items,
    }


def _fallback_topic(
    slug: str, day_dir: Path, error: Optional[str], titles: Dict[str, str]
) -> Dict[str, Any]:
    """Raw-markdown view of <topic>.md (legacy md-only days, or a json that wouldn't parse)."""
    md_path = day_dir / f"{slug}.md"
    if md_path.is_file():
        try:
            as_of, body = _split_md_header(md_path.read_text(encoding="utf-8"))
        except OSError:
            pass  # bug #7: the fallback itself unreadable → the honest no-readable card below
        else:
            return {
                "slug": slug,
                "title": topic_title(slug, titles),
                "as_of": as_of,
                "raw_markdown": body,
                "error": error,
            }
    return {
        "slug": slug,
        "title": topic_title(slug, titles),
        "error": error or f"no readable brief for {slug}",
    }


_DEDUP_LOOKBACK_DAYS = 7
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_URL_SCHEME = re.compile(r"^https?://", re.IGNORECASE)


def _norm_headline(headline: str) -> str:
    """Lowercase, alphanumeric-only identity for a headline (whitespace/punctuation-insensitive)."""
    return _NON_ALNUM.sub(" ", headline.lower()).strip()


def _norm_url(url: str) -> str:
    """host+path+query identity for a source URL — drop scheme, www., fragment, trailing
    slash, and tracking params (utm_*, fbclid). The query string itself is identity (bug #6):
    watch?v=AAA and watch?v=ZZZ are different stories, and a false 'developing' label is
    exactly the mislabeling the conservative invariant forbids."""
    u = _URL_SCHEME.sub("", url.strip().lower())
    if u.startswith("www."):
        u = u[4:]
    u = u.split("#", 1)[0]
    path, _, query = u.partition("?")
    params = [
        p
        for p in query.split("&")
        if p and not p.startswith("utm_") and p.split("=", 1)[0] != "fbclid"
    ]
    path = path.rstrip("/")
    return f"{path}?{'&'.join(params)}" if params else path


def _item_identity_keys(item: Dict[str, Any]) -> set[str]:
    """Cross-day match keys for one item: its normalized headline + each normalized source URL."""
    keys: set[str] = set()
    headline = _norm_headline(str(item.get("headline", "")))
    if headline:
        keys.add(f"h:{headline}")
    for src in item.get("sources", []):
        if isinstance(src, dict):
            u = _norm_url(str(src.get("url", "")))
            if u:
                keys.add(f"u:{u}")
    return keys


def _history_first_seen(sweeps_dir: Path, slug: str, before_date: str) -> Dict[str, str]:
    """Map each prior match key → the earliest date it appeared, within the
    _DEDUP_LOOKBACK_DAYS calendar days before ``before_date`` (this topic only)."""
    if not sweeps_dir.is_dir():
        return {}
    try:
        cutoff = (date.fromisoformat(before_date) - timedelta(days=_DEDUP_LOOKBACK_DAYS)).isoformat()
    except ValueError:
        return {}
    dates = sorted(
        p.name
        for p in sweeps_dir.iterdir()
        if p.is_dir() and _DATE_DIR.match(p.name) and cutoff <= p.name < before_date
    )
    first_seen: Dict[str, str] = {}
    for d in dates:  # oldest→newest, so a key's first set is its earliest date
        path = sweeps_dir / d / f"{slug}.json"
        try:
            items = json.loads(path.read_text(encoding="utf-8"))["items"]
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                for key in _item_identity_keys(item):
                    first_seen.setdefault(key, d)
    return first_seen


def _first_seen_digest(
    sweeps_dir: Path, slug: str, day: str, keys: set[str]
) -> Optional[str]:
    """FR13: the digest of the story's first appearance — the item on ``day`` sharing one
    of today's identity keys (the same match that set the badge, so the two can't
    disagree). Verbatim bytes already on disk; any problem returns None and the badge
    stays a plain label — the brief never fails over a history lookup."""
    try:
        items = json.loads((sweeps_dir / day / f"{slug}.json").read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(items, list):
        return None
    for prior in items:
        if isinstance(prior, dict) and _item_identity_keys(prior) & keys:
            digest = str(prior.get("digest") or "").strip()
            return digest or None
    return None


def _annotate_developing(topics: List[Dict[str, Any]], sweeps_dir: Path, date: str) -> None:
    """Flag each structured item that already appeared in the last week for its topic (M3).

    ``developing`` = the same normalized headline, or a shared source URL, showed up on an
    earlier day; ``first_seen`` = that earliest date. Read-only and conservative (exact-normalized
    match, per topic) so a genuinely fresh item is never mislabeled, and nothing is ever dropped.
    Any read error just leaves items unflagged — the brief must never fail over a history lookup.

    FR13: a flagged item also carries ``prior_digest`` — the digest as it read on its
    first_seen day, verbatim — so the badge and the chat can finally name what changed.
    Deterministic bytes-from-disk only; detection itself is unchanged.
    """
    for topic in topics:
        items = topic.get("items")
        if not items:
            continue
        history = _history_first_seen(sweeps_dir, topic["slug"], date)
        if not history:
            continue
        for item in items:
            keys = _item_identity_keys(item)
            seen = [history[k] for k in keys if k in history]
            if seen:
                item["developing"] = True
                item["first_seen"] = min(seen)
                digest = _first_seen_digest(sweeps_dir, topic["slug"], item["first_seen"], keys)
                if digest:
                    item["prior_digest"] = digest


_READINESS_TOP_N = 5
_READINESS_MIN_HISTORY_DAYS = 2


def _readiness_history_dates(sweeps_dir: Path, before_date: str) -> List[str]:
    """Renderable prior mornings within the dedup window before ``before_date``, oldest→
    newest — the archive's own renderability bar, so a garbled-but-present day still counts
    as a morning while an empty/.raw.txt-only dir never does."""
    if not sweeps_dir.is_dir():
        return []
    try:
        cutoff = (date.fromisoformat(before_date) - timedelta(days=_DEDUP_LOOKBACK_DAYS)).isoformat()
    except ValueError:
        return []
    return sorted(
        p.name
        for p in sweeps_dir.iterdir()
        if p.is_dir()
        and _DATE_DIR.match(p.name)
        and cutoff <= p.name < before_date
        and _has_renderable_content(p)
    )


def _topic_history_keys(sweeps_dir: Path, slug: str, days: List[str]) -> Dict[str, set]:
    """Per prior morning, the union of identity keys in this topic's file. A missing or
    garbled day contributes nothing — fewer matches, never a failure."""
    out: Dict[str, set] = {}
    for d in days:
        path = sweeps_dir / d / f"{slug}.json"
        try:
            items = json.loads(path.read_text(encoding="utf-8"))["items"]
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
            continue
        if not isinstance(items, list):
            continue
        keys: set[str] = set()
        for item in items:
            if isinstance(item, dict):
                keys |= _item_identity_keys(item)
        if keys:
            out[d] = keys
    return out


def build_readiness(
    sweeps_dir: Path, date: str, topics: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Readiness v0 (docs/ideas/readiness-brief.md): the 'Coming up' projection for the
    served morning — which of today's stories are still in motion, read from the same
    prior-day JSON ``_annotate_developing`` walks. Identity is the badge's own keys, so
    the strip and the badge can never disagree; ranking is deterministic (mornings seen,
    then denser streak = later first_seen, then slug/headline). Below
    ``_READINESS_MIN_HISTORY_DAYS`` renderable prior mornings nothing is projected — an
    honest cold start, not a trend invented from one day of archive."""
    days = _readiness_history_dates(sweeps_dir, date)
    result: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": _DEDUP_LOOKBACK_DAYS,
        "history_days": len(days),
        "sufficient": len(days) >= _READINESS_MIN_HISTORY_DAYS,
        "items": [],
    }
    if not result["sufficient"]:
        return result

    candidates: List[Dict[str, Any]] = []
    for topic in topics:
        developing = [i for i in topic.get("items") or [] if i.get("developing")]
        if not developing:
            continue
        history = _topic_history_keys(sweeps_dir, topic["slug"], days)
        for item in developing:
            keys = _item_identity_keys(item)
            candidates.append(
                {
                    "slug": topic["slug"],
                    "title": topic["title"],
                    "item_id": item["id"],
                    "headline": item["headline"],
                    "days_seen": 1 + sum(1 for day_keys in history.values() if keys & day_keys),
                    "first_seen": item["first_seen"],
                }
            )
    # Two stable passes: slug/headline ascending underneath, then the ranking keys
    # descending on top — full ties keep readable ascending order.
    candidates.sort(key=lambda c: (c["slug"], c["headline"]))
    candidates.sort(key=lambda c: (c["days_seen"], c["first_seen"]), reverse=True)
    result["items"] = candidates[:_READINESS_TOP_N]
    return result


_CALIBRATION_TRIAL_DAYS = 7


# Grading is a check-then-act (read the ledger → decide → append) and sync FastAPI
# endpoints run on a threadpool, so the realistic phone+Mac ~06:00 double-load had both
# serves read an unwritten ledger and both append the same wagers. One process-wide lock
# over the whole critical section; the ledger is re-read inside it (bug #9).
_CALIBRATION_LOCK = threading.Lock()


def _ledger_key(row: Dict[str, Any]) -> tuple:
    """A resolution's identity: which morning's call this row grades."""
    return (row["day"], row["slug"], row["headline"])


def _read_ledger(ledger_path: Path) -> List[Dict[str, Any]]:
    """The effective record: one row per (day, slug, headline), LAST occurrence winning.

    A junk line is skipped, never fatal, and the file not existing yet is just an empty
    record. The collapse does two jobs at once. It heals duplicates a pre-lock race
    already wrote — resolved/hits sum raw rows, so a duplicate would skew the record
    permanently. And it is what makes a *supersede-by-append* correction take effect
    (docs/ideas/regradeable-calibration-ledger.md): calibration.jsonl stays append-only
    and immutable on disk, while the newest grade of a call is the one that counts.
    """
    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        confidence = row.get("confidence")
        if (
            isinstance(row.get("day"), str)
            and isinstance(row.get("slug"), str)
            and isinstance(row.get("headline"), str)
            and isinstance(confidence, int)
            and not isinstance(confidence, bool)
            and isinstance(row.get("outcome"), bool)
        ):
            rows.append(row)
    # Last-per-key, but held in first-appearance order so the record reads chronologically.
    collapsed: Dict[tuple, Dict[str, Any]] = {}
    for row in rows:
        collapsed[_ledger_key(row)] = row
    return list(collapsed.values())


def _topic_day_items(sweeps_dir: Path, day: str, slug: str) -> Optional[List[Dict[str, Any]]]:
    """The parsed items for one topic on one archived day, or None when the file is
    missing/garbled — callers must treat None as 'no sweep to grade against', never as
    an empty morning (that distinction is what keeps grading honest)."""
    path = sweeps_dir / day / f"{slug}.json"
    if not path.is_file():
        return None
    try:
        items = json.loads(path.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(items, list):
        return None
    return [i for i in items if isinstance(i, dict)]


def build_calibration(
    sweeps_dir: Path,
    date: str,
    topics: List[Dict[str, Any]],
    titles: Dict[str, str],
    ledger_path: Path,
) -> Dict[str, Any]:
    """Calibrated Doubt v0 (docs/ideas/calibrated-doubt.md): grade prior mornings'
    wagers and summarize the running ledger for the 'Yesterday's calls' strip.

    A wager (the optional prediction+confidence pair on a sweep item) is the call that
    its story shows fresh movement by the topic's NEXT readable sweep. Grading is
    deterministic — the story's identity keys (the developing badge's own normalized
    headline/source-URL match) intersect the comparator morning's keys → hit, else miss;
    a topic with no later readable sweep leaves its calls open, so a pipeline failure is
    never graded as a wrong call. Each resolution appends once to calibration.jsonl,
    keyed by (day, slug, headline); the summary recomputes hits/Brier from stored
    confidence+outcome (never trusting stored derived bytes) and keeps ``trial`` true
    below ``_CALIBRATION_TRIAL_DAYS`` distinct graded mornings — the assumption-4 gate
    the strip wears as a label until an M0-style graded week is on the books.

    A graded call is not frozen. Resweep-from-the-phone rewrites the comparator day's
    files hours after the morning grade, so a call is re-checked against the files as they
    read *now*; when the outcome flips, a superseding row is appended carrying
    ``revises_resolved_at``. Nothing on disk is ever rewritten — calibration.jsonl stays
    append-only, and ``_read_ledger``'s last-per-key collapse is what makes the correction
    count (docs/ideas/regradeable-calibration-ledger.md).
    """
    # One lock over the whole read→grade→append critical section, with the ledger read
    # inside it: two concurrent serves must not both grade and both append (bug #9).
    with _CALIBRATION_LOCK:
        ledger = _read_ledger(ledger_path)
        graded = {_ledger_key(r): r for r in ledger}

        # Today's readable items per slug — the newest comparator. Today's own wagers are
        # never graded here: their comparator doesn't exist until tomorrow's sweep.
        today_keys: Dict[str, set] = {}
        for topic in topics:
            items = topic.get("items")
            if isinstance(items, list):
                keys: set = set()
                for item in items:
                    if isinstance(item, dict):
                        keys |= _item_identity_keys(item)
                today_keys[topic["slug"]] = keys

        days = _readiness_history_dates(sweeps_dir, date)  # renderable walk, oldest→newest
        new_rows: List[Dict[str, Any]] = []
        for i, day in enumerate(days):
            day_dir = sweeps_dir / day
            try:
                slugs = sorted(
                    p.stem
                    for p in day_dir.iterdir()
                    if p.is_file() and p.suffix == ".json" and _is_topic_stem(p.stem)
                )
            except OSError:
                continue
            for slug in slugs:
                items = _topic_day_items(sweeps_dir, day, slug)
                if not items:
                    continue
                wagered = [(item, _wager_pair(item)) for item in items]
                wagered = [(item, pair) for item, pair in wagered if pair]
                if not wagered:
                    continue
                # The topic's next readable sweep: a later archived day, else today's live
                # items; a missing/garbled later file just moves the comparator onward.
                comparator: Optional[str] = None
                comparator_keys: set = set()
                for later in days[i + 1 :]:
                    later_items = _topic_day_items(sweeps_dir, later, slug)
                    if later_items is None:
                        continue
                    comparator = later
                    for it in later_items:
                        comparator_keys |= _item_identity_keys(it)
                    break
                if comparator is None and slug in today_keys:
                    comparator, comparator_keys = date, today_keys[slug]
                if comparator is None:
                    continue  # no readable later sweep yet — the calls stay open
                for item, pair in wagered:
                    headline = str(item.get("headline") or "").strip()
                    if not headline:
                        continue
                    outcome = bool(_item_identity_keys(item) & comparator_keys)
                    prior = graded.get((day, slug, headline))
                    # Already graded and the comparator still says the same thing: nothing
                    # to record. Only a genuine flip earns a row, so re-checking every
                    # serve costs the ledger nothing.
                    if prior is not None and bool(prior["outcome"]) == outcome:
                        continue
                    confidence = pair["confidence"]
                    row = {
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "day": day,
                        "comparator": comparator,
                        "slug": slug,
                        "title": topic_title(slug, titles),
                        "headline": headline,
                        "prediction": pair["prediction"],
                        "confidence": confidence,
                        "outcome": outcome,
                        "brier": round((confidence / 100 - (1 if outcome else 0)) ** 2, 3),
                    }
                    if prior is not None:
                        row["revises_resolved_at"] = prior["resolved_at"]
                    graded[(day, slug, headline)] = row
                    new_rows.append(row)

        if new_rows:
            try:
                ledger_path.parent.mkdir(parents=True, exist_ok=True)
                with ledger_path.open("a", encoding="utf-8") as fh:
                    for row in new_rows:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            except OSError:
                pass  # this morning still gets its grades; the append retries next serve
            # Rebuild from the keyed view rather than extending: a superseding row
            # REPLACES the grade it revises, it doesn't add a second one to the totals.
            ledger = list(graded.values())

    resolved = len(ledger)
    hits = sum(1 for r in ledger if r["outcome"])
    day_count = len({r["day"] for r in ledger})
    brier = (
        round(
            sum((r["confidence"] / 100 - (1 if r["outcome"] else 0)) ** 2 for r in ledger)
            / resolved,
            3,
        )
        if resolved
        else None
    )
    yesterday: List[Dict[str, Any]] = []
    if ledger:
        last_day = max(r["day"] for r in ledger)
        rows = sorted(
            (r for r in ledger if r["day"] == last_day),
            key=lambda r: (r["slug"], r["headline"]),
        )
        yesterday = [
            {
                "slug": r["slug"],
                "title": str(r.get("title") or "") or topic_title(r["slug"], titles),
                "day": r["day"],
                "headline": r["headline"],
                "prediction": str(r.get("prediction") or ""),
                "confidence": r["confidence"],
                "outcome": r["outcome"],
            }
            for r in rows
        ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": _DEDUP_LOOKBACK_DAYS,
        "resolved": resolved,
        "hits": hits,
        "days": day_count,
        "brier": brier,
        "trial": day_count < _CALIBRATION_TRIAL_DAYS,
        "yesterday": yesterday,
    }


def load_brief_topics(
    sweeps_dir: Path, date: str, roster: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Every topic in data/sweeps/<date>/, structured when possible, roster order first.

    .raw.txt files (a sweep that failed validation) are skipped — they already failed the
    trust gate loudly at sweep time and must not reach the page as content. A paused roster
    topic whose files exist for this date still displays: the pause flag gates *sweeping*,
    never what's already on disk.
    """
    day_dir = sweeps_dir / date
    if not day_dir.is_dir():
        return []

    titles = {t["slug"]: t["title"] for t in roster if t["title"]}
    roster_slugs = [t["slug"] for t in roster]

    slugs = sorted(
        {
            p.stem
            for p in day_dir.iterdir()
            if p.is_file() and p.suffix in (".json", ".md") and _is_topic_stem(p.stem)
        }
    )
    slugs = [s for s in roster_slugs if s in slugs] + [s for s in slugs if s not in set(roster_slugs)]

    topics: List[Dict[str, Any]] = []
    for slug in slugs:
        json_path = day_dir / f"{slug}.json"
        if json_path.is_file():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                topics.append(_structured_topic(slug, data, titles, date))
                continue
            except (OSError, json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as e:
                topics.append(
                    _fallback_topic(slug, day_dir, f"unreadable {slug}.json ({e})", titles)
                )
                continue
        topics.append(_fallback_topic(slug, day_dir, None, titles))

    _annotate_developing(topics, sweeps_dir, date)
    return topics
