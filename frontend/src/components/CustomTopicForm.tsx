import { useState } from "react";
import type { CustomTopicUpdate } from "../api/types";

// One small form reused for both add and edit. Returns only the fields, normalized; the caller
// owns the POST/PATCH + refetch. Title is required; progress is a 0–100 slider.
export function CustomTopicForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: { title?: string; notes?: string; progress_pct?: number };
  submitLabel: string;
  onSubmit: (values: Required<CustomTopicUpdate>) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [progress, setProgress] = useState(initial?.progress_pct ?? 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("Give it a title.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ title: title.trim(), notes, progress_pct: progress });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save. Try again.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="mb-1 block text-xs font-medium text-muted">Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="A book, a YouTube series, a loose interest…"
          autoFocus
          className="w-full rounded-xl border border-line bg-card px-3 py-2 text-sm text-ink outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-muted">Notes (optional)</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full resize-y rounded-xl border border-line bg-card px-3 py-2 text-sm text-ink outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="mb-1 flex items-center justify-between text-xs font-medium text-muted">
          <span>Progress</span>
          <span className="tabular-nums text-ink">{progress}%</span>
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={progress}
          onChange={(e) => setProgress(Number(e.target.value))}
          className="w-full accent-accent"
        />
      </div>

      {error && <p className="text-xs text-amber-700">{error}</p>}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={busy}
          className="rounded-xl bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="rounded-xl px-3 py-1.5 text-sm font-medium text-muted hover:text-ink"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
