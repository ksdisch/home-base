/** @type {import('tailwindcss').Config} */

// ② A color system, not a color. Colors live as CSS variables (space-separated RGB channels
// defined in src/index.css) so the whole palette can be re-themed at the :root level — the
// substrate Dusk mode reuses. The `<alpha-value>` placeholder keeps every opacity modifier
// (accent/40, ink/90, border-accent/30, …) working through the variable indirection.
const withVar = (v) => `rgb(var(${v}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Calm, warm-neutral palette with a muted teal accent.
        bg: withVar("--color-bg"),
        card: withVar("--color-card"),
        ink: withVar("--color-ink"),
        muted: withVar("--color-muted"),
        accent: {
          DEFAULT: withVar("--color-accent"),
          soft: withVar("--color-accent-soft"),
        },
        // ③ Surface hairlines — exact stone values in light, warm charcoal in dusk.
        line: {
          DEFAULT: withVar("--color-line"),
          soft: withVar("--color-line-soft"),
          strong: withVar("--color-line-strong"),
        },
        // Semantic tints — one honest vocabulary for meaning, all inside the teal's
        // low-saturation envelope so nothing out-shouts the accent.
        success: withVar("--color-success"),
        info: withVar("--color-info"),
        warn: withVar("--color-warn"),
        danger: withVar("--color-danger"),
        // Deterministic per-source ramp (see src/lib/sourceTint.ts) — desaturated hues so a
        // News source reads as itself at a glance.
        source: {
          0: withVar("--color-source-0"),
          1: withVar("--color-source-1"),
          2: withVar("--color-source-2"),
          3: withVar("--color-source-3"),
          4: withVar("--color-source-4"),
          5: withVar("--color-source-5"),
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)",
        cardHover: "0 4px 12px rgba(16,24,40,0.10)",
      },
    },
  },
  plugins: [],
};
