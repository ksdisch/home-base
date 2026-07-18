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
from ..models import (
    NewsCategoriesResponse,
    NewsCategory,
    NewsCategoryResponse,
    NewsItem,
)
from ..news import NewsFeedError, get_category_items, load_news_categories

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
