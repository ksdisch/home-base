import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { CourseSummary, ReviewResponse } from "../api/types";

// M2 "Your learning" strip on the Today page — surfacing only (kickoff scope): due
// reviews + active courses from the existing hub, linking into /plan and /courses.
// It must never block or clutter the morning read: it renders nothing while loading,
// on fetch errors, or when there's genuinely nothing to surface.
export function YourLearning() {
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([api.review(), api.courses()]).then(([r, c]) => {
      if (!alive) return;
      if (r.status === "fulfilled") setReview(r.value);
      if (c.status === "fulfilled") setCourses(c.value.courses);
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  if (!loaded) return null;
  const due = review?.has_data ? review.items.filter((i) => i.due) : [];
  const active = courses.filter((c) => c.progress_pct < 100);
  if (due.length === 0 && active.length === 0) return null;

  return (
    <section className="rounded-2xl border border-line bg-card/60 p-5">
      <h2 className="text-lg font-semibold text-ink">Your learning</h2>
      <div className="mt-3 grid gap-5 sm:grid-cols-2">
        {due.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-ink">
              Due for review
              <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
                {due.length}
              </span>
            </h3>
            <ul className="mt-2 space-y-1">
              {due.slice(0, 3).map((i) => (
                <li key={i.notebook_id} className="text-sm text-ink/90">
                  {i.title}
                  {i.reason && <span className="text-xs text-muted"> — {i.reason}</span>}
                </li>
              ))}
            </ul>
            <Link to="/plan" className="mt-2 inline-block text-sm text-accent hover:underline">
              Start a session →
            </Link>
          </div>
        )}
        {active.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-ink">Active courses</h3>
            <ul className="mt-2 space-y-1">
              {active.slice(0, 3).map((c) => (
                <li key={c.slug} className="text-sm text-ink/90">
                  <Link to={`/courses/${c.slug}`} className="hover:underline">
                    {c.title}
                  </Link>
                  <span className="ml-2 text-xs text-muted">{c.progress_pct}%</span>
                </li>
              ))}
            </ul>
            <Link to="/courses" className="mt-2 inline-block text-sm text-accent hover:underline">
              All courses →
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}
