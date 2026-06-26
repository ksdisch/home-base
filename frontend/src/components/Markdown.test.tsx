import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders an unterminated code fence instead of dropping it and everything after", () => {
    // A fence opened but never closed must not silently swallow its content (and the rest of the doc).
    const src = "Intro paragraph.\n\n```\nconst x = 1;\nstill inside the fence";
    const { container } = render(<Markdown source={src} />);

    expect(container.textContent).toContain("Intro paragraph."); // before the fence still renders
    expect(container.textContent).toContain("const x = 1;"); // unterminated block content kept
    expect(container.textContent).toContain("still inside the fence");
    expect(container.querySelector("pre")).not.toBeNull(); // rendered as a code block
  });

  it("still renders a normal terminated code fence", () => {
    const src = "```\ncode here\n```";
    const { container } = render(<Markdown source={src} />);
    expect(container.querySelector("pre")?.textContent).toContain("code here");
  });
});
