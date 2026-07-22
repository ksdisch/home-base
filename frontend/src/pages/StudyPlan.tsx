import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { PathSummary, StudyPlanResponse, StudyPlanSegment } from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { cx } from "../lib/format";
import {
  PLAN_MINUTES,
  pathProgressSummary,
  planSummary,
  quizPlayerPath,
  segmentSummary,
  stepKindIcon,
} from "../lib/plan";

function MinutesPicker({
  value,
  onChange,
}: {
  value: number;
  onChange: (m: number) => void;
}) {
  return (
    <div className="inline-flex rounded-xl border border-line bg-card p-1 shadow-card">
      {PLAN_MINUTES.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          aria-pressed={m === value}
          className={cx(
            "rounded-lg px-3 py-1.5 text-sm font-medium transition",
            m === value ? "bg-accent-soft text-accent" : "text-muted hover:text-ink",
          )}
        >
          {m}m
        </button>
      ))}
    </div>
  );
}

// One Continue-lane card: an in-progress path + where to resume. Links into the outline+detail
// player at the topic (the same route the Learning card's Continue uses).
function ContinueCard({ item }: { item: PathSummary }) {
  const next = item.next_step;
  return (
    <Link
      to={`/learning/path/${encodeURIComponent(item.notebook_id)}`}
      className="group block rounded-2xl border border-line bg-card p-4 shadow-card transition hover:shadow-cardHover"
    >
      <div className="flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-ink">{item.title}</span>
            <Badge tone="neutral">{pathProgressSummary(item)}</Badge>
          </div>
          {next && (
            <div className="mt-0.5 truncate text-xs text-muted">
              <span className="mr-1">{stepKindIcon(next.kind)}</span>
              Next: {next.title}
            </div>
          )}
        </div>
        <span className="shrink-0 text-sm font-medium text-accent group-hover:underline">
          {item.completed_steps === 0 ? "Start →" : "Continue →"}
        </span>
      </div>
    </Link>
  );
}

function SegmentCard({ seg }: { seg: StudyPlanSegment }) {
  const path = seg.topic_url
    ? quizPlayerPath(seg.notebook_id, seg.quiz_artifact_id)
    : null;
  const inner = (
    <div className="flex items-center gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-ink">{seg.title}</span>
          {seg.due_count > 0 && <Badge tone="amber">🔁 {seg.due_count} due</Badge>}
        </div>
        <div className="mt-0.5 text-xs text-muted">{segmentSummary(seg)}</div>
      </div>
      {path && (
        <span className="shrink-0 text-sm font-medium text-accent group-hover:underline">
          Review →
        </span>
      )}
    </div>
  );
  return (
    <div className="group rounded-2xl border border-line bg-card p-4 shadow-card transition hover:shadow-cardHover">
      {path ? (
        <Link to={path} className="block">
          {inner}
        </Link>
      ) : (
        inner
      )}
    </div>
  );
}

export default function StudyPlan() {
  const [minutes, setMinutes] = useState(20);
  const [plan, setPlan] = useState<StudyPlanResponse | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(true);
  const [paths, setPaths] = useState<PathSummary[] | null>(null);

  // Review lane: the SR session — re-fetched whenever the minute budget changes.
  useEffect(() => {
    let alive = true;
    setPlanLoading(true);
    setPlanError(null); // clear any stale error before refetching (e.g. when the minute budget changes)
    api
      .studyPlan(minutes)
      .then((p) => alive && setPlan(p))
      .catch((e) => alive && setPlanError(e.message ?? "Failed to build a study plan"))
      .finally(() => alive && setPlanLoading(false));
    return () => {
      alive = false;
    };
  }, [minutes]);

  // Continue lane: coverage-driven, independent of the minute budget (fetch once). A failure
  // degrades to an empty lane — Continue is a head start, it never blocks the Review session.
  useEffect(() => {
    let alive = true;
    api
      .paths()
      .then((r) => alive && setPaths(r.items))
      .catch(() => alive && setPaths([]));
    return () => {
      alive = false;
    };
  }, []);

  const continueItems = (paths ?? []).filter((p) => p.next_step);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Today's plan</h1>
          <p className="mt-1 text-sm text-muted">
            {planLoading
              ? "Building your session…"
              : plan && plan.has_data
                ? planSummary(plan)
                : "A focused, interleaved review session sized to your time."}
          </p>
        </div>
        <MinutesPicker value={minutes} onChange={setMinutes} />
      </div>

      {/* Continue lane — coverage-driven, non-empty day one via the bundled example path. */}
      {continueItems.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
            Continue
          </h2>
          <div className="space-y-3">
            {continueItems.map((item) => (
              <ContinueCard key={item.notebook_id} item={item} />
            ))}
          </div>
        </section>
      )}

      {/* Review lane — the existing spaced-repetition session. */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">Review</h2>

        {planError && (
          <div className="mb-4">
            <Banner tone="warning" title="Couldn't build your plan">
              {planError}
            </Banner>
          </div>
        )}

        {planLoading && !plan && (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-2xl border border-line bg-card/60" />
            ))}
          </div>
        )}

        {plan && !plan.has_data && (
          <Banner tone="info" title="No questions to schedule yet">
            Take a quiz from any topic and your answers start feeding the spaced-repetition
            scheduler.{" "}
            <Link to="/learning" className="font-medium underline">
              Browse your topics →
            </Link>
          </Banner>
        )}

        {plan && plan.has_data && (
          <div className="space-y-4">
            {!plan.has_due && (
              <Banner tone="info" title="Nothing due — you're current">
                Everything you've practiced is still fresh. These are a head start if you've got the
                time.
              </Banner>
            )}
            <div className="space-y-3">
              {plan.segments.map((s) => (
                <SegmentCard key={`${s.notebook_id}:${s.quiz_artifact_id}`} seg={s} />
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
