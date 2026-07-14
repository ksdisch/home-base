"""Read the sweep engine's output for the Today brief (M1) + the topic roster (M2).

The sweep runner (sweep.sh → sweeps/render_brief.py) writes data/sweeps/<date>/ with one
validated <topic>.json + one gradeable <topic>.md per topic. This module finds the latest
day and shapes it for GET /api/brief, with titles + display order from the config-file
roster (sweeps/topics.json). Honesty rules: an md-only day (the pre-JSON era) or a json
that won't parse degrades to a raw-markdown fallback with an error note — a topic is never
silently dropped. Strictly read-only; the backend never writes under data/sweeps.
"""

from __future__ import annotations

import json
import re
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


def latest_sweep_date(sweeps_dir: Path) -> Optional[str]:
    """Newest YYYY-MM-DD folder name, or None when no sweeps exist yet."""
    if not sweeps_dir.is_dir():
        return None
    dates = [p.name for p in sweeps_dir.iterdir() if p.is_dir() and _DATE_DIR.match(p.name)]
    return max(dates) if dates else None


def _split_md_header(text: str) -> tuple[Optional[str], str]:
    """Pull the runner's honest ``# <topic> — as of <stamp>`` header off a legacy .md brief."""
    lines = text.splitlines()
    if lines and lines[0].startswith("# ") and " — as of " in lines[0]:
        as_of = lines[0].split(" — as of ", 1)[1].strip()
        return as_of or None, "\n".join(lines[1:]).strip("\n")
    return None, text


def _structured_topic(slug: str, data: Any, titles: Dict[str, str]) -> Dict[str, Any]:
    """Shape one parsed <topic>.json; raises on anything malformed (caller falls back)."""
    items = [
        {
            "headline": str(item["headline"]),
            "attribution": str(item.get("attribution", "")),
            "digest": str(item.get("digest", "")),
            "why_it_matters": str(item.get("why_it_matters", "")),
            "sources": [
                {"title": str(s["title"]), "url": str(s["url"])} for s in item.get("sources", [])
            ],
        }
        for item in data["items"]
    ]
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
        as_of, body = _split_md_header(md_path.read_text(encoding="utf-8"))
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
                topics.append(_structured_topic(slug, data, titles))
                continue
            except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as e:
                topics.append(
                    _fallback_topic(slug, day_dir, f"unreadable {slug}.json ({e})", titles)
                )
                continue
        topics.append(_fallback_topic(slug, day_dir, None, titles))
    return topics
