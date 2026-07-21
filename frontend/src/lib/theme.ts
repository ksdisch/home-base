// ③ Dusk mode — the theme store. Auto by default (follow the OS via prefers-color-scheme),
// with a persisted per-device override. "system" clears the data-theme attribute so the media
// query decides; "light"/"dark" pin data-theme on <html> to force the scheme regardless of OS.
export type Theme = "light" | "dark" | "system";

const KEY = "homebase.theme";
const CYCLE: Theme[] = ["light", "dark", "system"];

export function getStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" || v === "system" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* localStorage unavailable — the choice just won't persist across loads */
  }
  applyTheme(theme);
}

export function nextTheme(current: Theme): Theme {
  return CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length];
}
