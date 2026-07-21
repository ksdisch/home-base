import { Link } from "react-router-dom";
import type { CourseSummary } from "../api/types";
import { Badge } from "./Badge";

const LEVEL_TONE = {
  beginner: "accent",
  intermediate: "amber",
  advanced: "stone",
} as const;

export function CourseCard({ course }: { course: CourseSummary }) {
  const pct = Math.max(0, Math.min(100, course.progress_pct));
  return (
    <div className="group relative flex flex-col rounded-2xl border border-line bg-card p-5 shadow-card transition hover:shadow-cardHover">
      <div className="flex items-start justify-between gap-3">
        <Link
          to={`/courses/${encodeURIComponent(course.slug)}`}
          className="text-base font-semibold leading-snug text-ink hover:text-accent"
        >
          {course.title}
        </Link>
        <Badge tone={LEVEL_TONE[course.level as keyof typeof LEVEL_TONE] ?? "neutral"}>
          {course.level}
        </Badge>
      </div>

      {course.summary && (
        <p className="mt-2 line-clamp-3 text-sm text-muted">{course.summary}</p>
      )}

      <p className="mt-3 text-xs text-muted">
        {course.module_count} modules · {course.lesson_count} lessons
        {course.estimated_hours ? ` · ~${course.estimated_hours}h` : ""}
      </p>

      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs text-muted">
          <span>{course.completed_lessons}/{course.lesson_count} done</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft" role="img" aria-label={`Progress ${pct}%`}>
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="mt-4 border-t border-line-soft pt-3 text-sm">
        <Link
          to={`/courses/${encodeURIComponent(course.slug)}`}
          className="font-medium text-accent hover:underline"
          aria-label={`Open the ${course.title} course`}
        >
          {pct > 0 ? "Continue →" : "Start course →"}
        </Link>
      </div>
    </div>
  );
}
