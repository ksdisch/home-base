/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Calm, warm-neutral palette with a muted teal accent.
        ink: "#1f2733",
        muted: "#6b7686",
        accent: {
          DEFAULT: "#3f8f86",
          soft: "#e6f0ee",
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
