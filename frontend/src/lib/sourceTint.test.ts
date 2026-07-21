import { describe, expect, it } from "vitest";
import { sourceTint } from "./sourceTint";

describe("sourceTint — a deterministic per-source tint", () => {
  it("returns a valid text-source-N class", () => {
    expect(sourceTint("Reuters")).toMatch(/^text-source-[0-5]$/);
  });

  it("is stable for the same source name across calls", () => {
    expect(sourceTint("The Verge")).toBe(sourceTint("The Verge"));
    expect(sourceTint("AP News")).toBe(sourceTint("AP News"));
  });

  it("spreads a set of sources across more than one tint (provenance you can feel)", () => {
    const names = ["Reuters", "The Verge", "AP News", "Patch", "Wire", "Blog", "BBC", "NPR"];
    const distinct = new Set(names.map(sourceTint));
    expect(distinct.size).toBeGreaterThan(1);
  });

  it("handles an empty source without throwing", () => {
    expect(sourceTint("")).toMatch(/^text-source-[0-5]$/);
  });
});
