import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ProgressResponse, TopicProgress } from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
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

export default function Progress() {
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .progress()
      .then((p) => alive && setData(p))
      .catch((e) => alive && setError(e.message ?? "Failed to load progress"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

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

      {data && !data.has_data && (
        <Banner tone="info" title="No attempts yet">
          Take a quiz from any topic to start building your score history.{" "}
          <Link to="/" className="font-medium underline">
            Browse your topics →
          </Link>
        </Banner>
      )}

      {data && data.has_data && (
        <div className="space-y-8">
          {/* Summary band */}
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

          {/* Activity strip */}
          <section>
            <h2 className="mb-2 text-sm font-semibold text-ink">Recent activity</h2>
            <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-card">
              <ActivityStrip days={data.activity} />
              <p className="mt-2 text-xs text-muted">Last {data.activity.length} days · last touched {shortDate(data.summary.last_activity)}</p>
            </div>
          </section>

          {/* Per-topic trends */}
          <section>
            <h2 className="mb-2 text-sm font-semibold text-ink">By topic</h2>
            <div className="space-y-3">
              {data.topics.map((t) => (
                <TopicRow key={t.notebook_id} t={t} />
              ))}
            </div>
          </section>

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
        </div>
      )}
    </div>
  );
}
