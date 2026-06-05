import { Link } from "react-router-dom";
import type { NotebookCard as Card } from "../api/types";
import { countSummary } from "../lib/format";
import { Badge } from "./Badge";

export function NotebookCard({ card }: { card: Card }) {
  return (
    <div className="group relative flex flex-col rounded-2xl border border-stone-200 bg-white p-5 shadow-card transition hover:shadow-cardHover">
      <div className="flex items-start justify-between gap-3">
        <Link
          to={card.topic_url}
          className="text-base font-semibold leading-snug text-ink hover:text-accent"
        >
          {card.title}
        </Link>
        {card.archived && (
          <Badge tone="stone" title="Archived notebook">
            archived
          </Badge>
        )}
      </div>

      <p className="mt-2 text-sm text-muted">{countSummary(card)}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {/* Deferred-to-later-phase signals render as calm placeholders. */}
        <Badge tone="neutral" title="Progress tracking arrives in a later phase">
          progress —
        </Badge>
        {card.due_for_review && <Badge tone="amber">🔁 due for review</Badge>}
      </div>

      <div className="mt-4 flex items-center gap-4 border-t border-stone-100 pt-3 text-sm">
        <Link
          to={card.topic_url}
          className="font-medium text-accent hover:underline"
          aria-label={`Open ${card.title} in the hub`}
        >
          Open in hub →
        </Link>
        <a
          href={card.notebooklm_url}
          target="_blank"
          rel="noreferrer"
          className="text-muted hover:text-ink hover:underline"
          aria-label={`Open ${card.title} in NotebookLM`}
        >
          NotebookLM ↗
        </a>
      </div>
    </div>
  );
}
