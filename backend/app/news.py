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
import logging
import os
import re
import tempfile
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .foryou import dedup_by_headline
from .store import get_news_cache, set_news_cache

logger = logging.getLogger(__name__)

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


_PROMPT_TEMPLATE_NAME = "_template.md"

# Bug #12: serializes append_roster_topic's read-modify-write (single-process is the
# deployed shape — one uvicorn behind the LaunchAgent).
_roster_write_lock = threading.Lock()


def _write_topic_prompt(roster_file: Path, slug: str, title: str) -> None:
    """Ensure ``prompts/<slug>.md`` exists before the roster names the topic (P1 bug #2).

    sweep.sh requires a prompt file per roster topic and counts its absence as a failure
    (rc=1 every morning), so the add must produce both artifacts or neither. The prompt
    is stamped from the checked-in ``_template.md`` living next to the hand-written
    prompts (same strict-JSON contract, same M0-tuned sourcing bar); an existing file —
    a hand-tuned prompt — is never overwritten. Raises ValueError when no usable
    template exists: better to refuse the add than to poison every subsequent sweep.
    """
    prompts_dir = Path(roster_file).parent / "prompts"
    prompt_path = prompts_dir / f"{slug}.md"
    if prompt_path.is_file():
        return
    try:
        template = (prompts_dir / _PROMPT_TEMPLATE_NAME).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"sweep prompt template is unusable ({e}) — topic not added")
    tmp = Path(f"{prompt_path}.tmp")
    tmp.write_text(template.replace("{{TITLE}}", title), encoding="utf-8")
    tmp.replace(prompt_path)


def append_roster_topic(roster_file: Path, term: str) -> Dict[str, Any]:
    """The topic scout's one write (M7 Phase 4): append a suggested term to the Mode-A
    roster (``sweeps/topics.json``) so the next 06:00 sweep picks it up. The file is the
    hub's own config — this is the single deliberate Mode-B → Mode-A bridge. Preserves
    the existing entries verbatim, refuses duplicates by slug, and writes atomically
    (sweep.sh reads this file). Also stamps ``prompts/<slug>.md`` from the generic
    template first — prompt then roster, so a failure can never leave a roster topic
    the sweep counts as a permanent failure (an orphan prompt file is inert and gets
    reused on retry). Raises ValueError on bad input or an unusable roster/template."""
    term = (term or "").strip()
    if not term:
        raise ValueError("term must be a non-empty string")
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", term.lower())).strip("-")
    if not slug:
        raise ValueError(f"could not derive a slug from {term!r}")
    # Bug #12: FastAPI runs sync handlers on a threadpool, so two Add taps can race the
    # read→dupe-check→write→replace and silently drop the loser's entry. One process
    # writes this file from the app, so a module lock serializes it; the unique tempfile
    # (vs a fixed .tmp name) keeps an out-of-process writer from clobbering our staging.
    with _roster_write_lock:
        try:
            roster = json.loads(Path(roster_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"roster file is unusable: {e}")
        if not isinstance(roster, list):
            raise ValueError("roster file is unusable: not a JSON list")
        if any(isinstance(t, dict) and t.get("slug") == slug for t in roster):
            raise ValueError(f"'{slug}' is already on the roster")
        entry = {"slug": slug, "title": term.title(), "paused": False}
        _write_topic_prompt(roster_file, slug, entry["title"])
        fd, tmp_name = tempfile.mkstemp(
            dir=str(Path(roster_file).parent), prefix=f"{Path(roster_file).name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(roster + [entry], indent=2) + "\n")
            Path(tmp_name).replace(roster_file)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
    return entry


def parse_rss(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """Normalize one RSS 2.0 document into item dicts. An item without a headline or an
    http link is useless and gets skipped; an unparseable document raises.

    Per-item ``<source>`` is a Google News extra; plain outlet feeds (WordPress etc. —
    the Uplifting category's good-news sites) don't carry it, so those items fall back
    to the feed's channel title ("Good News Network") for attribution."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise NewsFeedError(f"unparseable feed XML: {e}")
    channel_title = (root.findtext("channel/title") or "").strip() or None
    items: List[Dict[str, Any]] = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not link.startswith("http"):
            continue
        source = (node.findtext("source") or "").strip() or channel_title
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
    marked ``stale`` when the live fetch fails. Multi-feed categories (Local, Uplifting)
    merge and dedupe by item id — and fail per feed: one dead host must not discard the
    feeds that succeeded, or the category freezes on an ever-staler cache while that
    host stays down. Stale-cache/raise honesty applies only when *every* feed failed.
    ``now`` is injected for deterministic TTL tests."""
    now_dt = now or datetime.now(timezone.utc)
    cached = get_news_cache(category["slug"], db_path=db_path)
    if cached is not None and _age_seconds(cached["fetched_at"], now_dt) < CACHE_TTL_SECONDS:
        return {"fetched_at": cached["fetched_at"], "stale": False, "items": cached["items"]}

    merged: Dict[str, Dict[str, Any]] = {}
    ok_feeds = 0
    last_error: Optional[NewsFeedError] = None
    for url in category["feeds"]:
        try:
            for item in parse_rss(fetcher.fetch(url)):
                merged.setdefault(item["id"], item)
        except NewsFeedError as e:
            last_error = e
            continue
        ok_feeds += 1
    if ok_feeds == 0 and last_error is not None:
        if cached is not None:
            return {"fetched_at": cached["fetched_at"], "stale": True, "items": cached["items"]}
        raise last_error

    # HA8 (docs/ideas/empty-feed-drift-guard.md): a feed-markup reshape can parse cleanly
    # to zero surviving items — indistinguishable from a quiet day, except the cache holds
    # real items. Extend the serve-last-good philosophy (bug #3 covered fetch failure) to
    # the parse-that-looks-like-success case: keep the cache, serve it stale, say so once.
    if not merged and cached is not None and cached["items"]:
        logger.warning(
            "news: %s parsed to zero items while the cache holds %d — serving stale "
            "(feed markup drift?)",
            category["slug"],
            len(cached["items"]),
        )
        return {"fetched_at": cached["fetched_at"], "stale": True, "items": cached["items"]}

    # Newest first; undated items (ISO string None → "") sort last. Then collapse the
    # same story syndicated across outlets (newest copy wins), before the cap so dupes
    # never eat the category's 50 slots.
    items = sorted(merged.values(), key=lambda i: i["published_at"] or "", reverse=True)
    items = dedup_by_headline(items)[:MAX_ITEMS_PER_CATEGORY]
    fetched_at = now_dt.isoformat(timespec="seconds")
    set_news_cache(category["slug"], items, fetched_at=fetched_at, db_path=db_path)
    return {"fetched_at": fetched_at, "stale": False, "items": items}
