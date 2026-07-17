import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BriefHabitWeek } from "../api/types";

// The kickoff's v1 targets, as UI copy: ≥5 mornings/week on the visit log, ≥3 notes/week.
const MORNINGS_TARGET = 5;
const NOTES_TARGET = 3;

// "Jun 29" from a YYYY-MM-DD Monday (parsed as local, like the Brief page's date helpers).
function humanWeek(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Habit strip on Today — the read surface for the kickoff's ~3-weeks-in success check
// (mornings/week + notes/week), so the evaluation is a glance here instead of a sqlite
// dig. Same contract as YourLearning: renders nothing while loading, on fetch errors,
// or before there's any signal at all — it must never clutter the morning read.
export function HabitStrip() {
  const [weeks, setWeeks] = useState<BriefHabitWeek[] | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .briefHabit()
      .then((r) => alive && setWeeks(r.weeks))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!weeks || weeks.length === 0) return null;
  if (weeks.every((w) => w.mornings === 0 && w.notes === 0)) return null;

  const current = weeks[weeks.length - 1];
  const previous = weeks.slice(0, -1).filter((w) => w.mornings > 0 || w.notes > 0);

  return (
    <section className="mt-4 rounded-2xl border border-stone-200 bg-white/60 px-5 py-3">
      <p className="text-sm text-ink/90">
        <span className="font-semibold">Habit check:</span>{" "}
        <span title={`v1 target: ≥${MORNINGS_TARGET} mornings/week (distinct days you opened Today)`}>
          {current.mornings} of {MORNINGS_TARGET} mornings
        </span>
        {" · "}
        <span title={`v1 target: ≥${NOTES_TARGET} notes attached/week`}>
          {current.notes} of {NOTES_TARGET} notes
        </span>{" "}
        this week
      </p>
      {previous.length > 0 && (
        <p className="mt-1 text-xs text-muted">
          {previous.map((w, i) => (
            <span key={w.week_start}>
              {i > 0 && " · "}
              week of {humanWeek(w.week_start)}: {w.mornings}m / {w.notes}n
            </span>
          ))}
        </p>
      )}
    </section>
  );
}
