import type { NotebookCard } from "../api/types";

const TYPE_LABELS: Record<string, string> = {
  audio: "audio",
  quizzes: "quizzes",
  study_guides: "study guides",
  report: "reports",
  flashcards: "flashcards",
  mind_map: "mind maps",
  slide_deck: "slide decks",
  infographic: "infographics",
  video: "videos",
  data_table: "data tables",
};

// Build a short, human "12 audio · 10 quizzes" summary from the counts map.
export function countSummary(card: NotebookCard): string {
  const order = ["audio", "quizzes", "study_guides", "flashcards"];
  const parts: string[] = [];
  for (const key of order) {
    const n = card.counts[key];
    if (n) parts.push(`${n} ${TYPE_LABELS[key] ?? key}`);
  }
  if (parts.length === 0) {
    const total = card.counts.total ?? 0;
    return total ? `${total} artifacts` : "no artifacts yet";
  }
  return parts.join(" · ");
}

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// "Jun 6" style short date from an ISO timestamp/date. Empty input → "—".
export function shortDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
