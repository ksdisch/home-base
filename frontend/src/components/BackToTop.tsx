import { useEffect, useState } from "react";

const SHOW_AFTER_PX = 400;

// F4 · Stranded at the bottom of the feed — a thumb-zone escape from a long one-handed News
// scroll. Fades in past ~400px, scrolls to the top (smooth, or instant under reduced-motion),
// and fades back out near the top. Pinned in the thumb zone above the mobile tab bar; no API,
// no shared state.
export function BackToTop({ showAfterPx = SHOW_AFTER_PX }: { showAfterPx?: number }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > showAfterPx);
    onScroll(); // sync to the current position on mount
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [showAfterPx]);

  const toTop = () => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };

  return (
    <button
      type="button"
      aria-label="Back to top"
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
      onClick={toTop}
      className={`fixed bottom-20 right-4 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-line bg-card/90 text-accent shadow-md backdrop-blur transition-opacity duration-200 hover:bg-card motion-reduce:transition-none sm:bottom-6 ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
    >
      <span aria-hidden="true" className="text-lg leading-none">
        ↑
      </span>
    </button>
  );
}
