"""M7 Phase 3: the For You engine — Google's published click-behavior recipe at
single-user scale, with zero LLM.

Pure functions over the ``news_events`` log (Phase 2) and cached feed items (Phase 1):

1. ``build_profile`` — decaying interest scores per category and per headline term.
   Weights: click +3 · more_like +5 · not_interested −8 · visit +1 (category only),
   halved every 14 days so recent interests dominate (the Bayesian-recency idea from
   Google's news-personalization paper, reduced to one user).
2. ``rank_candidates`` — interest × freshness over the candidate pool, seen items
   excluded, net-negative items dropped (that's "Fewer like this" doing its job),
   near-duplicate headlines deduped (the practical slice of Google's story clustering).
3. ``top_search_terms`` — the strongest profile terms, used by the API to pull
   ``news.google.com/rss/search?q=…`` feeds so For You can reach beyond the standard
   sections. This is the only place Mode B looks outside its category roster; it still
   never reads ``topics.json`` (Kyle's distinctness fork).

Everything takes an injected ``now`` for deterministic tests. The profile reads the
event log and nothing else — Mode-A data is deliberately not an input.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

EVENT_WEIGHTS = {"click": 3.0, "more_like": 5.0, "visit": 1.0, "not_interested": -8.0}
POSITIVE_KINDS = ("click", "more_like", "visit")  # what counts toward warming up
HALF_LIFE_DAYS = 14.0
FRESHNESS_HALF_LIFE_HOURS = 24.0
UNDATED_FRESHNESS = 0.3  # an item with no pubDate is probably not breaking news
COLD_START_EVENTS = 20
FORYOU_MAX_ITEMS = 40
MAX_SEARCH_TERMS = 3
SEARCH_TERM_MIN_SCORE = 5.0
CATEGORY_WEIGHT = 0.5  # category affinity is softer evidence than term matches
DEDUP_JACCARD = 0.6

# Small inline stopword list — enough to keep profile terms meaningful without a dependency.
_STOPWORDS = frozenset(
    """a about after all also am an and any are as at be because been before being but by can
    could did do does down for from had has have he her here his how i if in into is it its
    just like me more most my new no not now of off on one only or other our out over own said
    say says she so some than that the their them then there these they this to two under up
    us was we were what when where which who why will with would you your""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]+")


def extract_terms(headline: Optional[str]) -> set:
    """Unigrams + adjacent bigrams from a headline, lowercased, stopworded. Bigrams keep
    the terms that actually mean something ("lake county", "fantasy football")."""
    if not headline:
        return set()
    words = [w for w in _TOKEN_RE.findall(headline.lower()) if w not in _STOPWORDS and len(w) > 2]
    terms = set(words)
    terms.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return terms


_LOCAL_TZ = ZoneInfo("America/Chicago")


def _local_day(created_at: Optional[str]) -> str:
    """The LOCAL calendar day an event belongs to, or "" when unreadable (bug #13).

    Naive rows are sqlite's UTC ``datetime('now')`` — attach UTC then convert, mirroring
    ``_decay``'s normalization. The persistence gate's stated intent is 'a persistent
    interest, not one morning's rabbit hole', so the bucket is Kyle's calendar day: two
    evening sittings straddling UTC midnight are not two distinct days."""
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_LOCAL_TZ).date().isoformat()


