import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyTheme, getStoredTheme, nextTheme, setTheme } from "./theme";

const KEY = "homebase.theme";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});
afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
});

describe("theme store — auto by default, with a persisted override", () => {
  it("defaults to system when nothing is stored", () => {
    expect(getStoredTheme()).toBe("system");
  });

  it("reads a stored override", () => {
    localStorage.setItem(KEY, "dark");
    expect(getStoredTheme()).toBe("dark");
  });

  it("falls back to system on a garbage value", () => {
    localStorage.setItem(KEY, "chartreuse");
    expect(getStoredTheme()).toBe("system");
  });

  it("cycles light -> dark -> system -> light", () => {
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("system");
    expect(nextTheme("system")).toBe("light");
  });

  it("applyTheme sets data-theme for an explicit choice and clears it for system (media query decides)", () => {
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    applyTheme("system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("setTheme persists the choice and applies it", () => {
    setTheme("dark");
    expect(localStorage.getItem(KEY)).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
