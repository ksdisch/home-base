import { cx } from "../lib/format";

export function Badge({
  children,
  tone = "neutral",
  title,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "accent" | "amber" | "stone";
  title?: string;
}) {
  const tones = {
    neutral: "bg-stone-100 text-muted",
    accent: "bg-accent-soft text-accent",
    amber: "bg-amber-100 text-amber-800",
    stone: "bg-stone-200 text-ink/70",
  } as const;
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
