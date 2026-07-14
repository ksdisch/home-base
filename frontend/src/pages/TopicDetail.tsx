import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Episode, TopicDetail as Detail } from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";

export default function TopicDetail() {
  const { id = "" } = useParams();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    (live: boolean) => {
      if (live) setRefreshing(true);
      else setLoading(true);
      api
        .topic(id, live)
        .then(setDetail)
        .catch((e) => setError(e.message ?? "Failed to load topic"))
        .finally(() => {
          setLoading(false);
          setRefreshing(false);
        });
    },
    [id],
  );

  useEffect(() => load(false), [load]);

  const onToggleListened = async (ep: Episode) => {
    if (!detail) return;
    const next = !ep.listened;
    // optimistic
    const apply = (eps: Episode[]) =>
      eps.map((e) => (e.artifact_id === ep.artifact_id ? { ...e, listened: next } : e));
    setDetail({ ...detail, episodes: apply(detail.episodes), standalones: apply(detail.standalones) });
    try {
      await api.setEpisodeListened(detail.notebook_id, ep.artifact_id, next);
    } catch {
      // revert on failure
      const revert = (eps: Episode[]) =>
        eps.map((e) => (e.artifact_id === ep.artifact_id ? { ...e, listened: !next } : e));
      setDetail((d) =>
        d ? { ...d, episodes: revert(d.episodes), standalones: revert(d.standalones) } : d,
      );
    }
  };

  if (loading && !detail) {
    return <div className="h-40 animate-pulse rounded-2xl border border-stone-200 bg-white/60" />;
  }
  if (error && !detail) {
    return (
      <div className="space-y-4">
        <Link to="/learning" className="text-sm text-accent hover:underline">
          ← All topics
        </Link>
        <Banner tone="warning" title="Couldn't load this topic">
          {error}
        </Banner>
      </div>
    );
  }
  if (!detail) return null;

  return (
    <div className="space-y-8">
      <div>
        <Link to="/learning" className="text-sm text-accent hover:underline">
          ← All topics
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-ink">{detail.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone="accent">{detail.group_label}</Badge>
              {detail.archived && <Badge tone="stone">archived</Badge>}
              {detail.live && <Badge tone="neutral">live-synced</Badge>}
              {typeof detail.source_count === "number" && (
                <span className="text-xs text-muted">{detail.source_count} sources</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => load(true)}
              disabled={refreshing}
              className="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent disabled:opacity-50"
            >
              {refreshing ? "Refreshing…" : "Refresh (live)"}
            </button>
            <a
              href={detail.notebooklm_url}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              Open in NotebookLM ↗
            </a>
          </div>
        </div>
      </div>

      {detail.archived && detail.merged_into && (
        <Banner tone="muted">
          This notebook is archived (merged into <code>{detail.merged_into}</code>). Its artifacts
          are still listed below.
        </Banner>
      )}

      {!detail.auth.ok && detail.auth.message && (
        <Banner tone="warning" title="NotebookLM sign-in needed">
          {detail.auth.message}
        </Banner>
      )}

      <Section title="Audio season" count={detail.episodes.length} empty="No season episodes found.">
        <ul className="divide-y divide-stone-100">
          {detail.episodes.map((ep) => (
            <EpisodeRow key={ep.artifact_id} ep={ep} url={detail.notebooklm_url} onToggle={onToggleListened} />
          ))}
        </ul>
      </Section>

      {detail.standalones.length > 0 && (
        <Section title="Standalone audio" count={detail.standalones.length}>
          <ul className="divide-y divide-stone-100">
            {detail.standalones.map((ep) => (
              <EpisodeRow key={ep.artifact_id} ep={ep} url={detail.notebooklm_url} onToggle={onToggleListened} />
            ))}
          </ul>
        </Section>
      )}

      <Section title="Study guides" count={detail.study_guides.length} empty="No study guides found.">
        <ul className="divide-y divide-stone-100">
          {detail.study_guides.map((g) => {
            const guideUrl = `/topics/${encodeURIComponent(detail.notebook_id)}/guide/${encodeURIComponent(
              g.artifact_id,
            )}`;
            return (
              <li key={g.artifact_id} className="flex items-center justify-between gap-3 py-2.5">
                <Link to={guideUrl} className="text-sm text-ink hover:text-accent hover:underline">
                  {g.title}
                </Link>
                <Link
                  to={guideUrl}
                  className="shrink-0 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white hover:opacity-90"
                >
                  Read ▸
                </Link>
              </li>
            );
          })}
        </ul>
      </Section>

      <Section title="Quizzes" count={detail.quizzes.length} empty="No quizzes found.">
        <ul className="divide-y divide-stone-100">
          {detail.quizzes.map((q) =>
            q.takeable ? (
              <li key={q.artifact_id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="text-sm text-ink">{q.title}</span>
                <Link
                  to={`/topics/${encodeURIComponent(detail.notebook_id)}/quiz/${encodeURIComponent(
                    q.artifact_id,
                  )}`}
                  className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white hover:opacity-90"
                >
                  Take ▸
                </Link>
              </li>
            ) : (
              <li key={q.artifact_id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="text-sm text-ink">{q.title}</span>
                <button
                  disabled
                  title="This quiz can't be taken in the hub yet"
                  className="cursor-not-allowed rounded-lg border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-medium text-muted"
                >
                  Take ▸ soon
                </button>
              </li>
            ),
          )}
        </ul>
      </Section>

      {detail.other_artifacts.length > 0 && (
        <Section title="Library" count={detail.other_artifacts.length}>
          <ul className="flex flex-wrap gap-2">
            {detail.other_artifacts.map((a) => (
              <li key={a.artifact_id}>
                <Badge tone="neutral" title={a.type}>
                  {a.title}
                </Badge>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {detail.warnings.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer select-none">
            {detail.warnings.length} parsing note(s)
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {detail.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  empty,
  children,
}: {
  title: string;
  count: number;
  empty?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-card">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <span className="text-sm text-muted">{count}</span>
      </div>
      {count === 0 ? <p className="text-sm text-muted">{empty ?? "Nothing here."}</p> : children}
    </section>
  );
}

function EpisodeRow({
  ep,
  url,
  onToggle,
}: {
  ep: Episode;
  url: string;
  onToggle: (ep: Episode) => void;
}) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <input
        type="checkbox"
        checked={ep.listened}
        onChange={() => onToggle(ep)}
        className="h-4 w-4 rounded border-stone-300 text-accent focus:ring-accent"
        aria-label={`Mark "${ep.title}" listened`}
      />
      <div className="min-w-0 flex-1">
        <p className={ep.listened ? "text-sm text-muted line-through" : "text-sm text-ink"}>
          {ep.title}
        </p>
        {(ep.fmt || ep.length) && (
          <p className="text-xs text-stone-400">{[ep.fmt, ep.length].filter(Boolean).join(" · ")}</p>
        )}
      </div>
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="shrink-0 text-xs font-medium text-accent hover:underline"
      >
        Play ↗
      </a>
    </li>
  );
}
