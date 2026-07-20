import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { BriefResponse } from "../api/types";
import { Banner } from "../components/Banner";
import { humanDate, humanDateShort, TopicSection } from "./Brief";

// QU1: read-only time travel over the never-pruned data/sweeps/<date>/ archive — the
// first surface that cashes the design's durable-record promise. Deliberately OUTSIDE
// the FR15 shell: an archived day must never pollute Today's held payload, and the SW
// stands aside for ?date= requests, so this view is live-only (needs the hub). Notes on
// an archived item stay fully live (they're date-scoped rows); Ask is hidden — chat
// resolves the served (latest) day only. No audio for historical days in v1.
export default function BriefArchive() {
  const { date } = useParams();
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setBrief(null);
    setError(null);
    setLoading(true);
    api
      .briefByDate(date ?? "")
      .then((b) => alive && setBrief(b))
      .catch((e) => alive && setError(e.message ?? "Couldn't load that morning"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [date]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Archived brief</h1>
        <p className="mt-1 text-sm text-muted">
          {loading
            ? "Reading that morning…"
            : brief?.date
              ? `The morning of ${humanDate(brief.date)}, as it was swept.`
              : "A past morning from the sweep archive."}
        </p>
        <p className="mt-2 flex flex-wrap gap-3 text-sm">
          {brief?.prev_date && (
            <Link to={`/brief/${brief.prev_date}`} className="text-accent hover:underline">
              ← {humanDateShort(brief.prev_date)}
            </Link>
          )}
          {brief?.next_date && (
            <Link to={`/brief/${brief.next_date}`} className="text-accent hover:underline">
              {humanDateShort(brief.next_date)} →
            </Link>
          )}
          <Link to="/" className="text-muted hover:text-accent hover:underline">
            Today
          </Link>
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <Banner tone="info" title="That morning isn't in the archive">
            {error} —{" "}
            <Link to="/" className="text-accent hover:underline">
              Today
            </Link>{" "}
            is still there.
          </Banner>
        </div>
      )}

      {brief && brief.topics.length > 0 && (
        <div className="space-y-4">
          {brief.topics.map((t) => (
            <TopicSection key={t.slug} topic={t} date={brief.date ?? null} archived />
          ))}
        </div>
      )}
    </div>
  );
}
