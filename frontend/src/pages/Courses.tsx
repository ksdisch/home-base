import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CourseSummary } from "../api/types";
import { Banner } from "../components/Banner";
import { CourseCard } from "../components/CourseCard";

export default function Courses() {
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .courses()
      .then((r) => alive && setCourses(r.courses))
      .catch((e) => alive && setError(e.message ?? "Failed to load courses"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Courses</h1>
        <p className="mt-1 text-sm text-muted">
          {loading
            ? "Loading your courses…"
            : "Structured, multi-format learning paths. Build a new one with /build-course."}
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't load your courses">
            {error}
          </Banner>
        </div>
      )}

      {loading && !courses && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-2xl border border-line bg-card/60" />
          ))}
        </div>
      )}

      {courses && courses.length === 0 && (
        <Banner tone="muted" title="No courses yet">
          Generate one with the <code>/build-course &lt;topic&gt;</code> command (or the{" "}
          <code>course-builder</code> skill) — it drops a course into your hub and it shows up here.
        </Banner>
      )}

      {courses && courses.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((c) => (
            <CourseCard key={c.slug} course={c} />
          ))}
        </div>
      )}
    </div>
  );
}
