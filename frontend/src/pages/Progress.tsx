import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  ProgressResponse,
  ReflectionItem,
  ReflectionsResponse,
  ReviewItem,
  ReviewResponse,
  TopicProgress,
} from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { MasteryBar } from "../components/MasteryBar";
import { Sparkline } from "../components/Sparkline";
import { cx, shortDate } from "../lib/format";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-card" title={hint}>
      <div className="text-2xl font-semibold text-ink">{value}</div>
      <div className="mt-0.5 text-xs uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

// A calm one-cell-per-day activity strip. Deeper cell = more activity that day.
function ActivityStrip({ days }: { days: ProgressResponse["activity"] }) {
  const max = Math.max(1, ...days.map((d) => d.count));
  return (
    <div className="flex flex-wrap gap-1" aria-label="Recent activity">
      {days.map((d) => {
        const intensity = d.count === 0 ? 0 : Math.ceil((d.count / max) * 3); // 0..3
        const bg = ["bg-stone-100", "bg-accent/30", "bg-accent/60", "bg-accent"][intensity];
        return (
          <div
            key={d.day}
            className={cx("h-3.5 w-3.5 rounded-sm", bg)}
            title={`${shortDate(d.day)}: ${d.count} ${d.count === 1 ? "activity" : "activities"}`}
          />
        );
      })}
    </div>
  );
}

function pctTone(pct: number): "accent" | "amber" | "stone" {
  if (pct >= 80) return "accent";
  if (pct >= 50) return "amber";
  return "stone";
}

// The Phase-4 spaced-repetition queue: one row per practiced topic, due-first, with the decay
// model's "why this surfaced" reason and a retention bar. Actionable, not a scoreboard.
function ReviewRow({ item }: { item: ReviewItem }) {
  const inner = (
    <div className="flex items-center gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-ink">{item.title}</span>
          {item.due && <Badge tone="amber">🔁 due</Badge>}
        </div>
        <div className="mt-0.5 text-xs text-muted">{item.reason}</div>
        <MasteryBar mastery={item.decayed} className="mt-2 max-w-xs" />
      </div>
      {item.topic_url && (
        <span className="shrink-0 text-sm font-medium text-accent group-hover:underline">Review →</span>
      )}
    </div>
  );
  return (
    <div className="group rounded-2xl border border-stone-200 bg-white p-4 shadow-card transition hover:shadow-cardHover">
      {item.topic_url ? (
        <Link to={item.topic_url} className="block">
          {inner}
        </Link>
      ) : (
        inner
      )}
    </div>
  );
}

function ReviewNext({ review }: { review: ReviewResponse | null }) {
  if (!review || !review.has_data) return null;
  const due = review.items.filter((i) => i.due);
  const shown = due.length > 0 ? due : review.items.slice(0, 3);
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Review next</h2>
        {review.due_count > 0 && (
          <span className="text-xs text-muted">
            {review.due_count} {review.due_count === 1 ? "topic" : "topics"} due
          </span>
        )}
      </div>
      {due.length === 0 ? (
        <Banner tone="info" title="Nothing due — you're current">
          Mastery on every topic you've practiced is still fresh. Keep the streak going.
        </Banner>
      ) : (
        <p className="mb-3 text-xs text-muted">
          Mastery decays over time since your last review — these have faded most.
        </p>
      )}
      <div className="space-y-3">
        {shown.map((i) => (
          <ReviewRow key={i.notebook_id} item={i} />
        ))}
      </div>
    </section>
  );
}

function TopicRow({ t }: { t: TopicProgress }) {
  const trend = t.points.map((p) => p.pct);
  const inner = (
    <div className="flex items-center gap-4">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-ink">{t.title}</div>
        <div className="mt-0.5 text-xs text-muted">
          {t.attempts} {t.attempts === 1 ? "attempt" : "attempts"} · last {shortDate(t.last_practiced)}
        </div>
      </div>
      <Sparkline values={trend} className="hidden shrink-0 sm:block" />
      <div className="flex shrink-0 items-center gap-2">
        <Badge tone={pctTone(t.last_pct)} title="Most recent score">
          {Math.round(t.last_pct)}%
        </Badge>
        <span className="hidden text-xs text-muted md:inline" title="Best · average">
          best {Math.round(t.best_pct)}% · avg {Math.round(t.avg_pct)}%
        </span>
      </div>
    </div>
  );
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-card transition hover:shadow-cardHover">
      {t.topic_url ? (
        <Link to={t.topic_url} className="block hover:[&_.text-ink]:text-accent">
          {inner}
        </Link>
      ) : (
        inner
      )}
    </div>
  );
}

// The reflection journal — the `/episode-review` skill's "how well did it land?" notes, finally
// surfaced. Read-only, newest first, with the self-rated grasp where present.
function GraspChip({ rating }: { rating?: number | null }) {
  if (rating == null) return null;
  const tone = rating >= 4 ? "accent" : rating >= 3 ? "amber" : "stone";
  return (
    <Badge tone={tone} title="Self-rated grasp (1–5)">
      grasp {rating}/5
    </Badge>
  );
}

