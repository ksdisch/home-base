import { useCallback, useEffect, useRef, useState } from "react";

// FR10 (docs/ideas/destructive-tap-undo.md): the three thumb-reach destructive taps —
// News "Not interested", note Delete on /notes, and the inline ✕ on Today — used to
// commit the instant they were touched. This is the one shared hold-then-fire
// primitive: the UI change stays optimistic (the thing vanishes now), but the mutation
// waits UNDO_WINDOW_MS behind an Undo toast. Undo restores the UI and the API is never
// called; the timeout, a second destructive tap, or leaving the page commits. Purely
// client-side — no queue, no tombstones, no change to what the mutation does.

export const UNDO_WINDOW_MS = 5000;

type Pending = {
  label: string;
  commit: () => void;
  rollback: () => void;
  timer: ReturnType<typeof setTimeout>;
};

export function useUndoable() {
  const [label, setLabel] = useState<string | null>(null);
  const pending = useRef<Pending | null>(null);

  const settle = useCallback((how: "commit" | "rollback") => {
    const p = pending.current;
    if (!p) return;
    clearTimeout(p.timer);
    pending.current = null;
    setLabel(null);
    (how === "commit" ? p.commit : p.rollback)();
  }, []);

  const fire = useCallback(
    (nextLabel: string, commit: () => void, rollback: () => void) => {
      settle("commit"); // a second destructive tap commits the held one immediately
      const timer = setTimeout(() => settle("commit"), UNDO_WINDOW_MS);
      pending.current = { label: nextLabel, commit, rollback, timer };
      setLabel(nextLabel);
    },
    [settle],
  );

  const undo = useCallback(() => settle("rollback"), [settle]);

  // Leaving the page commits the held action — the grace window must never LOSE a tap.
  useEffect(() => () => settle("commit"), [settle]);

  return { label, fire, undo };
}

export function UndoToast({ label, onUndo }: { label: string | null; onUndo: () => void }) {
  if (!label) return null;
  return (
    <div
      role="status"
      className="fixed bottom-20 left-1/2 z-50 flex -translate-x-1/2 items-center gap-4 rounded-full bg-ink px-4 py-2.5 text-sm text-white shadow-lg sm:bottom-6"
    >
      <span>{label}</span>
      <button onClick={onUndo} className="font-semibold underline underline-offset-2">
        Undo
      </button>
    </div>
  );
}
