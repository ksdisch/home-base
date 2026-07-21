import { cx } from "../lib/format";

// Mastery (estimated current retention) as a 0–1 fraction → a calm band + tone.
// Mirrors the backend's 0.5 due threshold: below it reads "fading".
export function masteryTone(mastery: number): "accent" | "amber" | "stone" {
  if (mastery >= 0.75) return "accent";
  if (mastery >= 0.5) return "amber";
  return "stone";
}

export function masteryLabel(mastery: number): string {
  if (mastery >= 0.75) return "strong";
  if (mastery >= 0.5) return "fading";
  return "shaky";
}

// A tiny inline retention bar — no deps, fits the minimalist grain (like Sparkline).
export function MasteryBar({
  mastery,
  className,
}: {
  mastery: number;
  className?: string;
}) {
  const pct = Math.round(Math.min(1, Math.max(0, mastery)) * 100);
  const fill = {
    accent: "bg-accent",
    amber: "bg-amber-400",
    stone: "bg-line-strong",
  }[masteryTone(mastery)];
  return (
    <div
      className={cx("h-1.5 w-full overflow-hidden rounded-full bg-line-soft", className)}
      role="img"
      aria-label={`Mastery ${pct}%`}
      title={`Estimated retention ~${pct}% (${masteryLabel(mastery)})`}
    >
      <div className={cx("h-full rounded-full transition-all", fill)} style={{ width: `${pct}%` }} />
    </div>
  );
}
