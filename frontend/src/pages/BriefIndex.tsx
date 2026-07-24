import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { BriefArchiveEntry } from "../api/types";
import { humanDate } from "./Brief";

function localToday(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function monthLabel(iso: string): string {
  const [y, m] = iso.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export default function BriefIndex() {
  const [entries, setEntries] = useState<BriefArchiveEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const today = localToday();

  useEffect(() => {
    api
      .briefArchive()
      .then((r) => setEntries(r.dates))
      .catch((e) => setError(e.message ?? "Couldn't load the archive"));
  }, []);

  // Group newest-first entries by "Month YYYY".
  const groups: { label: string; items: BriefArchiveEntry[] }[] = [];
  for (const entry of entries ?? []) {
    const label = monthLabel(entry.date);
    const last = groups[groups.length - 1];
    if (last && last.label === label) {
      last.items.push(entry);
    } else {
      groups.push({ label, items: [entry] });
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Brief archive</h1>
        <p className="mt-1 text-sm text-muted">Every morning sweep, newest first.</p>
        <p className="mt-2 text-sm">
          <Link to="/" className="text-accent hover:underline">
            ← Today
          </Link>
        </p>
      </div>

      {error && (
        <p className="text-sm text-warning">{error}</p>
      )}

      {entries === null && !error && (
        <p className="text-sm text-muted">Loading…</p>
      )}

      {groups.map((group) => (
        <div key={group.label} className="mb-6">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            {group.label}
          </h2>
          <ul className="space-y-1">
            {group.items.map((entry) => (
              <li key={entry.date} className="flex items-center gap-2 text-sm">
                {entry.date === today ? (
                  <span className="font-medium text-ink">{humanDate(entry.date)} — today</span>
                ) : (
                  <Link
                    to={`/brief/${entry.date}`}
                    className="text-accent hover:underline"
                  >
                    {humanDate(entry.date)}
                  </Link>
                )}
                {entry.has_audio && (
                  <span className="text-muted" title="Audio brief available">
                    🎧
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
