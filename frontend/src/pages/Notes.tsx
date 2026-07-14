import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { BriefNote } from "../api/types";
import { Banner } from "../components/Banner";

// M2: the browse view for inline brief notes — every take/question you've attached to a
// brief item, filterable per topic (the kickoff's "browsable per topic"). Note rows are
// self-contained (topic/date/headline snapshots), so this page works even for days whose
// sweep files are long gone.
export default function Notes() {
  const [notes, setNotes] = useState<BriefNote[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [topic, setTopic] = useState("all");

  useEffect(() => {
    let alive = true;
    api
      .briefNotes()
      .then((r) => alive && setNotes(r.notes))
      .catch((e) => alive && setError(e.message ?? "Failed to load notes"));
    return () => {
      alive = false;
    };
  }, []);

  const topics = useMemo(() => {
    const seen = new Map<string, string>();
    for (const n of notes ?? []) {
      if (!seen.has(n.topic_slug)) seen.set(n.topic_slug, n.topic_title || n.topic_slug);
    }
    return [...seen.entries()].map(([slug, title]) => ({ slug, title }));
  }, [notes]);

  const visible = (notes ?? []).filter((n) => topic === "all" || n.topic_slug === topic);

  const remove = (id: number) => {
    api
      .deleteBriefNote(id)
      .then(() => setNotes((prev) => (prev ?? []).filter((n) => n.id !== id)))
      .catch((e) => setError(e.message ?? "Failed to delete the note"));
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Notes</h1>
          <p className="mt-1 text-sm text-muted">
            Your takes and questions from the Today brief, newest first.
          </p>
        </div>
        {topics.length > 1 && (
          <label className="text-sm text-muted">
            Topic{" "}
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="ml-1 rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-sm text-ink"
            >
              <option value="all">All topics</option>
              {topics.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.title}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {error && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't load notes">
            {error}
          </Banner>
        </div>
      )}

      {notes && visible.length === 0 && !error && (
        <Banner tone="info" title="No notes yet">
          Add one from an item on the Today brief — they'll collect here.
        </Banner>
      )}

      {visible.length > 0 && (
        <div className="space-y-3">
          {visible.map((n) => (
            <article key={n.id} className="rounded-2xl border border-stone-200 bg-white/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="text-xs text-muted">
                  <span className="font-medium text-accent">{n.topic_title || n.topic_slug}</span>
                  {" · "}
                  {n.brief_date}
                  {" · "}
                  {n.item_headline}
                </div>
                <button
                  onClick={() => remove(n.id)}
                  aria-label={`Delete note ${n.id}`}
                  className="text-xs text-muted transition hover:text-ink"
                >
                  Delete
                </button>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-ink/90">{n.body}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
