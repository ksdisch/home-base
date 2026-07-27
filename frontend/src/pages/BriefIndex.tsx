import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { BriefArchiveEntry, BriefSearchResponse } from "../api/types";
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

  // Archive search (docs/ideas/archive-search.md). Browsable was only half the job — the
  // corpus grows by 8 files a day forever, and nothing anywhere searched Kyle's own
  // history. Submit-driven rather than as-you-type: every keystroke would re-walk every
  // sweep file on the Mac for a query that isn't finished yet.
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<BriefSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);

  const runSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) {
      setResults(null); // a blank box goes back to browsing, it doesn't dump the corpus
      return;
    }
    setSearching(true);
    api
      .briefSearch(q)
      .then((r) => setResults(r))
      .catch((err) => setError(err.message ?? "Search failed"))
      .finally(() => setSearching(false));
  };

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

      <form role="search" onSubmit={runSearch} className="mb-6 flex gap-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search every brief and note…"
          aria-label="Search the archive"
          className="min-w-0 flex-1 rounded-lg border border-line bg-card/60 px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          className="shrink-0 rounded-lg border border-line px-3 py-2 text-sm font-medium text-ink hover:border-accent hover:text-accent"
        >
          Search
        </button>
      </form>

      {error && (
        <p className="text-sm text-warning">{error}</p>
      )}

      {searching && <p className="text-sm text-muted">Searching…</p>}

      {results !== null && !searching && (
        <div className="mb-8">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            {results.hits.length === 0
              ? "No matches"
              : results.truncated
                ? `Showing ${results.hits.length} of ${results.total} matches`
                : `${results.total} match${results.total === 1 ? "" : "es"}`}
          </h2>
          <ul className="space-y-3">
            {results.hits.map((hit) => (
              <li key={`${hit.kind}-${hit.date}-${hit.item_id}-${hit.snippet.slice(0, 20)}`}>
                <Link
                  to={`/brief/${hit.date}`}
                  className="text-sm font-medium text-ink hover:text-accent"
                >
                  {hit.headline}
                </Link>
                <p className="mt-0.5 text-xs text-muted">
                  {hit.kind === "note" && (
                    <span className="mr-1 rounded bg-accent-soft px-1.5 py-0.5 text-accent">
                      Note
                    </span>
                  )}
                  {humanDate(hit.date)}
                  {hit.topic_title && ` · ${hit.topic_title}`}
                </p>
                <p className="mt-0.5 text-xs text-muted">{hit.snippet}</p>
              </li>
            ))}
          </ul>
        </div>
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
