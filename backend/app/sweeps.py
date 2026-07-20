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
from datetime import date, timedelta
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


def _has_renderable_content(day_dir: Path) -> bool:
    """True when the day folder holds at least one servable brief file (*.json / *.md).

    sweep.sh mkdir-p's the day folder minutes before the first topic lands, and a fully
    failed sweep leaves only .raw.txt — neither may count as a servable day, or the
    morning wake window hides yesterday's complete brief behind has_data=false.
    """
    try:
        return any(p.is_file() and p.suffix in (".json", ".md") for p in day_dir.iterdir())
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


def _split_md_header(text: str) -> tuple[Optional[str], str]:
    """Pull the runner's honest ``# <topic> — as of <stamp>`` header off a legacy .md brief."""
    lines = text.splitlines()
    if lines and lines[0].startswith("# ") and " — as of " in lines[0]:
        as_of = lines[0].split(" — as of ", 1)[1].strip()
        return as_of or None, "\n".join(lines[1:]).strip("\n")
    return None, text


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


def _annotate_developing(topics: List[Dict[str, Any]], sweeps_dir: Path, date: str) -> None:
    """Flag each structured item that already appeared in the last week for its topic (M3).

    ``developing`` = the same normalized headline, or a shared source URL, showed up on an
    earlier day; ``first_seen`` = that earliest date. Read-only and conservative (exact-normalized
    match, per topic) so a genuinely fresh item is never mislabeled, and nothing is ever dropped.
    Any read error just leaves items unflagged — the brief must never fail over a history lookup.
    """
    for topic in topics:
        items = topic.get("items")
        if not items:
            continue
        history = _history_first_seen(sweeps_dir, topic["slug"], date)
        if not history:
            continue
        for item in items:
            seen = [history[k] for k in _item_identity_keys(item) if k in history]
            if seen:
                item["developing"] = True
                item["first_seen"] = min(seen)


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
        {p.stem for p in day_dir.iterdir() if p.is_file() and p.suffix in (".json", ".md")}
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
