import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { NewsCategory, NewsItem } from "../api/types";
import { Banner } from "../components/Banner";

// M7: the Google-News-style general mode. Phase 1: a tab per category from
// sweeps/news_categories.json, real RSS-backed articles opening at the source, ?cat=
// deep-links. Phase 2: every interaction (visit, click, More-like-this, Not-interested)
// is a fire-and-forget signal to /api/news/events. Phase 3: the For You tab — default
// landing, ranked by the decayed interest profile those signals build; cold start shows
// Top stories and says so. Mode A (the Today brief) is untouched; this is its sibling.

type FeedItem = NewsItem & { category_slug?: string | null };
type FeedView = {
  items: FeedItem[];
  stale: boolean;
  fetched_at?: string | null;
  learning?: boolean;
  event_count?: number;
};

const FOR_YOU: NewsCategory = { slug: "foryou", title: "For You" };

export default function News() {
  const [categories, setCategories] = useState<NewsCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feed, setFeed] = useState<FeedView | null>(null);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  // Phase 2 signal state: not-interested items vanish now (the ranker learns from the
  // event); more-like acks keep the button honest. Both per-visit — the log is the record.
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [liked, setLiked] = useState<Set<string>>(new Set());

  const hasCategories = categories !== null && categories.length > 0;
  const selected = hasCategories ? (params.get("cat") ?? FOR_YOU.slug) : null;
  const tabs = hasCategories ? [FOR_YOU, ...categories] : null;

  // Every signal is fire-and-forget: reading the news must never break on a logging
  // hiccup. Item signals credit the item's origin section (For You items carry theirs).
  const signal = (kind: "click" | "more_like" | "not_interested", item: FeedItem) => {
    if (!selected) return;
    api
      .logNewsEvent({
        kind,
        category_slug: item.category_slug ?? selected,
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
    const load =
      selected === FOR_YOU.slug
        ? api.newsForYou().then(
            (r): FeedView => ({
              items: r.items,
              stale: false,
              learning: r.learning,
              event_count: r.event_count,
            }),
          )
        : api.newsCategory(selected).then(
            (r): FeedView => ({ items: r.items, stale: r.stale, fetched_at: r.fetched_at }),
          );
    load
      .then((view) => alive && setFeed(view))
      .catch((e) => alive && setFeedError(e.message ?? "Failed to load this section"));
    return () => {
      alive = false;
    };
  }, [selected]);

  const originLabel = (item: FeedItem): string | null => {
    if (selected !== FOR_YOU.slug || !item.category_slug) return null;
    if (item.category_slug.startsWith("search:")) {
      return `“${item.category_slug.slice("search:".length)}”`;
    }
    return categories?.find((c) => c.slug === item.category_slug)?.title ?? null;
  };

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

      {tabs && (
        <nav
          aria-label="News categories"
          className="-mx-4 mb-6 flex gap-1 overflow-x-auto whitespace-nowrap px-4 pb-1 text-sm"
        >
          {tabs.map((c) => (
            <button
              key={c.slug}
              onClick={() => setParams(c.slug === FOR_YOU.slug ? {} : { cat: c.slug })}
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

      {feed?.learning && (
        <div className="mb-4">
          <Banner tone="info" title="Still learning you">
            For You warms up as you read — clicks, section visits, and the feedback buttons
            all teach it ({feed.event_count ?? 0} of 20 signals so far). Until then, here are
            the top stories.
          </Banner>
        </div>
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

      {feed && feed.items.length === 0 && !feed.learning && (
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
                  {originLabel(item) && (
                    <span className="ml-2 rounded bg-accent-soft px-1.5 py-0.5 text-accent">
                      {originLabel(item)}
                    </span>
                  )}
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
