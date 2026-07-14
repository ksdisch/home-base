import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BriefResponse, BriefTopic } from "../api/types";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";

// "Sunday, July 13" from the sweep folder's YYYY-MM-DD (parsed as local, not UTC).
function humanDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function localToday(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function TopicSection({ topic }: { topic: BriefTopic }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white/60 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink">{topic.title}</h2>
        {topic.as_of && <span className="text-xs text-muted">as of {topic.as_of}</span>}
      </div>

      {topic.error && (
        <div className="mt-3">
          <Banner tone="warning" title="This topic's sweep didn't validate">
            {topic.error}
          </Banner>
        </div>
      )}

      {topic.top_line && <p className="mt-3 font-medium text-ink">{topic.top_line}</p>}
      {topic.context_note && (
        <p className="mt-2 text-sm italic text-muted">{topic.context_note}</p>
      )}

      {topic.items.length > 0 && (
        <div className="mt-4 space-y-5">
          {topic.items.map((item, i) => (
            <article key={i} className="border-t border-stone-100 pt-4">
              <h3 className="font-semibold text-ink">
                {item.headline}
                {item.attribution && (
                  <span className="ml-2 text-sm font-normal text-muted">
                    — {item.attribution}
                  </span>
                )}
              </h3>
              <div className="mt-1 text-sm text-ink/90">
                <Markdown source={item.digest} inline />
              </div>
              {item.why_it_matters && (
                <p className="mt-2 text-sm">
                  <span className="font-semibold text-accent">Why it matters:</span>{" "}
                  <Markdown source={item.why_it_matters} inline />
                </p>
              )}
              {item.sources.length > 0 && (
                <p className="mt-2 text-xs text-muted">
                  {item.sources.map((s, j) => (
                    <span key={j}>
                      {j > 0 && " · "}
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent hover:underline"
                      >
                        {s.title}
                      </a>
                    </span>
                  ))}
                </p>
              )}
            </article>
          ))}
        </div>
      )}

      {/* Legacy md-only day, or a json that wouldn't parse — shown whole, never dropped. */}
      {topic.raw_markdown && (
        <div className="mt-4">
          <Markdown source={topic.raw_markdown} />
        </div>
      )}
    </section>
  );
}

export default function Brief() {
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .brief()
      .then((b) => alive && setBrief(b))
      .catch((e) => alive && setError(e.message ?? "Failed to load the brief"))
      .finally(() => alive && setLoading(false));
    // The habit metric — fire-and-forget so logging can never block the morning read.
    api.logBriefVisit().catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const stale = brief?.date != null && brief.date < localToday();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Today</h1>
        <p className="mt-1 text-sm text-muted">
          {loading
            ? "Reading your morning brief…"
            : brief?.date
              ? `Your sweep from ${humanDate(brief.date)}.`
              : "Your cross-topic morning brief."}
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't load the brief">
            {error}
          </Banner>
        </div>
      )}

      {stale && (
        <div className="mb-6">
          <Banner tone="info" title="This brief is from a previous day">
            Run{" "}
            <code className="rounded bg-stone-100 px-1 font-mono text-[0.85em]">make sweep</code>{" "}
            for a fresh one — it takes a few minutes, then lands here on reload.
          </Banner>
        </div>
      )}

      {loading && !brief && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-2xl border border-stone-200 bg-white/60"
            />
          ))}
        </div>
      )}

      {brief && !brief.has_data && !error && (
        <Banner tone="info" title="No sweeps yet">
          Run{" "}
          <code className="rounded bg-stone-100 px-1 font-mono text-[0.85em]">make sweep</code>{" "}
          to generate today's brief across your pilot topics.
        </Banner>
      )}

      {brief && brief.topics.length > 0 && (
        <div className="space-y-4">
          {brief.topics.map((t) => (
            <TopicSection key={t.slug} topic={t} />
          ))}
        </div>
      )}
    </div>
  );
}
