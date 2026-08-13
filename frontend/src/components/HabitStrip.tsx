import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BriefHabitResponse } from "../api/types";

// The kickoff's v1 targets, as UI copy: ≥5 mornings/week on the visit log, ≥3 notes/week.
const MORNINGS_TARGET = 5;
const NOTES_TARGET = 3;

// PR5 sweep-trust gauge: past this many days since the last manual accuracy re-grade
// (docs/sweep-trust-log.md), the strip flags "re-grade due" instead of quietly aging.
const REGRADE_DUE_DAYS = 30;

// v14 visit-source attribution: the raw morning count can't tell a Tuesday read from a
// localhost dev load, so the phone-sourced count rides beside it. A week whose visits all
// predate attribution has nothing to report, so the number is withheld rather than shown
// as 0 — the caveat this tooltip used to carry is now enforced instead of explained.
const PHONE_TITLE =
  "Distinct days a tailnet (phone) client opened Today — the reading-habit number, " +
  "reported beside the raw count. Weeks whose visits predate attribution (before " +
  "2026-07-27) show no phone number at all rather than a 0 nothing measured.";

// ④ Milestones the strip finally notices — round lifetime-mornings thresholds worth a nod,
// acknowledged once per crossing via localStorage so the ledger never nags.
const MORNING_MILESTONES = [25, 50, 100, 200, 365];
const MILESTONE_KEY = "homebase.habit.morningsMilestone";

type Week = BriefHabitResponse["weeks"][number];

// Lifetime mornings the visit log has recorded.
export function totalMornings(weeks: Week[]): number {
  return weeks.reduce((sum, w) => sum + w.mornings, 0);
}

// Length of the trailing run of on-target weeks (≥ the mornings target), newest-first. A
// below-target current week breaks the run, so mid-week it reads 0 until the week is re-earned
// — the streak is never claimed prematurely.
export function consecutiveOnTarget(weeks: Week[]): number {
  let n = 0;
  for (let i = weeks.length - 1; i >= 0; i--) {
    if (weeks[i].mornings >= MORNINGS_TARGET) n++;
    else break;
  }
  return n;
}

// A personal-best week needs ≥2 prior weeks that actually logged mornings and a strict
// improvement over all of them — so it never fires on the second week ever, or on a tie.
export function isBestWeek(weeks: Week[]): boolean {
  if (weeks.length < 3) return false;
  const current = weeks[weeks.length - 1];
  const priorMornings = weeks
    .slice(0, -1)
    .map((w) => w.mornings)
    .filter((m) => m > 0);
  if (priorMornings.length < 2) return false;
  return current.mornings > Math.max(...priorMornings);
}

// The largest round lifetime-mornings threshold crossed (0 when none yet).
export function highestMorningMilestone(total: number): number {
  let hit = 0;
  for (const m of MORNING_MILESTONES) if (total >= m) hit = m;
  return hit;
}

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
  // Highest lifetime-mornings milestone already celebrated on this device — read once so a
  // crossed milestone shows for the whole session but never re-fires on a later load.
  const [celebratedMilestone] = useState<number>(() => {
    try {
      return Number(localStorage.getItem(MILESTONE_KEY)) || 0;
    } catch {
      return 0;
    }
  });

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

  // Persist a newly-crossed lifetime milestone so it's acknowledged exactly once per crossing,
  // without updating the in-session flag (so it stays visible until the next load).
  useEffect(() => {
    const w = habit?.weeks;
    if (!w) return;
    const milestone = highestMorningMilestone(totalMornings(w));
    if (milestone > celebratedMilestone) {
      try {
        localStorage.setItem(MILESTONE_KEY, String(milestone));
      } catch {
        /* localStorage unavailable — the marker simply re-appears next load */
      }
    }
  }, [habit, celebratedMilestone]);

  const weeks = habit?.weeks;
  if (!weeks || weeks.length === 0) return null;
  if (weeks.every((w) => w.mornings === 0 && w.notes === 0)) return null;

  const current = weeks[weeks.length - 1];
  const previous = weeks.slice(0, -1).filter((w) => w.mornings > 0 || w.notes > 0);

  // ④ Earned markers, each bound to a verified threshold. At most the target-hit ✓ plus one
  // suffix, so the strip stays a calm ledger — not a scoreboard. Suffix precedence: a crossed
  // lifetime milestone > an active streak > a personal-best week.
  const targetHit = current.mornings >= MORNINGS_TARGET;
  const streak = consecutiveOnTarget(weeks);
  const milestone = highestMorningMilestone(totalMornings(weeks));
  const showLifetime = milestone > celebratedMilestone;
  let marker: string | null = null;
  if (showLifetime) marker = `☀ ${milestone} mornings`;
  else if (streak >= 2) marker = `${streak} weeks running`;
  else if (isBestWeek(weeks)) marker = "best week yet";

  const lastGraded = habit?.last_graded ?? null;
  const gradedDaysAgo = lastGraded ? daysSince(lastGraded) : null;
  const regradeDue = gradedDaysAgo !== null && gradedDaysAgo > REGRADE_DUE_DAYS;

  return (
    <section className="mt-4 rounded-2xl border border-line bg-card/60 px-5 py-3">
      <p className="text-sm text-ink/90">
        <span className="font-semibold">Habit check:</span>{" "}
        <span
          className={targetHit ? "text-accent font-medium" : undefined}
          title={`v1 target: ≥${MORNINGS_TARGET} mornings/week (distinct days you opened Today)`}
        >
          {current.mornings} of {MORNINGS_TARGET} mornings{targetHit ? " ✓" : ""}
        </span>
        {/* v14 (docs/ideas/builder-vs-reader-metric.md): the phone-sourced number rides
            BESIDE the raw one — the criterion above is unchanged. Rendered at 0 when the
            week IS attributed: hiding a measured zero would hide exactly the signal this
            exists to catch (the reading habit fading while dev traffic props up the raw
            count). Gated on `attributed` so an unmeasurable zero is withheld instead —
            "(0 on phone)" for a week of pre-v14 rows is an accusation, not a reading.
            Absent on those payloads too, which is the same answer for the same reason. */}
        {current.attributed && current.mornings_phone !== undefined && (
          <span
            className="text-muted"
            title={PHONE_TITLE}
          >
            {" "}
            ({current.mornings_phone} on phone)
          </span>
        )}
        {" · "}
        <span title={`v1 target: ≥${NOTES_TARGET} notes attached/week`}>
          {current.notes} of {NOTES_TARGET} notes
        </span>{" "}
        this week
        {marker && <span className="text-accent"> · {marker}</span>}
      </p>
      {previous.length > 0 && (
        <p className="mt-1 text-xs text-muted">
          {previous.map((w, i) => (
            <span key={w.week_start} title={PHONE_TITLE}>
              {i > 0 && " · "}
              week of {humanWeek(w.week_start)}: {w.mornings}m
              {w.attributed && w.mornings_phone !== undefined && ` / ${w.mornings_phone}p`} /{" "}
              {w.notes}n
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
