import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ApiError } from "../api/client";
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
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [pathFailed, setPathFailed] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setPathLoading(true);
    api
      .path(card.notebook_id)
      .then((p) => {
        if (!alive) return;
        setPath(p);
        setPathFailed(null);
      })
      // api.path() resolves null ONLY for a 404 and rethrows everything else, so "no path yet" and
      // "couldn't tell" stay distinct here: a hiccup must NOT render NoPathState, whose one control
      // is a Generate that REPLACES an existing path (08-12 hunt #2). Keep the error rather than
      // discarding it — a 422 (the file is on disk but unparseable) is PERMANENT and fixable by
      // hand, so it must not be described as a blip that will clear itself. The type-only import
      // means this reads `status` off the thrown value without a runtime dependency on the class.
      .catch((e: unknown) => {
        if (!alive) return;
        setPath(null);
        const status = (e as ApiError | undefined)?.status;
        setPathFailed(
          status === 422
            ? `This topic's path file is malformed and needs a fix — ${(e as Error).message}`
            : "Couldn't load this topic's path just now.",
        );
      })
      .finally(() => alive && setPathLoading(false));
    return () => {
      alive = false;
    };
  }, [card.notebook_id]);

  // The on-demand Designer (M8): one grounded claude -p authoring call composes a path over this
  // topic's real artifacts. Slow (~1–3 min) + never a 500 — a hiccup / bad output / fabricated id all
  // come back ok:false. On success the fresh path drops straight into state and the card lights up.
  const onGenerate = async () => {
    if (generating) return;
    setGenerating(true);
    setGenError(null);
    try {
      const res = await api.generatePath(card.notebook_id);
      if (res.ok && res.path) {
        setPath(res.path);
      } else {
        setGenError(res.error || res.errors.join("; ") || "Couldn't compose a path just now.");
      }
    } catch (e) {
      setGenError((e as Error).message ?? "Couldn't compose a path just now.");
    } finally {
      setGenerating(false);
    }
  };

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
        ) : pathFailed ? (
          <p className="mt-2 text-sm text-muted">{pathFailed}</p>
        ) : (
          <NoPathState onGenerate={onGenerate} generating={generating} error={genError} />
        )}
      </div>

      {/* Cross-link: the course(s) built on this same notebook, so the topic + course stop
          reading as duplicate entries across the Learning / Courses tabs. */}
      {card.courses?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {card.courses.map((c) => (
            <Link
              key={c.slug}
              to={`/courses/${encodeURIComponent(c.slug)}`}
              className="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent hover:opacity-90"
              title={`Also taught as a course: ${c.title}`}
            >
              📘 Course: {c.title} →
            </Link>
          ))}
        </div>
      )}

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

// No path composed yet. ✨ Generate runs the on-demand Designer (one grounded claude -p call over the
// topic's real artifacts, ~1–3 min); on success the card re-renders into PathState. The topic itself
// also stays reachable via the title while a path doesn't exist.
function NoPathState({
  onGenerate,
  generating,
  error,
}: {
  onGenerate: () => void;
  generating: boolean;
  error: string | null;
}) {
  return (
    <div>
      <p className="text-sm text-muted">
        No path yet — let the designer compose one from these artifacts.
      </p>
      <button
        type="button"
        onClick={onGenerate}
        disabled={generating}
        aria-busy={generating}
        className="mt-3 inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-60"
      >
        {generating ? (
          <>
            <span
              className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white"
              aria-hidden
            />
            Composing your path… (~1–3 min)
          </>
        ) : (
          "✨ Generate path"
        )}
      </button>
      {error && <p className="mt-2 text-xs text-amber-700">{error}</p>}
    </div>
  );
}
