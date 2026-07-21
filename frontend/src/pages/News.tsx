import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { sourceTint } from "../lib/sourceTint";
import type { NewsCategory, NewsItem, NewsTopicSuggestion } from "../api/types";
import { Banner } from "../components/Banner";
import { UndoToast, useUndoable } from "../components/undo";
import { BackToTop } from "../components/BackToTop";
import { useNewsShell } from "../components/NewsShell";

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
  suggestions?: NewsTopicSuggestion[];
};

const FOR_YOU: NewsCategory = { slug: "foryou", title: "For You" };

// Today as local YYYY-MM-DD (same helper the Brief page uses) — a news note's brief_date
// snapshots the morning Kyle saw it, since a news item has no sweep folder of its own.
function localToday(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export default function News() {
  const [categories, setCategories] = useState<NewsCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feed, setFeed] = useState<FeedView | null>(null);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  // Phase 2 signal state: not-interested items vanish now (the ranker learns from the
  // event); more-like acks keep the button honest. Both per-visit — the log is the record.
  // F1: hidden/liked/noted + scroll live in NewsShell (above the route) so they survive a
  // Today→News→Today remount; the feed still refetches fresh and these id-keyed sets reconcile.
  const { hidden, setHidden, liked, setLiked, noted, setNoted, scrollY } = useNewsShell();
  // Phase 4 scout state: added terms show their confirmation; dismissed ones drop now
  // (the backend remembers, so they stay gone on every future load too).
  const [added, setAdded] = useState<Map<string, string>>(new Map());
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  // QU5 note state: one open composer at a time; saved ids keep their "✓ Saved" ack.
  // Notes write through the SAME POST /brief/notes path as Today, so a news item becomes
  // a durable note interleaved on /notes — the snapshot columns make it self-contained.
  const [noting, setNoting] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  // FR10: Not-interested sits inches from More-like-this on a one-handed phone — the
  // card still vanishes now, but the −8 signal holds behind the undo toast.
  const { label: undoLabel, fire: holdThenFire, undo } = useUndoable();

  const hasCategories = categories !== null && categories.length > 0;
  // F1 (first wedge): a Today→News→Today hop drops the ?cat= query, so News reset to For You
  // every return. Fall back to the last-opened tab (persisted on click below) so News lands
  // back where you left it; an explicit ?cat= in the URL still wins.
  const selected = hasCategories
    ? (params.get("cat") ?? sessionStorage.getItem("news.tab") ?? FOR_YOU.slug)
    : null;
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
              suggestions: r.suggestions,
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

  // F1: restore the scroll position from before the last nav-away, once the fresh feed is
  // back in the DOM. Once per mount — a tab switch within News keeps its own scroll.
  const scrollRestored = useRef(false);
  useEffect(() => {
    if (feed && !scrollRestored.current) {
      scrollRestored.current = true;
      if (scrollY.current > 0) window.scrollTo(0, scrollY.current);
    }
  }, [feed, scrollY]);

  // Track scroll while News is open so the position is already saved before a nav hop
  // unmounts it — reading window.scrollY at unmount is too late (the page has already
  // collapsed to the next route's height, clamping scroll to 0).
  useEffect(() => {
    const onScroll = () => {
      // Only record once the feed is back and we've restored — otherwise the brief
      // collapse to "Loading…" on return fires a scroll event that would overwrite the
      // saved position with 0 before the restore above can use it.
      if (scrollRestored.current) scrollY.current = window.scrollY;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [scrollY]);

  // Same origin-crediting rule as signal(): a For You item's note lands under the
  // section it actually came from, not the synthetic "foryou" tab.
  const saveNote = (item: FeedItem) => {
    if (!selected || noteSaving) return;
    const body = noteDraft.trim();
    if (!body) return;
    setNoteSaving(true);
    setNoteError(null);
    api
      .addBriefNote({
        item_id: item.id,
        topic_slug: item.category_slug ?? selected,
        brief_date: localToday(),
        item_headline: item.headline,
        body,
      })
      .then(() => {
        setNoted((prev) => new Set(prev).add(item.id));
        setNoting(null);
        setNoteDraft("");
      })
      .catch((e) => setNoteError(e.message ?? "Couldn't save the note"))
      .finally(() => setNoteSaving(false));
  };

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
          className="-mx-4 mb-6 flex snap-x snap-mandatory gap-1 overflow-x-auto whitespace-nowrap px-4 pb-1 text-sm"
        >
          {tabs.map((c) => (
            <button
              key={c.slug}
              onClick={() => {
                sessionStorage.setItem("news.tab", c.slug); // F1: remember for the next return
                setParams(c.slug === FOR_YOU.slug ? {} : { cat: c.slug });
              }}
              aria-current={c.slug === selected ? "page" : undefined}
              className={`flex min-h-[44px] snap-start items-center rounded-lg px-4 font-medium transition ${
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
            <p>
              <span className="font-medium">Do this first:</span> open a story you actually
              want more of, or tap “More like this” on the ones you like.
            </p>
            <p className="mt-1">
              For You warms up as you read — clicks, section visits, and the feedback buttons
              all teach it ({feed.event_count ?? 0} of 20 signals so far). Until then, here are
              the top stories.
            </p>
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

      {feed?.suggestions && feed.suggestions.filter((s) => !dismissed.has(s.term)).length > 0 && (
        <div className="mb-6 space-y-3">
          {suggestionError && (
            <Banner tone="warning" title="Suggestion action failed">
              {suggestionError}
            </Banner>
          )}
          {feed.suggestions
            .filter((s) => !dismissed.has(s.term))
            .map((s) => (
              <div
                key={s.term}
                className="rounded-2xl border border-line bg-accent-soft/40 p-4"
              >
                <div className="text-sm text-ink">
                  You've been reading a lot about{" "}
                  <span className="font-semibold text-accent">{s.term}</span>
                  <span className="text-muted">
                    {" "}
                    — across {s.days_seen} days
                    {s.example_headlines[0] ? ` (e.g. “${s.example_headlines[0]}”)` : ""}.
                  </span>
                </div>
                <div className="mt-2 flex gap-3 text-xs">
                  {added.has(s.term) ? (
                    <span className="font-medium text-accent">
                      Added ✓ — in tomorrow's morning brief
                    </span>
                  ) : (
                    <>
                      <button
                        onClick={() => {
                          setSuggestionError(null);
                          api
                            .addNewsTopic({ term: s.term })
                            .then((r) =>
                              setAdded((prev) => new Map(prev).set(s.term, r.slug)),
                            )
                            .catch((e) =>
                              setSuggestionError(e.message ?? "Couldn't add the topic"),
                            );
                        }}
                        className="font-medium text-accent transition hover:underline"
                      >
                        Add to my brief
                      </button>
                      <button
                        onClick={() => {
                          setSuggestionError(null);
                          api
                            .dismissNewsSuggestion({ term: s.term })
                            .then(() =>
                              setDismissed((prev) => new Set(prev).add(s.term)),
                            )
                            .catch((e) =>
                              setSuggestionError(e.message ?? "Couldn't dismiss it"),
                            );
                        }}
                        className="text-muted transition hover:text-ink"
                      >
                        Don't suggest this
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
        </div>
      )}

      {selected && !feed && !feedError && <p className="text-sm text-muted">Loading…</p>}

      {feed && feed.items.length === 0 && !feed.learning && (
        <Banner tone="info" title="Nothing here right now">
          This section came back empty — try another category or check back later.
        </Banner>
      )}

      {feed && feed.items.length > 0 && (() => {
        // ① A front page, not a spreadsheet: the visible #1 gets its own lead card; the rest
        // stay the compact field. Same <article> body for both — the headline is the primary
        // tap (F2: semibold + ↗ + full-height block), feedback stays one-tap but subordinated.
        const visible = feed.items.filter((item) => !hidden.has(item.id));
        if (visible.length === 0) return null;
        const [lead, ...rest] = visible;
        const renderArticle = (item: FeedItem, isLead: boolean) => (
              <article key={item.id} className={isLead ? "p-5" : "p-4"}>
                <div className={`text-meta text-muted ${isLead ? "mb-1" : ""}`}>
                  {item.source && <span className={`font-medium ${sourceTint(item.source)}`}>{item.source}</span>}
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
                  className={`mt-1 block py-0.5 font-semibold text-ink transition hover:text-accent ${
                    isLead ? "text-lede" : ""
                  }`}
                >
                  {item.headline}
                  <span aria-hidden="true" className="ml-1 text-muted">
                    ↗
                  </span>
                </a>
                <div className="mt-2 flex justify-end gap-4 text-xs text-muted">
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
                      setHidden((prev) => new Set(prev).add(item.id));
                      holdThenFire(
                        "Marked not interested",
                        () => signal("not_interested", item),
                        () =>
                          setHidden((prev) => {
                            const next = new Set(prev);
                            next.delete(item.id);
                            return next;
                          }),
                      );
                    }}
                    aria-label={`Not interested in ${item.headline}`}
                    className="transition hover:text-ink"
                  >
                    Not interested
                  </button>
                  <button
                    onClick={() => {
                      if (noted.has(item.id)) return;
                      setNoteError(null);
                      setNoteDraft("");
                      setNoting(noting === item.id ? null : item.id);
                    }}
                    aria-label={`Note on ${item.headline}`}
                    className={`transition ${
                      noted.has(item.id) ? "text-accent" : "hover:text-ink"
                    }`}
                  >
                    {noted.has(item.id) ? "✓ Saved" : "Note"}
                  </button>
                </div>
                {noting === item.id && !noted.has(item.id) && (
                  <div className="mt-2">
                    {noteError && (
                      <p className="mb-1 text-xs text-danger">{noteError}</p>
                    )}
                    <textarea
                      value={noteDraft}
                      onChange={(e) => setNoteDraft(e.target.value)}
                      placeholder="Your take — lands in your notes"
                      rows={2}
                      className="w-full rounded-lg border border-line bg-card p-2 text-sm text-ink"
                    />
                    <div className="mt-1 flex gap-3 text-xs">
                      <button
                        onClick={() => saveNote(item)}
                        disabled={noteSaving || !noteDraft.trim()}
                        className="font-medium text-accent transition hover:underline disabled:opacity-50"
                      >
                        Save note
                      </button>
                      <button
                        onClick={() => setNoting(null)}
                        className="text-muted transition hover:text-ink"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </article>
        );
        return (
          <div className="space-y-4">
            <div className="rounded-2xl border border-line bg-card/60">{renderArticle(lead, true)}</div>
            {rest.length > 0 && (
              <div className="divide-y divide-line rounded-2xl border border-line bg-card/60">
                {rest.map((item) => renderArticle(item, false))}
              </div>
            )}
          </div>
        );
      })()}

      <UndoToast label={undoLabel} onUndo={undo} />
      <BackToTop />
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
