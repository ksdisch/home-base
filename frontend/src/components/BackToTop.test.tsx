import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BackToTop } from "./BackToTop";

function setScrollY(y: number) {
  Object.defineProperty(window, "scrollY", { value: y, writable: true, configurable: true });
}

beforeEach(() => {
  setScrollY(0);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
});
afterEach(() => {
  setScrollY(0);
});

describe("BackToTop — thumb-zone escape from a long feed", () => {
  it("stays hidden near the top of the feed", () => {
    render(<BackToTop showAfterPx={400} />);
    const btn = screen.getByRole("button", { hidden: true }); // aria-hidden near top => name resolves empty
    expect(btn.className).toContain("opacity-0");
    expect(btn.className).toContain("pointer-events-none");
  });

  it("appears once scrolled past the threshold", () => {
    render(<BackToTop showAfterPx={400} />);
    setScrollY(500);
    fireEvent.scroll(window);
    const btn = screen.getByRole("button", { name: /back to top/i });
    expect(btn.className).toContain("opacity-100");
    expect(btn.className).not.toContain("pointer-events-none");
  });

  it("has a >=44px thumb target", () => {
    render(<BackToTop showAfterPx={400} />);
    const btn = screen.getByRole("button", { hidden: true }); // aria-hidden near top => name resolves empty
    // h-11 / w-11 == 44px (Tailwind 11 = 2.75rem)
    expect(btn.className).toContain("h-11");
    expect(btn.className).toContain("w-11");
  });

  it("scrolls back to the top on tap", () => {
    render(<BackToTop showAfterPx={400} />);
    setScrollY(500);
    fireEvent.scroll(window);
    fireEvent.click(screen.getByRole("button", { name: /back to top/i }));
    expect(window.scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }));
  });
});
