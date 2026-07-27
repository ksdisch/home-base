import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BriefRunDay, BriefRunsSummaryResponse } from "../api/types";

// "Jul 25" from a YYYY-MM-DD (parsed as local, like the other Today strips).
function humanDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// Whole minutes of wall time the day's sweep took. Sub-minute rounds up to 1 rather than
// reading "0 min" — the sweep did run.
export function humanMinutes(ms: number): string {
  return `${Math.max(1, Math.round(ms / 60_000))} min`;
}

export function humanCost(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

// The ops line on Today (docs/ideas/sweep-ledger-readout.md). sweeps/envelope.py has logged
// every topic run's cost/duration/error to data/sweeps/.runs.jsonl since M3 and nothing ever
// totaled it, so a silently-degraded or expensive sweep was grep-only on the Mac.
//
// Same contract as HabitStrip and YourLearning: renders nothing while loading, on a fetch
// error, or on an empty ledger — the readout may never block or clutter the morning read.
export function SweepLedgerStrip() {
  const [summary, setSummary] = useState<BriefRunsSummaryResponse | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .briefRunsSummary()
      .then((r) => alive && setSummary(r))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const latest = summary?.latest;
  if (!latest) return null;

  // Only claim "this morning" when the newest day that actually RAN is today. When the 06:00
  // sweep hasn't landed (or failed), the line names the day it is really reporting — the
  // alternative is a stale total wearing today's label, which is the exact dishonesty this
  // readout exists to remove.
  const isToday = latest.date === todayIso();
  const when = isToday ? "This morning" : humanDay(latest.date);

  // Days worth a second look: never swept at all, or ran far under the window's norm. Both
  // shapes are live in the ledger right now (a missing 07-24; $1-2 on 07-23/07-25 against a
  // ~$10 norm), and neither is visible to a "did it run?" check alone.
  const days = summary?.days ?? [];
  const missing = days.filter((d) => !d.ran);
  const thin = days.filter((d) => d.thin);
  const window = summary?.window_days ?? days.length;

  return (
    <section className="mt-3 border-t border-line pt-3">
      <p data-testid="sweep-ledger-line" className="text-xs text-muted">
        {when}: {latest.topics} {latest.topics === 1 ? "topic" : "topics"} ·{" "}
        {humanMinutes(latest.duration_ms)} · {humanCost(latest.cost_usd)} ·{" "}
        <span className={latest.errors > 0 ? "text-amber-700" : undefined}>
          {latest.errors} {latest.errors === 1 ? "error" : "errors"}
        </span>
      </p>
      <p data-testid="sweep-ledger-rollup" className="mt-1 text-xs text-muted">
        Last {window} days: {humanCost(summary?.cost_usd ?? 0)} · {summary?.errors ?? 0}{" "}
        {(summary?.errors ?? 0) === 1 ? "error" : "errors"}
        {missing.length > 0 && (
          <span className="text-amber-700" title="No rows in the sweep ledger for these days">
            {" · "}
            no sweep: {missing.map((d) => humanDay(d.date)).join(", ")}
          </span>
        )}
        {thin.length > 0 && (
          <span
            className="text-amber-700"
            title="Ran, but cost far under this window's median — usually a thin or half-failed sweep"
          >
            {" · "}
            thin: {thin.map((d: BriefRunDay) => humanDay(d.date)).join(", ")}
          </span>
        )}
      </p>
    </section>
  );
}
