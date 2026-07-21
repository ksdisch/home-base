import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Banner } from "./Banner";

describe("Banner", () => {
  // The calm honesty tones speak in the app's own margin — a thin accent left rule —
  // so "Still learning you" / "Nothing here right now" read as a companion, not a system alert.
  it("gives the calm info tone an accent left rule (the companion voice)", () => {
    const { getByRole } = render(<Banner tone="info">Still learning you</Banner>);
    const cls = getByRole("status").className;
    expect(cls).toContain("border-l-2");
    expect(cls).toContain("border-l-accent/40");
    expect(cls).toContain("pl-3");
  });

  it("gives the calm muted tone the same accent left rule", () => {
    const { getByRole } = render(<Banner tone="muted">Nothing here right now</Banner>);
    const cls = getByRole("status").className;
    expect(cls).toContain("border-l-2");
    expect(cls).toContain("border-l-accent/40");
    expect(cls).toContain("pl-3");
  });

  // Honesty about *failure* must stay loud: the warning tone keeps its full-fill amber alarm
  // and does NOT get the softer companion margin.
  it("leaves the warning tone a loud full-fill amber alarm (no companion left rule)", () => {
    const { getByRole } = render(<Banner tone="warning">Sweep failed</Banner>);
    const cls = getByRole("status").className;
    expect(cls).not.toContain("border-l-2");
    expect(cls).not.toContain("border-l-accent/40");
    expect(cls).toContain("border-amber-200");
  });
});
