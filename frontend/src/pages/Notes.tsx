import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { BriefNote } from "../api/types";
import { Banner } from "../components/Banner";
import { UndoToast, useUndoable } from "../components/undo";

// M2: the browse view for inline brief notes — every take/question you've attached to a
// brief item, filterable per topic (the kickoff's "browsable per topic"). Note rows are
// self-contained (topic/date/headline snapshots), so this page works even for days whose
// sweep files are long gone.
export default function Notes() {
  const [notes, setNotes] = useState<BriefNote[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [topic, setTopic] = useState("all");
  const { label: undoLabel, fire: holdThenFire, undo } = useUndoable();

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

  // Bug #14: a filter can outlive its topic (deleting the topic's last note) — derive
  // the effective filter so the page falls back to All instead of stranding behind a
  // false empty state with the select unmounted.
  const effectiveTopic = topics.some((t) => t.slug === topic) ? topic : "all";
  const visible = (notes ?? []).filter(
    (n) => effectiveTopic === "all" || n.topic_slug === effectiveTopic,
  );

  // FR10: the row vanishes now, the DELETE holds behind the undo toast; Undo restores
  // the row in place and the API is never called. A failed commit restores too and
  // reports itself accurately (bug #17: never under the load-failure heading).
  const remove = (note: BriefNote) => {
    const idx = (notes ?? []).findIndex((n) => n.id === note.id);
    const restore = () =>
      setNotes((prev) => {
        const list = [...(prev ?? [])];
        list.splice(Math.max(idx, 0), 0, note);
        return list;
      });
    setNotes((prev) => (prev ?? []).filter((n) => n.id !== note.id));
    holdThenFire(
      "Note deleted",
      () =>
        void api.deleteBriefNote(note.id).catch((e) => {
          restore();
          setDeleteError(e.message ?? "Failed to delete the note");
        }),
      restore,
    );
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
        {/* Full-width comfortable filter on phones; the compact inline control ≥sm. */}
        {topics.length > 1 && (
          <label className="w-full text-sm text-muted sm:w-auto">
            Topic{" "}
            <select
              value={effectiveTopic}
              onChange={(e) => setTopic(e.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-200 bg-white px-2 py-2.5 text-sm text-ink sm:ml-1 sm:mt-0 sm:w-auto sm:py-1.5"
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

      {/* Bug #17: a failed delete is its own event — it must never render under the
          load-failure heading while the fully loaded list sits right below it. */}
      {deleteError && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't delete the note">
            {deleteError}
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
                  onClick={() => remove(n)}
                  aria-label={`Delete note ${n.id}`}
                  className="-m-2 p-2 text-xs text-muted transition hover:text-ink sm:m-0 sm:p-0"
                >
                  Delete
                </button>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-ink/90">{n.body}</p>
            </article>
          ))}
        </div>
      )}

      <UndoToast label={undoLabel} onUndo={undo} />
    </div>
  );
}
