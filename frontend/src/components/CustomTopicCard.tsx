import { useState } from "react";
import { api } from "../api/client";
import type { CustomTopic } from "../api/types";
import { shortDate } from "../lib/format";
import { CustomTopicForm } from "./CustomTopicForm";

function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft" role="img" aria-label={`${clamped}% complete`}>
      <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${clamped}%` }} />
    </div>
  );
}

export function CustomTopicCard({
  topic,
  onChanged,
}: {
  topic: CustomTopic;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);

  if (editing) {
    return (
      <div className="rounded-2xl border border-line bg-card p-5 shadow-card">
        <CustomTopicForm
          initial={topic}
          submitLabel="Save"
          onCancel={() => setEditing(false)}
          onSubmit={async (values) => {
            await api.updateCustomTopic(topic.id, values);
            setEditing(false);
            onChanged();
          }}
        />
      </div>
    );
  }

  return (
    <div className="group flex flex-col rounded-2xl border border-line bg-card p-5 shadow-card transition hover:shadow-cardHover">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-base font-semibold leading-snug text-ink">{topic.title}</h3>
        <button
          onClick={() => setEditing(true)}
          className="shrink-0 text-xs font-medium text-muted opacity-0 transition hover:text-accent group-hover:opacity-100"
          aria-label={`Edit ${topic.title}`}
        >
          Edit
        </button>
      </div>

      {topic.notes.trim() && (
        <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-sm text-muted">{topic.notes}</p>
      )}

      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-medium text-muted">Progress</span>
          <span className="tabular-nums text-ink">{topic.progress_pct}%</span>
        </div>
        <ProgressBar pct={topic.progress_pct} />
      </div>

      <p className="mt-3 border-t border-line-soft pt-3 text-xs text-muted">
        updated {shortDate(topic.updated_at)}
      </p>
    </div>
  );
}