def _decay(created_at: Optional[str], now: datetime) -> float:
    """0.5 ** (age_days / 14). Unreadable timestamps decay to nothing rather than raise —
    a malformed row must never sink the whole profile."""
    if not created_at:
        return 0.0
    try:
        # sqlite's datetime('now') is naive UTC ("YYYY-MM-DD HH:MM:SS"); ISO strings also land here.
        dt = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def build_profile(events: Iterable[Dict[str, Any]], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """The one-user interest profile: decayed category scores, decayed term scores, seen
    item ids (clicked or dismissed — never re-recommended), and the positive-event count
    the cold-start gate reads."""
    now_dt = now or datetime.now(timezone.utc)
    category_scores: Dict[str, float] = {}
    term_scores: Dict[str, float] = {}
    seen_item_ids: set = set()
    event_count = 0

    for e in events:
        kind = e.get("kind")
        weight = EVENT_WEIGHTS.get(kind)
        if weight is None:
            continue
        if kind in POSITIVE_KINDS:
            event_count += 1
        decayed = weight * _decay(e.get("created_at"), now_dt)
        slug = e.get("category_slug")
        if slug:
            category_scores[slug] = category_scores.get(slug, 0.0) + decayed
        for term in extract_terms(e.get("headline")):
            term_scores[term] = term_scores.get(term, 0.0) + decayed
        if e.get("item_id") and kind in ("click", "not_interested"):
            seen_item_ids.add(e["item_id"])

    return {
        "event_count": event_count,
        "category_scores": category_scores,
        "term_scores": term_scores,
        "seen_item_ids": seen_item_ids,
    }


def _freshness(published_at: Optional[str], now: datetime) -> float:
    if not published_at:
        return UNDATED_FRESHNESS
    try:
        dt = datetime.fromisoformat(published_at)
    except (TypeError, ValueError):
        return UNDATED_FRESHNESS
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / FRESHNESS_HALF_LIFE_HOURS)


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def rank_candidates(
    profile: Dict[str, Any],
    items_by_category: Dict[str, List[Dict[str, Any]]],
    *,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """The For You feed: every candidate scored as
    ``(category_affinity × 0.5 + term_affinity) × freshness``, seen items excluded,
    net-negative items dropped, near-duplicates deduped keeping the higher-scored copy.
    Zero-affinity items trail the scored ones ordered by freshness alone, so a young
    profile still fills the page. Returned items carry their origin ``category_slug``."""
    now_dt = now or datetime.now(timezone.utc)
    category_scores = profile["category_scores"]
    term_scores = profile["term_scores"]
    seen = profile["seen_item_ids"]

    scored: List[tuple] = []
    for slug, items in items_by_category.items():
        cat_affinity = category_scores.get(slug, 0.0)
        for item in items:
            if item["id"] in seen:
                continue
            terms = extract_terms(item.get("headline"))
            term_affinity = sum(term_scores.get(t, 0.0) for t in terms)
            interest = cat_affinity * CATEGORY_WEIGHT + term_affinity
            if interest < 0:
                continue  # "Fewer like this" doing its job
            score = interest * _freshness(item.get("published_at"), now_dt)
            # Zero-interest items rank behind every scored item, by freshness alone.
            sort_key = (1 if interest > 0 else 0, score if interest > 0 else _freshness(item.get("published_at"), now_dt))
            scored.append((sort_key, terms, {**item, "category_slug": slug}))

    scored.sort(key=lambda t: t[0], reverse=True)

    out: List[Dict[str, Any]] = []
    kept_terms: List[set] = []
    seen_ids: set = set()
    for _key, terms, item in scored:
        if item["id"] in seen_ids:  # same story syndicated into two sections
            continue
        if any(_jaccard(terms, kt) >= DEDUP_JACCARD for kt in kept_terms):
            continue
        seen_ids.add(item["id"])
        kept_terms.append(terms)
        out.append(item)
    return out


def dedup_by_headline(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order-preserving near-duplicate collapse (≥ 0.6 headline-term Jaccard): the same
    story syndicated across outlets keeps only the first copy. Callers pass newest-first
    lists (category pages) so the freshest copy wins; ``rank_candidates`` keeps its own
    interwoven score-aware dedup."""
    out: List[Dict[str, Any]] = []
    kept_terms: List[set] = []
    for item in items:
        terms = extract_terms(item.get("headline"))
        if any(_jaccard(terms, kt) >= DEDUP_JACCARD for kt in kept_terms):
            continue
        kept_terms.append(terms)
        out.append(item)
    return out


def top_search_terms(profile: Dict[str, Any]) -> List[str]:
    """The strongest positive profile terms — the API pulls a Google News search feed per
    term so For You can surface interests no standard section covers. Bigrams win ties
    (more specific searches); weak terms stay home (junk queries help nobody)."""
    candidates = [
        (score, " " in term, term)
        for term, score in profile["term_scores"].items()
        if score >= SEARCH_TERM_MIN_SCORE
    ]
    candidates.sort(reverse=True)
    return [term for _score, _is_bigram, term in candidates[:MAX_SEARCH_TERMS]]


def search_feed_url(term: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(term)}&hl=en-US&gl=US&ceid=US:en"


# -- the topic scout (Phase 4) ---------------------------------------------------

SUGGESTION_MIN_SCORE = 9.0  # ≈ three fresh clicks on the theme
SUGGESTION_MIN_DAYS = 3  # a persistent interest, not one morning's rabbit hole
MAX_SUGGESTIONS = 3
_SUGGESTION_KINDS = {"click": 3.0, "more_like": 5.0, "not_interested": -8.0}


def _roster_tokens(roster: Iterable[Dict[str, Any]]) -> set:
    """Every meaningful token in the Mode-A roster's slugs + titles. A term sharing any
    token with the roster counts as covered — conservative on purpose: better to miss a
    suggestion than nag about a topic the brief already sweeps."""
    tokens: set = set()
    for topic in roster:
        for field in ("slug", "title"):
            tokens.update(
                w for w in _TOKEN_RE.findall(str(topic.get(field) or "").lower()) if len(w) > 2
            )
    return tokens


def suggest_topics(
    events: Iterable[Dict[str, Any]],
    roster: Iterable[Dict[str, Any]],
    dismissed: Iterable[str],
    *,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """The Mode-A bridge: persistent, high-scoring profile terms the morning brief doesn't
    cover yet. A term qualifies with decayed score ≥ 9 across ≥ 3 distinct days, no token
    overlap with the roster, and no prior dismissal. Coverage applies at the *event*
    level too: a story about a rostered topic teaches the scout nothing — Chiefs stories
    must not spawn a "kicker battle" suggestion. Bigrams absorb their own unigrams, and
    the final list is token-disjoint (one suggestion per theme, not three phrasings of
    it). Each suggestion carries recent example headlines as the card's evidence."""
    now_dt = now or datetime.now(timezone.utc)
    # A dismissal silences every phrasing of its theme: dropping "quantum computing"
    # must not resurface as a bare "quantum" card. Token overlap, like roster coverage.
    dismissed_tokens: set = set()
    for d in dismissed:
        if d and d.strip():
            dismissed_tokens.update(d.strip().lower().split())
    roster_tokens = _roster_tokens(roster)

    scores: Dict[str, float] = {}
    days: Dict[str, set] = {}
    examples: Dict[str, List[str]] = {}
    for e in events:
        weight = _SUGGESTION_KINDS.get(e.get("kind"))
        if weight is None:
            continue
        headline = e.get("headline")
        terms = extract_terms(headline)
        if {t for t in terms if " " not in t} & roster_tokens:
            continue  # a story the brief already covers — not scout evidence
        decayed = weight * _decay(e.get("created_at"), now_dt)
        day = _local_day(e.get("created_at"))
        for term in terms:
            scores[term] = scores.get(term, 0.0) + decayed
            if weight > 0 and day:
                days.setdefault(term, set()).add(day)
                bucket = examples.setdefault(term, [])
                if headline and headline not in bucket and len(bucket) < 2:
                    bucket.append(headline)

    qualifying = {
        term: score
        for term, score in scores.items()
        if score >= SUGGESTION_MIN_SCORE
        and len(days.get(term, ())) >= SUGGESTION_MIN_DAYS
        and not (set(term.split()) & dismissed_tokens)
        and not any(tok in roster_tokens for tok in term.split())
    }
    # Bigrams absorb their unigrams: keep the specific phrase, drop its parts.
    bigram_parts: set = set()
    for term in qualifying:
        if " " in term:
            bigram_parts.update(term.split())
    ranked = sorted(
        ((score, " " in term, term) for term, score in qualifying.items()
         if " " in term or term not in bigram_parts),
        reverse=True,
    )
    # Token-disjoint greedy pick: once "quantum computing" is suggested, "computing
    # breakthrough" is the same reading streak, not a second interest.
    out: List[Dict[str, Any]] = []
    used_tokens: set = set()
    for score, _is_bigram, term in ranked:
        tokens = set(term.split())
        if tokens & used_tokens:
            continue
        used_tokens |= tokens
        out.append(
            {
                "term": term,
                "score": round(score, 2),
                "days_seen": len(days.get(term, ())),
                "example_headlines": examples.get(term, []),
            }
        )
        if len(out) == MAX_SUGGESTIONS:
            break
    return out
