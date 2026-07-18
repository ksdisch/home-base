"""M7 news mode (Phase 1): Google News RSS → normalized category feeds + a short cache.

The general-news counterpart to the Mode-A sweeps: ``sweeps/news_categories.json`` names
the categories (slug, title, one or more RSS feed URLs — Local merges the Chicago and
Lake County geo feeds), and this module fetches, parses, dedupes, and serves them
newest-first. A ~15-minute TTL cache in the store keeps page loads instant and Google
unhammered. When a refresh fails and an expired payload exists we serve it marked
``stale`` — degraded honestly, never a blank page. No LLM anywhere in this path.

Google News RSS quirks handled here: item titles carry a " - Source" suffix (stripped
when it matches the ``<source>`` element), links are Google redirect URLs (kept as-is —
they open the original article), and items rarely have images (the UI is text-first).
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import get_news_cache, set_news_cache

CACHE_TTL_SECONDS = 15 * 60
FETCH_TIMEOUT_SECONDS = 10
MAX_ITEMS_PER_CATEGORY = 50

# Google's frontends reject the default urllib UA; any honest identifying string works.
_USER_AGENT = "home-base-news/1.0 (personal single-user reader)"


class NewsFeedError(Exception):
    """A feed couldn't be fetched or parsed at the document level."""


class NewsFetcher:
    """Network access as an injectable dependency — tests override it and never hit the web."""

    def fetch(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
                return resp.read()
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise NewsFeedError(f"could not fetch {url}: {e}")


def load_news_categories(path: Path) -> List[Dict[str, Any]]:
    """The category roster, in display order. Tolerant like the topic roster: a missing or
    malformed file degrades to no categories (the page says so), and a bad entry is skipped
    rather than sinking the rest."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug") or "").strip()
        title = str(entry.get("title") or "").strip()
        feeds = entry.get("feeds")
        if isinstance(feeds, str):
            feeds = [feeds]
        if not slug or not title or not isinstance(feeds, list):
            continue
        urls = [f.strip() for f in feeds if isinstance(f, str) and f.strip().startswith("http")]
        if not urls:
            continue
        out.append({"slug": slug, "title": title, "feeds": urls})
    return out


def parse_rss(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """Normalize one RSS 2.0 document into item dicts. An item without a headline or an
    http link is useless and gets skipped; an unparseable document raises."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise NewsFeedError(f"unparseable feed XML: {e}")
    items: List[Dict[str, Any]] = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not link.startswith("http"):
            continue
        source = (node.findtext("source") or "").strip() or None
        items.append(
            {
                # sha1(link)[:12] — the same read-time id shape brief items use.
                "id": hashlib.sha1(link.encode("utf-8")).hexdigest()[:12],
                "headline": _clean_headline(title, source),
                "url": link,
                "source": source,
                "published_at": _parse_pubdate(node.findtext("pubDate")),
            }
        )
    return items


def _clean_headline(title: str, source: Optional[str]) -> str:
    if source and title.endswith(f" - {source}"):
        return title[: -len(f" - {source}")].rstrip()
    return title


def _parse_pubdate(raw: Optional[str]) -> Optional[str]:
    """RFC-822 pubDate → UTC ISO 8601; None when absent or unparseable (item still served)."""
    if not raw or not raw.strip():
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _age_seconds(fetched_at: str, now: datetime) -> float:
    try:
        return (now - datetime.fromisoformat(fetched_at)).total_seconds()
    except (TypeError, ValueError):
        return float("inf")  # unreadable timestamp = expired, refetch


def get_category_items(
    category: Dict[str, Any],
    fetcher: NewsFetcher,
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """One category's items: fresh cache when young, live fetch otherwise, expired cache
    marked ``stale`` when the live fetch fails. Multi-feed categories (Local) merge and
    dedupe by item id. ``now`` is injected for deterministic TTL tests."""
    now_dt = now or datetime.now(timezone.utc)
    cached = get_news_cache(category["slug"], db_path=db_path)
    if cached is not None and _age_seconds(cached["fetched_at"], now_dt) < CACHE_TTL_SECONDS:
        return {"fetched_at": cached["fetched_at"], "stale": False, "items": cached["items"]}

    try:
        merged: Dict[str, Dict[str, Any]] = {}
        for url in category["feeds"]:
            for item in parse_rss(fetcher.fetch(url)):
                merged.setdefault(item["id"], item)
    except NewsFeedError:
        if cached is not None:
            return {"fetched_at": cached["fetched_at"], "stale": True, "items": cached["items"]}
        raise

    # Newest first; undated items (ISO string None → "") sort last.
    items = sorted(merged.values(), key=lambda i: i["published_at"] or "", reverse=True)
    items = items[:MAX_ITEMS_PER_CATEGORY]
    fetched_at = now_dt.isoformat(timespec="seconds")
    set_news_cache(category["slug"], items, fetched_at=fetched_at, db_path=db_path)
    return {"fetched_at": fetched_at, "stale": False, "items": items}
