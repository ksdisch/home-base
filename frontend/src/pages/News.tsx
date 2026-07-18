import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { NewsCategory, NewsCategoryResponse, NewsItem } from "../api/types";
import { Banner } from "../components/Banner";

// M7 Phase 1: the Google-News-style general mode — a tab per category from
// sweeps/news_categories.json, real RSS-backed articles opening at the source. Text-first
// (the feeds carry no images). The selected tab lives in ?cat= so back/forward and
// deep-links work. Mode A (the Today brief) is untouched; this is its sibling page.
export default function News() {
  const [categories, setCategories] = useState<NewsCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feed, setFeed] = useState<NewsCategoryResponse | null>(null);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  // Phase 2 signal state: not-interested items vanish now (the ranker learns later);
  // more-like acks keep the button honest. Both per-visit only — the log is the record.
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [liked, setLiked] = useState<Set<string>>(new Set());

  const selected = params.get("cat") ?? categories?.[0]?.slug ?? null;

  // Every signal is fire-and-forget: reading the news must never break on a logging hiccup.
  const signal = (kind: "click" | "more_like" | "not_interested", item: NewsItem) => {
    if (!selected) return;
    api
      .logNewsEvent({
        kind,
        category_slug: selected,
        item_id: item.id,
        headline: item.headline,
        source: item.source,
        url: item.url,
      })
      .catch(() => {});
  };

  useEffect(() => {
    let alive = true;
    api
      .newsCategories()
      .then((r) => alive && setCategories(r.categories))
      .catch((e) => alive && setError(e.message ?? "Failed to load news categories"));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let alive = true;
    setFeed(null);
    setFeedError(null);
    // The category-visit signal (Phase 2): you opened this tab — that's the event,
    // regardless of whether the feed then loads.
    api.logNewsEvent({ kind: "visit", category_slug: selected }).catch(() => {});
    api
      .newsCategory(selected)
      .then((r) => alive && setFeed(r))
      .catch((e) => alive && setFeedError(e.message ?? "Failed to load this category"));
    return () => {
      alive = false;
    };
  }, [selected]);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-semibold text-ink">News</h1>
        <p className="mt-1 text-sm text-muted">
          The wider world, by section — your personalized brief stays on Today.
        </p>
      </div>

      {error && (
        <Banner tone="warning" title="Couldn't load news">
          {error}
        </Banner>
      )}

      {categories && categories.length === 0 && !error && (
        <Banner tone="info" title="No news categories configured">
          Add sections to sweeps/news_categories.json and reload.
        </Banner>
      )}

      {categories && categories.length > 0 && (
        <nav
          aria-label="News categories"
          className="-mx-4 mb-6 flex gap-1 overflow-x-auto whitespace-nowrap px-4 pb-1 text-sm"
        >
          {categories.map((c) => (
            <button
              key={c.slug}
              onClick={() => setParams(c.slug === categories[0].slug ? {} : { cat: c.slug })}
              aria-current={c.slug === selected ? "page" : undefined}
              className={`rounded-lg px-3 py-1.5 font-medium transition ${
                c.slug === selected
                  ? "bg-accent-soft text-accent"
                  : "text-muted hover:text-ink"
              }`}
            >
              {c.title}
            </button>
          ))}
        </nav>
      )}

      {feedError && (
        <Banner tone="warning" title="Couldn't load this section">
          {feedError}
        </Banner>
      )}

      {feed?.stale && (
        <div className="mb-4">
          <Banner tone="warning" title="Showing saved articles">
            The live refresh failed — these are the most recent articles we have
            {feed.fetched_at ? ` (from ${timeAgo(feed.fetched_at) ?? feed.fetched_at})` : ""}.
          </Banner>
        </div>
      )}

      {selected && !feed && !feedError && <p className="text-sm text-muted">Loading…</p>}

      {feed && feed.items.length === 0 && (
        <Banner tone="info" title="Nothing here right now">
          This section came back empty — try another category or check back later.
        </Banner>
      )}

      {feed && feed.items.length > 0 && (
        <div className="divide-y divide-stone-200 rounded-2xl border border-stone-200 bg-white/60">
          {feed.items
            .filter((item) => !hidden.has(item.id))
            .map((item) => (
              <article key={item.id} className="p-4">
                <div className="text-xs text-muted">
                  {item.source && <span className="font-medium text-accent">{item.source}</span>}
                  {item.source && timeAgo(item.published_at) && " · "}
                  {timeAgo(item.published_at)}
                </div>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  onClick={() => signal("click", item)}
                  className="mt-1 block font-medium text-ink transition hover:text-accent"
                >
                  {item.headline}
                </a>
                <div className="mt-1.5 flex gap-3 text-xs text-muted">
                  <button
                    onClick={() => {
                      if (liked.has(item.id)) return;
                      signal("more_like", item);
                      setLiked((prev) => new Set(prev).add(item.id));
                    }}
                    aria-label={`More like ${item.headline}`}
                    className={`transition ${
                      liked.has(item.id) ? "text-accent" : "hover:text-ink"
                    }`}
                  >
                    {liked.has(item.id) ? "Noted ✓" : "More like this"}
                  </button>
                  <button
                    onClick={() => {
                      signal("not_interested", item);
                      setHidden((prev) => new Set(prev).add(item.id));
                    }}
                    aria-label={`Not interested in ${item.headline}`}
                    className="transition hover:text-ink"
                  >
                    Not interested
                  </button>
                </div>
              </article>
            ))}
        </div>
      )}
    </div>
  );
}

function timeAgo(iso?: string | null): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return null;
  const min = Math.round((Date.now() - then) / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.round(hr / 24)}d ago`;
}
