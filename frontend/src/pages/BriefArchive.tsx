import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { BriefResponse } from "../api/types";
import { Banner } from "../components/Banner";
import { BriefAudioCard } from "../components/BriefAudioCard";
import { useBriefShell } from "../components/BriefShell";
import { humanDate, humanDateShort, TopicSection } from "./Brief";

// QU1: read-only time travel over the never-pruned data/sweeps/<date>/ archive — the
// first surface that cashes the design's durable-record promise. Deliberately OUTSIDE
// the FR15 shell: an archived day must never pollute Today's held payload, and the SW
// stands aside for ?date= requests, so this view is live-only (needs the hub). Notes on
// an archived item stay fully live (they're date-scoped rows); Ask is hidden — chat
// resolves the served (latest) day only. Historical audio streams from
// GET /brief/audio?date= through the same player the Today shell uses.

export default function BriefArchive() {
  const { date } = useParams();
  const { pauseAudio } = useBriefShell();
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // #23: a 404 and a dead network are different facts about the archive. Only the first
  // one licenses "that morning isn't in the archive" — the record is never pruned, so
  // claiming a day is missing because the hub is unreachable is a wrong claim, not just
  // an unhelpful one.
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setBrief(null);
    setError(null);
    setMissing(false);
    setLoading(true);
    api
      .briefByDate(date ?? "")
      .then((b) => alive && setBrief(b))
      .catch((e) => {
        if (!alive) return;
        setMissing(e instanceof ApiError && e.status === 404);
        setError(e.message ?? "Couldn't load that morning");
      })
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
          <Banner
            tone="info"
            title={
              missing
                ? "That morning isn't in the archive"
                : "The hub is unreachable — archived days need a live connection"
            }
          >
            {error} —{" "}
            <Link to="/" className="text-accent hover:underline">
              Today
            </Link>{" "}
            is still there.
          </Banner>
        </div>
      )}

      {brief?.audio_available && brief.date && (
        <BriefAudioCard
          src={api.briefAudioUrl(brief.date)}
          chapters={brief.audio_chapters ?? []}
          posKey={`audio-pos-${brief.date}`}
          trackKey={brief.date}
          // The single-track rule: starting an archived morning stops Today's narration
          // rather than layering a second Kokoro voice over it.
          onPlay={pauseAudio}
        />
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
