// A tiny dependency-free trend line. Draws a 0–100 series as an inline SVG polyline + soft
// area fill, scaled to the box. One point renders as a single dot. Keeps the frontend's "no
// chart library" footprint (SPEC named Recharts "or similar" — this is the "similar").

type Props = {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
};

export function Sparkline({ values, width = 120, height = 36, className }: Props) {
  const pad = 3;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const max = 100; // values are already 0–100 percentages
  const n = values.length;

  const x = (i: number) => (n <= 1 ? pad + w / 2 : pad + (i / (n - 1)) * w);
  const y = (v: number) => pad + h - (Math.max(0, Math.min(max, v)) / max) * h;

  if (n === 0) return null;

  if (n === 1) {
    return (
      <svg width={width} height={height} className={className} aria-hidden="true">
        <circle cx={x(0)} cy={y(values[0])} r={3} className="fill-accent" />
      </svg>
    );
  }

  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `${pad},${pad + h} ${line} ${pad + w},${pad + h}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden="true"
    >
      <polygon points={area} className="fill-accent/10" />
      <polyline
        points={line}
        fill="none"
        className="stroke-accent"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={x(n - 1)} cy={y(values[n - 1])} r={2.5} className="fill-accent" />
    </svg>
  );
}