function ReflectionsJournal({ reflections }: { reflections: ReflectionsResponse | null }) {
  if (!reflections || !reflections.has_data) return null;
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Reflections</h2>
        {reflections.avg_grasp != null && (
          <span className="text-xs text-muted">avg grasp {reflections.avg_grasp}/5</span>
        )}
      </div>
      <p className="mb-3 text-xs text-muted">
        Your post-episode notes — what landed and what didn't.
      </p>
      <div className="space-y-3">
        {reflections.items.map((r: ReflectionItem) => {
          const body = (
            <div className="flex items-start gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-ink">{r.title}</span>
                  <GraspChip rating={r.grasp_rating} />
                </div>
                {r.body && <p className="mt-1 whitespace-pre-wrap text-sm text-ink/80">{r.body}</p>}
                <div className="mt-1 text-xs text-muted">{shortDate(r.created_at)}</div>
              </div>
            </div>
          );
          return (
            <div
              key={r.id}
              className="rounded-2xl border border-stone-200 bg-white p-4 shadow-card"
            >
              {r.topic_url ? (
                <Link to={r.topic_url} className="block hover:[&_.text-ink]:text-accent">
                  {body}
                </Link>
              ) : (
                body
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function Progress() {
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [reflections, setReflections] = useState<ReflectionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    // Each section renders off its OWN endpoint (see below), so fetch them independently: a single
    // flaky call must degrade only its own section, not blank the whole dashboard. The error banner
    // shows only if EVERY endpoint failed.
    Promise.allSettled([api.progress(), api.review(), api.reflections()])
      .then(([p, r, refl]) => {
        if (!alive) return;
        if (p.status === "fulfilled") setData(p.value);
        if (r.status === "fulfilled") setReview(r.value);
        if (refl.status === "fulfilled") setReflections(refl.value);
        if (p.status === "rejected" && r.status === "rejected" && refl.status === "rejected") {
          setError((p.reason instanceof Error && p.reason.message) || "Failed to load progress");
        }
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  // The page fuses three independent endpoints. Each section is shown based on ITS OWN data, not on
  // whether a quiz has been graded — reflections and listens write activity + reflection rows with no
  // attempt, so gating the whole block on progress.has_data hid the journal + activity strip for
  // reflections-only / listen-only users.
  const hasActivity = (data?.activity ?? []).some((d) => d.count > 0);
  const hasAnything =
    !!data?.has_data || hasActivity || !!review?.has_data || !!reflections?.has_data;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Your progress</h1>
        <p className="mt-1 text-sm text-muted">
          {loading ? "Adding up your attempts…" : "Score trends and streaks from every quiz you've taken in the hub."}
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't load your progress">
            {error}
          </Banner>
        </div>
      )}

      {loading && !data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-2xl border border-stone-200 bg-white/60" />
          ))}
        </div>
      )}

      {data && !hasAnything && (
        <Banner tone="info" title="No attempts yet">
          Take a quiz from any topic to start building your score history.{" "}
          <Link to="/" className="font-medium underline">
            Browse your topics →
          </Link>
        </Banner>
      )}

      {data && hasAnything && (
        <div className="space-y-8">
          {/* Review next — the actionable headline (self-guards on review.has_data) */}
          <ReviewNext review={review} />

          {/* Summary band — quiz-attempt stats; only meaningful once a quiz has been graded */}
          {data.has_data && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <Stat label="Attempts" value={String(data.summary.attempts_total)} />
              <Stat label="Avg score" value={`${Math.round(data.summary.avg_pct)}%`} />
              <Stat label="Topics" value={String(data.summary.topics_practiced)} hint="Topics you've practiced" />
              <Stat
                label="Streak"
                value={data.summary.current_streak > 0 ? `🔥 ${data.summary.current_streak}` : "0"}
                hint="Consecutive days with activity"
              />
              <Stat label="Best streak" value={String(data.summary.longest_streak)} />
            </div>
          )}

          {/* Activity strip — driven by activity rows (reflections/listens too), so show it
              whenever there's any activity, not only after a quiz is graded */}
          {hasActivity && (
            <section>
              <h2 className="mb-2 text-sm font-semibold text-ink">Recent activity</h2>
              <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-card">
                <ActivityStrip days={data.activity} />
                <p className="mt-2 text-xs text-muted">Last {data.activity.length} days · last touched {shortDate(data.summary.last_activity)}</p>
              </div>
            </section>
          )}

          {/* Per-topic trends — quiz-attempt data */}
          {data.has_data && (
            <section>
              <h2 className="mb-2 text-sm font-semibold text-ink">By topic</h2>
              <div className="space-y-3">
                {data.topics.map((t) => (
                  <TopicRow key={t.notebook_id} t={t} />
                ))}
              </div>
            </section>
          )}

          {/* Shaky spots */}
          {data.shaky.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-semibold text-ink">Shaky spots</h2>
              <p className="mb-3 text-xs text-muted">
                Quizzes with the most missed questions — good candidates to retake.
              </p>
              <div className="space-y-3">
                {data.shaky.map((s) => (
                  <div
                    key={`${s.notebook_id}:${s.quiz_artifact_id}`}
                    className="flex items-center justify-between gap-4 rounded-2xl border border-stone-200 bg-white p-4 shadow-card"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-ink">{s.title}</div>
                      <div className="mt-0.5 text-xs text-muted">
                        {s.total_misses} {s.total_misses === 1 ? "miss" : "misses"} across {s.shaky_questions}{" "}
                        {s.shaky_questions === 1 ? "question" : "questions"} · last {shortDate(s.last_review_at)}
                      </div>
                    </div>
                    {s.topic_url && (
                      <Link to={s.topic_url} className="shrink-0 text-sm font-medium text-accent hover:underline">
                        Open →
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Reflection journal — surfacing the captured-but-previously-hidden notes */}
          <ReflectionsJournal reflections={reflections} />
        </div>
      )}
    </div>
  );
}
