import type { PathSummary, StudyPlanResponse, StudyPlanSegment } from "../api/types";

// The minute budgets the Study Plan page offers.
export const PLAN_MINUTES = [10, 20, 30, 45] as const;

// A plan segment can be a NotebookLM topic quiz or a course quiz. Course segments carry the
// synthetic ``course:<slug>`` notebook id (mirrors backend app.courses.COURSE_NB_PREFIX).
const COURSE_NB_PREFIX = "course:";

export function isCourseSegment(notebookId: string): boolean {
  return notebookId.startsWith(COURSE_NB_PREFIX);
}

// The deep link to retake a quiz. Topic quizzes route as /topics/:id/quiz/:quizId; course quizzes
// as /courses/:slug/quiz?path=… (the material path can contain a slash → it rides the query string).
export function quizPlayerPath(notebookId: string, quizArtifactId: string): string {
  if (isCourseSegment(notebookId)) {
    const slug = notebookId.slice(COURSE_NB_PREFIX.length);
    return `/courses/${encodeURIComponent(slug)}/quiz?path=${encodeURIComponent(quizArtifactId)}`;
  }
  return `/topics/${encodeURIComponent(notebookId)}/quiz/${encodeURIComponent(quizArtifactId)}`;
}

// A short human line describing the planned session, e.g. "~12 min · 18 questions across 4 areas".
// "areas" (not "topics") because a segment can be a course quiz as well as a notebook topic.
export function planSummary(plan: StudyPlanResponse): string {
  if (plan.total_items === 0) return "Nothing to review right now.";
  const areas = new Set(plan.segments.map((s) => s.notebook_id)).size;
  const mins = `~${Math.round(plan.total_minutes)} min`;
  const qs = `${plan.total_items} ${plan.total_items === 1 ? "question" : "questions"}`;
  const as = `${areas} ${areas === 1 ? "area" : "areas"}`;
  return `${mins} · ${qs} across ${as}`;
}

// "3 due · 5 questions" sub-line for one segment.
export function segmentSummary(seg: StudyPlanSegment): string {
  const due = seg.due_count > 0 ? `${seg.due_count} due` : "getting ahead";
  const qs = `${seg.item_count} ${seg.item_count === 1 ? "question" : "questions"}`;
  return `${due} · ${qs} · ~${Math.round(seg.minutes)} min`;
}

// -- M8 #12 Continue lane -------------------------------------------------------

// One glyph per path-step kind (the design's step vocabulary), for the Continue-lane next-step line.
const STEP_KIND_ICON: Record<string, string> = {
  intro: "🧭",
  audio: "🎧",
  read: "📖",
  flashcards: "🃏",
  quiz: "❓",
  bridge: "✨",
  reflect: "✍️",
  recap: "🔁",
};

export function stepKindIcon(kind: string): string {
  return STEP_KIND_ICON[kind] ?? "•";
}

// "3 of 9 · 33%" coverage line for a Continue-lane card.
export function pathProgressSummary(p: PathSummary): string {
  return `${p.completed_steps} of ${p.step_count} · ${p.progress_pct}%`;
}
