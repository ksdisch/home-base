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

// Parse a backend timestamp into a Date, honoring how the API actually encodes them:
//   • zone-less datetimes ("2026-06-26 20:00:27") are naive-UTC SQLite `datetime('now')` strings —
//     read them as the UTC instant, else they drift off-by-one in non-UTC zones (e.g. Central);
//   • date-only values ("2026-06-26") are `date('now')` calendar labels, not instants — parse them
//     to *local* midnight so they render as that literal day (UTC midnight shows the day before);
//   • already-zoned values (Z or ±hh:mm, e.g. *Response.generated_at) are trusted as written.
export function parseTimestamp(iso: string): Date {
  if (!iso.includes(":")) {
    // Date-only calendar label → local midnight, rendered literally with no zone shift.
    return new Date(`${iso}T00:00:00`);
  }
  const isZoned = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso);
  const normalized = iso.replace(" ", "T");
  return new Date(isZoned ? normalized : `${normalized}Z`);
}

// "Jun 6" style short date from a backend timestamp/date. Empty/unparseable input → "—".
export function shortDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = parseTimestamp(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
