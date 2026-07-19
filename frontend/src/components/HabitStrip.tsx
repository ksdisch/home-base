import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BriefHabitResponse } from "../api/types";

// The kickoff's v1 targets, as UI copy: ≥5 mornings/week on the visit log, ≥3 notes/week.
const MORNINGS_TARGET = 5;
const NOTES_TARGET = 3;

// PR5 sweep-trust gauge: past this many days since the last manual accuracy re-grade
// (docs/sweep-trust-log.md), the strip flags "re-grade due" instead of quietly aging.
const REGRADE_DUE_DAYS = 30;

// "Jun 29" from a YYYY-MM-DD Monday (parsed as local, like the Brief page's date helpers).
function humanWeek(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Whole local days since a YYYY-MM-DD date (never negative — a future date reads as 0).
function daysSince(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((now.getTime() - new Date(y, m - 1, d).getTime()) / 86_400_000));
}

// Habit strip on Today — the read surface for the kickoff's ~3-weeks-in success check
// (mornings/week + notes/week), so the evaluation is a glance here instead of a sqlite
// dig. Same contract as YourLearning: renders nothing while loading, on fetch errors,
// or before there's any signal at all — it must never clutter the morning read.
export function HabitStrip() {
  const [habit, setHabit] = useState<BriefHabitResponse | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .briefHabit()
      .then((r) => alive && setHabit(r))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const weeks = habit?.weeks;
  if (!weeks || weeks.length === 0) return null;
  if (weeks.every((w) => w.mornings === 0 && w.notes === 0)) return null;

  const current = weeks[weeks.length - 1];
  const previous = weeks.slice(0, -1).filter((w) => w.mornings > 0 || w.notes > 0);

  const lastGraded = habit?.last_graded ?? null;
  const gradedDaysAgo = lastGraded ? daysSince(lastGraded) : null;
  const regradeDue = gradedDaysAgo !== null && gradedDaysAgo > REGRADE_DUE_DAYS;

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
      {/* PR5: trust is measured, not assumed — the last manual accuracy re-grade rides
          the habit numbers, and its absence is rendered loudly instead of hidden. */}
      <p
        className={`mt-1 text-xs ${lastGraded && !regradeDue ? "text-muted" : "text-amber-700"}`}
        title="Monthly manual re-grade against the M0 rubric — append a dated entry to docs/sweep-trust-log.md"
      >
        Sweep trust:{" "}
        {lastGraded
          ? `last accuracy-graded ${humanWeek(lastGraded)} (${gradedDaysAgo}d ago)` +
            (regradeDue ? " — re-grade due" : "")
          : "no accuracy grade on record — see docs/sweep-trust-log.md"}
      </p>
    </section>
  );
}
