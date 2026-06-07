import type { StudyPlanResponse, StudyPlanSegment } from "../api/types";

// The minute budgets the Study Plan page offers.
export const PLAN_MINUTES = [10, 20, 30, 45] as const;

// The deep link to retake a quiz, matching the TopicDetail / QuizPlayer route.
export function quizPlayerPath(notebookId: string, quizArtifactId: string): string {
  return `/topics/${encodeURIComponent(notebookId)}/quiz/${encodeURIComponent(quizArtifactId)}`;
}

// A short human line describing the planned session, e.g. "~12 min · 18 questions across 4 topics".
export function planSummary(plan: StudyPlanResponse): string {
  if (plan.total_items === 0) return "Nothing to review right now.";
  const topics = new Set(plan.segments.map((s) => s.notebook_id)).size;
  const mins = `~${Math.round(plan.total_minutes)} min`;
  const qs = `${plan.total_items} ${plan.total_items === 1 ? "question" : "questions"}`;
  const ts = `${topics} ${topics === 1 ? "topic" : "topics"}`;
  return `${mins} · ${qs} across ${ts}`;
}

// "3 due · 5 questions" sub-line for one segment.
export function segmentSummary(seg: StudyPlanSegment): string {
  const due = seg.due_count > 0 ? `${seg.due_count} due` : "getting ahead";
  const qs = `${seg.item_count} ${seg.item_count === 1 ? "question" : "questions"}`;
  return `${due} · ${qs} · ~${Math.round(seg.minutes)} min`;
}
