import { describe, expect, it } from "vitest";
import { parseTimestamp, shortDate } from "./format";

describe("parseTimestamp", () => {
  it("reads a zone-less SQLite datetime as UTC, not local time", () => {
    // The backend stores naive-UTC `datetime('now')` strings (no zone designator). They must be
    // read as that UTC instant — otherwise dates drift off-by-one in non-UTC zones (e.g. Central).
    // Epoch ms is absolute, so this assertion holds in any test-runner timezone.
    expect(parseTimestamp("2026-06-26 02:00:00").getTime()).toBe(Date.UTC(2026, 5, 26, 2, 0, 0));
  });

  it("renders a date-only calendar label literally, with no zone shift", () => {
    // `activity.day` / `last_activity` come from `date('now')` — calendar labels, not instants. They
    // must show that exact day everywhere, so they parse to *local* midnight (not UTC midnight, which
    // would render as the previous day in a behind-UTC zone). Local getters are timezone-stable.
    const d = parseTimestamp("2026-06-26");
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 5, 26]);
  });

  it("honors an explicit UTC offset without double-shifting", () => {
    // *Response.generated_at carries an offset (+00:00); a trailing Z is equivalent. Trust it as-is.
    expect(parseTimestamp("2026-06-26T02:00:00+00:00").getTime()).toBe(Date.UTC(2026, 5, 26, 2, 0, 0));
    expect(parseTimestamp("2026-06-26T02:00:00Z").getTime()).toBe(Date.UTC(2026, 5, 26, 2, 0, 0));
  });
});

describe("shortDate", () => {
  it("falls back to an em dash for empty or unparseable input", () => {
    expect(shortDate(null)).toBe("—");
    expect(shortDate(undefined)).toBe("—");
    expect(shortDate("not a date")).toBe("—");
  });
});
