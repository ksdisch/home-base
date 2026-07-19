"""GET /api/news/* — the M7 Google-News-style mode's read path (Phase 1).

Categories come from ``sweeps/news_categories.json`` (a config-file roster, like
``topics.json``); items come from Google News RSS via ``app.news`` and its short store
cache. Unknown slugs 404. A category whose feeds can't be fetched *and* has no cached
payload is an honest 502 (the page shows the error); an expired cache behind a failed
refresh serves marked ``stale`` instead — never a blank page when we have something real.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_app_settings, get_news_fetcher
from ..foryou import (
    COLD_START_EVENTS,
    FORYOU_MAX_ITEMS,
    build_profile,
    rank_candidates,
    search_feed_url,
    suggest_topics,
    top_search_terms,
)
from ..models import (
    ForYouItem,
    NewsCategoriesResponse,
    NewsCategory,
    NewsCategoryResponse,
    NewsEventCreate,
    NewsEventResponse,
    NewsForYouResponse,
    NewsItem,
    NewsSuggestionActionRequest,
    NewsSuggestionAddResponse,
    NewsSuggestionDismissResponse,
    NewsTopicSuggestion,
)
from ..news import (
    NewsFeedError,
    append_roster_topic,
    get_category_items,
    load_news_categories,
)
from ..store import (
    add_news_dismissal,
    list_news_dismissals,
    list_news_events,
    record_news_event,
)
from ..sweeps import load_roster

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/news/categories", response_model=NewsCategoriesResponse)
def get_news_categories(settings=Depends(get_app_settings)) -> NewsCategoriesResponse:
    cats = load_news_categories(settings.news_categories_file)
    return NewsCategoriesResponse(
        generated_at=_now_iso(),
        categories=[NewsCategory(slug=c["slug"], title=c["title"]) for c in cats],
    )


@router.get("/news/foryou", response_model=NewsForYouResponse)
def get_news_foryou(
    settings=Depends(get_app_settings),
    fetcher=Depends(get_news_fetcher),
) -> NewsForYouResponse:
    """The personalized feed (M7 Phase 3). Cold start (< 20 positive signals) serves Top
    stories labeled ``learning`` — honest about not knowing you yet. Warm, it ranks the
    whole cached candidate pool (every section + a search feed per strong profile term)
    by decayed interest × freshness. Declared before ``/news/{slug}`` so it isn't
    swallowed by the slug route. A dead feed is skipped, never fatal — For You degrades
    to ranking whatever candidates exist."""
    cats = load_news_categories(settings.news_categories_file)
    events = list_news_events()
    profile = build_profile(events)
    # The topic scout (Phase 4): persistent interests the brief's roster doesn't cover.
    suggestions = [
        NewsTopicSuggestion(**s)
        for s in suggest_topics(events, load_roster(settings.roster_file), list_news_dismissals())
    ]

    if profile["event_count"] < COLD_START_EVENTS:
        top = next((c for c in cats if c["slug"] == "top"), cats[0] if cats else None)
        items: list = []
        if top is not None:
            try:
                fetched = get_category_items(top, fetcher)["items"]
                items = [{**i, "category_slug": top["slug"]} for i in fetched]
            except NewsFeedError:
                items = []  # the tab already explains itself; stay calm
        return NewsForYouResponse(
            generated_at=_now_iso(),
            learning=True,
            event_count=profile["event_count"],
            items=[ForYouItem(**i) for i in items[:FORYOU_MAX_ITEMS]],
            suggestions=suggestions,
        )

    items_by_category = {}
    for cat in cats:
        try:
            items_by_category[cat["slug"]] = get_category_items(cat, fetcher)["items"]
        except NewsFeedError:
            continue
    for term in top_search_terms(profile):
        slug = f"search:{term}"
        pseudo = {"slug": slug, "title": term, "feeds": [search_feed_url(term)]}
        try:
            items_by_category[slug] = get_category_items(pseudo, fetcher)["items"]
        except NewsFeedError:
            continue

    ranked = rank_candidates(profile, items_by_category)[:FORYOU_MAX_ITEMS]
    return NewsForYouResponse(
        generated_at=_now_iso(),
        learning=False,
        event_count=profile["event_count"],
        items=[ForYouItem(**i) for i in ranked],
        suggestions=suggestions,
    )


@router.post("/news/suggestions/add", response_model=NewsSuggestionAddResponse)
def add_suggested_topic(
    payload: NewsSuggestionActionRequest, settings=Depends(get_app_settings)
) -> NewsSuggestionAddResponse:
    """The scout's one-click add (M7 Phase 4): append the term to the Mode-A roster
    (``sweeps/topics.json``) — tomorrow's 06:00 sweep picks it up. The single deliberate
    Mode-B → Mode-A bridge; a duplicate slug is a 409, not a silent overwrite."""
    try:
        entry = append_roster_topic(settings.roster_file, payload.term)
    except ValueError as e:
        status = 409 if "already on the roster" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e))
    return NewsSuggestionAddResponse(ok=True, slug=entry["slug"], title=entry["title"])


@router.post("/news/suggestions/dismiss", response_model=NewsSuggestionDismissResponse)
def dismiss_suggested_topic(
    payload: NewsSuggestionActionRequest,
) -> NewsSuggestionDismissResponse:
    """Remember "don't suggest this again" (M7 Phase 4) — the scout never re-nags."""
    try:
        term = add_news_dismissal(payload.term)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return NewsSuggestionDismissResponse(ok=True, term=term)


@router.post("/news/events", response_model=NewsEventResponse)
def create_news_event(payload: NewsEventCreate) -> NewsEventResponse:
    """Append one For-You signal (M7 Phase 2). Fire-and-forget from the page — but invalid
    events (unknown kind, item event without its snapshot) 400 rather than pollute the
    profile the Phase 3 ranker learns from."""
    try:
        row = record_news_event(
            payload.kind,
            payload.category_slug,
            item_id=payload.item_id,
            headline=payload.headline,
            source=payload.source,
            url=payload.url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return NewsEventResponse(ok=True, id=row["id"], created_at=row["created_at"])


@router.get("/news/{slug}", response_model=NewsCategoryResponse)
def get_news_category(
    slug: str,
    settings=Depends(get_app_settings),
    fetcher=Depends(get_news_fetcher),
) -> NewsCategoryResponse:
    cats = load_news_categories(settings.news_categories_file)
    cat = next((c for c in cats if c["slug"] == slug), None)
    if cat is None:
        raise HTTPException(status_code=404, detail=f"no news category '{slug}'")
    try:
        result = get_category_items(cat, fetcher)
    except NewsFeedError as e:
        raise HTTPException(status_code=502, detail=f"news feed unavailable: {e}")
    return NewsCategoryResponse(
        generated_at=_now_iso(),
        slug=cat["slug"],
        title=cat["title"],
        fetched_at=result["fetched_at"],
        stale=result["stale"],
        items=[NewsItem(**i) for i in result["items"]],
    )
