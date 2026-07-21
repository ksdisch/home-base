import { cx } from "../lib/format";

type Tone = "warning" | "info" | "muted";

const TONES: Record<Tone, string> = {
  warning: "bg-amber-50 border-amber-200 text-amber-900",
  info: "bg-accent-soft border-accent/30 text-accent border-l-2 border-l-accent/40 pl-3",
  muted: "bg-line-soft border-line text-muted border-l-2 border-l-accent/40 pl-3",
};

export function Banner({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cx("rounded-xl border px-4 py-3 text-sm", TONES[tone])} role="status">
      {title && <p className="font-medium">{title}</p>}
      <div className={title ? "mt-0.5" : ""}>{children}</div>
    </div>
  );
}
