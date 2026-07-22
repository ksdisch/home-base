import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { NotebookCard as Card, PathResponse } from "../api/types";
import { clampPct, confidenceDots, countSummary } from "../lib/format";
import { Badge } from "./Badge";
import { masteryTone } from "./MasteryBar";

// M8: a Learning card is a path entry, not a dead inventory. It fetches this topic's path (404 = no
// path composed yet — the slice ships exactly one, the Jacobian-Lens fixture) and shows the three
// live axes + one primary action (Generate / Continue / Review), replacing the old "mastery —" chip.

const KIND_ICON: Record<string, string> = {
  intro: "🧭",
  audio: "🎧",
  read: "📖",
  flashcards: "🃏",
  quiz: "❓",
  bridge: "✨",
  reflect: "✍️",
  recap: "🔁",
};
const kindIcon = (k: string) => KIND_ICON[k] ?? "•";

// Mastery's honest tone as a text color (same 0.5/0.75 thresholds as the Badge/MasteryBar).
const masteryTextTone: Record<"accent" | "amber" | "stone", string> = {
  accent: "text-accent",
  amber: "text-amber-700",
  stone: "text-muted",
};

export function NotebookCard({ card }: { card: Card }) {
  const [path, setPath] = useState<PathResponse | null>(null);
  const [pathLoading, setPathLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setPathLoading(true);
    api
      .path(card.notebook_id)
      .then((p) => alive && setPath(p))
      .catch(() => alive && setPath(null)) // a hiccup reads as "no path yet" — the card is a nicety
      .finally(() => alive && setPathLoading(false));
    return () => {
      alive = false;
    };
  }, [card.notebook_id]);

  const pathMinutes = path ? path.steps.reduce((n, s) => n + (s.estimated_minutes ?? 0), 0) : 0;

  return (
    <div className="group relative flex flex-col rounded-2xl border border-line bg-card p-5 shadow-card transition hover:shadow-cardHover">
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

      {/* Subline: the composed path's shape once it exists, else the artifact inventory it'd draw from. */}
      {path ? (
        <p className="mt-1 text-xs text-muted">
          {path.step_count}-step path{pathMinutes > 0 ? ` · ~${pathMinutes} min` : ""}
        </p>
      ) : (
        <p className="mt-2 text-sm text-muted">{countSummary(card)}</p>
      )}

      <div className="mt-3 flex-1">
        {pathLoading ? (
          <div className="h-16 animate-pulse rounded-lg bg-line-soft/60" />
        ) : path ? (
          <PathState card={card} path={path} />
        ) : (
          <NoPathState />
        )}
      </div>

      <div className="mt-4 flex items-center gap-4 border-t border-line-soft pt-3 text-sm">
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

// The three live axes + the lifecycle's one primary action. Continue while a path is in progress;
// Review once it's complete (↻ when recall has decayed due); Start on a fresh, untouched path.
function PathState({ card, path }: { card: Card; path: PathResponse }) {
  const complete = path.progress_pct >= 100;
  const nextStep = path.steps.find((s) => !s.completed);
  const actionLabel = complete
    ? card.due_for_review
      ? "↻ Review →"
      : "Review →"
    : path.progress_pct > 0
      ? "Continue →"
      : "Start →";

  return (
    <div>
      <div className="space-y-1.5 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-16 shrink-0 text-muted">Progress</span>
          <b className="text-ink">{path.progress_pct}%</b>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-line-soft">
            <span
              className="block h-full rounded-full bg-accent"
              style={{ width: `${clampPct(path.progress_pct)}%` }}
            />
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted">
          <span>
            Mastery{" "}
            {path.mastery != null ? (
              <b className={masteryTextTone[masteryTone(path.mastery)]}>
                {Math.round(path.mastery * 100)}%
              </b>
            ) : (
              <b className="font-medium opacity-70">— not tested</b>
            )}
          </span>
          <span>
            Confidence{" "}
            {path.confidence != null ? (
              <b className="text-accent" title={`Mean self-rating ${path.confidence.toFixed(1)} / 5`}>
                {confidenceDots(path.confidence)}
              </b>
            ) : (
              <b className="opacity-70">—</b>
            )}
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Link
          to={`/learning/path/${encodeURIComponent(card.notebook_id)}`}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          {actionLabel}
        </Link>
        {nextStep && (
          <span className="min-w-0 truncate text-xs text-muted">
            Next: <span aria-hidden>{kindIcon(nextStep.kind)}</span> {nextStep.title}
          </span>
        )}
      </div>
    </div>
  );
}

// No path composed yet. The on-demand ✨ Generate designer is Phase 7, so the button is a calm stub
// (mirrors the "Take ▸ soon" disabled-quiz pattern) — the topic itself stays reachable via the title.
function NoPathState() {
  return (
    <div>
      <p className="text-sm text-muted">
        No path yet — the designer can compose one from these artifacts.
      </p>
      <button
        type="button"
        disabled
        title="On-demand path generation arrives in a later phase — the Jacobian-Lens example is the one live path for now."
        className="mt-3 cursor-not-allowed rounded-lg border border-line bg-line-soft px-3 py-1.5 text-sm font-medium text-muted"
      >
        ✨ Generate path · soon
      </button>
    </div>
  );
}
