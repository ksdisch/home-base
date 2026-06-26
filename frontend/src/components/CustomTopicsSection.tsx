import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { CustomTopic } from "../api/types";
import { Banner } from "./Banner";
import { CustomTopicCard } from "./CustomTopicCard";
import { CustomTopicForm } from "./CustomTopicForm";

// Self-contained "Custom" home section: lists non-NotebookLM topics from /api/custom-topics and
// lets you add/edit them inline. Owns its own fetch so the Home page stays a thin composer.
export function CustomTopicsSection() {
  const [topics, setTopics] = useState<CustomTopic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    setError(null); // clear any stale error before refetching
    return api
      .customTopics()
      .then((r) => setTopics(r.topics))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load custom topics"));
  }, []);

  useEffect(() => {
    let alive = true;
    api
      .customTopics()
      .then((r) => alive && setTopics(r.topics))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "Failed to load custom topics"));
    return () => {
      alive = false;
    };
  }, []);

  const count = topics?.length ?? 0;

  return (
    <section className="mb-10">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h2 className="text-lg font-semibold text-ink">Custom</h2>
          <span className="text-sm text-muted">{count}</span>
        </div>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            className="rounded-lg px-2.5 py-1 text-sm font-medium text-accent hover:bg-accent-soft"
          >
            + Add custom topic
          </button>
        )}
      </div>

      {error && (
        <div className="mb-3">
          <Banner tone="warning" title="Couldn't load custom topics">
            {error}
          </Banner>
        </div>
      )}

      {adding && (
        <div className="mb-4 rounded-2xl border border-stone-200 bg-white p-5 shadow-card">
          <CustomTopicForm
            submitLabel="Add topic"
            onCancel={() => setAdding(false)}
            onSubmit={async (values) => {
              await api.addCustomTopic(values);
              setAdding(false);
              await load();
            }}
          />
        </div>
      )}

      {topics && topics.length === 0 && !adding ? (
        <p className="rounded-xl border border-dashed border-stone-200 bg-white/50 px-4 py-6 text-sm text-muted">
          Track a book, a YouTube series, or a loose interest with no NotebookLM artifacts — manual
          progress + notes, all yours.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topics?.map((t) => (
            <CustomTopicCard key={t.id} topic={t} onChanged={load} />
          ))}
        </div>
      )}
    </section>
  );
}
