import { useState } from "react";
import { getStoredTheme, nextTheme, setTheme, type Theme } from "../lib/theme";

const LABEL: Record<Theme, string> = { light: "Light", dark: "Dark", system: "System" };
const GLYPH: Record<Theme, string> = { light: "☀", dark: "☾", system: "◐" };

// ③ Dusk toggle — cycles the theme override light → dark → system (follow the OS). "system" is
// the honest default; the glyph shows the current choice. The initial paint is already set by
// the inline script in index.html, so this never flashes.
export function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme);
  const cycle = () => {
    const next = nextTheme(theme);
    setTheme(next);
    setThemeState(next);
  };
  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={`Theme: ${LABEL[theme]}. Tap to change.`}
      title={`Theme: ${LABEL[theme]}`}
      className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition hover:text-ink"
    >
      <span aria-hidden="true" className="text-base leading-none">
        {GLYPH[theme]}
      </span>
    </button>
  );
}
