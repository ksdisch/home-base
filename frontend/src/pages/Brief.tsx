import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BriefItem, BriefNote, BriefResponse, BriefTopic } from "../api/types";
import { Banner } from "../components/Banner";
import { HabitStrip } from "../components/HabitStrip";
import { Markdown } from "../components/Markdown";
import { YourLearning } from "../components/YourLearning";

// "Sunday, July 13" from the sweep folder's YYYY-MM-DD (parsed as local, not UTC).
function humanDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// "Jul 14" from a YYYY-MM-DD (parsed as local) — for the compact "developing since" chip.
function humanDateShort(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function localToday(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

// M2: flat notes on one brief item — existing notes plus an add-a-take composer. Notes
// state is local to the item after load; saves go through POST /api/brief/notes with the
// item's snapshot (slug/date/headline) so the note outlives the regenerable sweep file.
// M5 adds "Ask about this": one grounded follow-up answer per question (a real model call,
// ~5–20s). Answers are ephemeral by design; "Save as note" turns a keeper into a normal
// note through the same POST, so it appends to this item's list live and shows on /notes.
function ItemNotes({
  item,
  slug,
  date,
  readOnly = false,
}: {
  item: BriefItem;
  slug: string;
  date: string;
  readOnly?: boolean;
}) {
  const [notes, setNotes] = useState<BriefNote[]>(item.notes ?? []);
  const [composing, setComposing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [thinking, setThinking] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [qaSaved, setQaSaved] = useState(false);

  const save = () => {
    if (!draft.trim() || saving) return;
    setSaving(true);
    setError(null);
    api
      .addBriefNote({
        item_id: item.id,
        topic_slug: slug,
        brief_date: date,
        item_headline: item.headline,
        body: draft.trim(),
      })
      .then((n) => {
        setNotes((prev) => [...prev, n]);
        setDraft("");
        setComposing(false);
      })
      .catch((e) => setError(e.message ?? "Couldn't save the note"))
      .finally(() => setSaving(false));
  };

  const remove = (id: number) => {
    api
      .deleteBriefNote(id)
      .then(() => setNotes((prev) => prev.filter((n) => n.id !== id)))
      .catch((e) => setError(e.message ?? "Couldn't delete the note"));
  };

  const ask = () => {
    const q = question.trim();
    if (!q || thinking) return;
    setThinking(true);
    setChatError(null);
    setAnswer(null);
    setQaSaved(false);
    api
      .briefChat({ item_id: item.id, topic_slug: slug, question: q })
      .then((r) => {
        setAnswer(r.answer);
        setAskedQuestion(q);
      })
      .catch((e) => setChatError(e.message ?? "Couldn't get an answer"))
      .finally(() => setThinking(false));
  };

  const closeAsk = () => {
    setAsking(false);
    setQuestion("");
    setAnswer(null);
    setChatError(null);
    setQaSaved(false);
  };

  const saveAnswerAsNote = () => {
    if (!answer || qaSaved) return;
    api
      .addBriefNote({
        item_id: item.id,
        topic_slug: slug,
        brief_date: date,
        item_headline: item.headline,
        body: `**Q:** ${askedQuestion}\n\n**A:** ${answer}`,
      })
      .then((n) => {
        setNotes((prev) => [...prev, n]);
        setQaSaved(true);
      })
      .catch((e) => setChatError(e.message ?? "Couldn't save the answer"));
  };

  return (
    <div className="mt-2">
      {notes.length > 0 && (
        <ul className="space-y-1">
          {notes.map((n) => (
            <li
              key={n.id}
              className="group flex items-start justify-between gap-3 rounded-lg bg-accent-soft/40 px-3 py-1.5"
            >
              <p className="whitespace-pre-wrap text-sm text-ink/90">{n.body}</p>
              {/* Touch screens have no hover: always visible below sm, hover-revealed ≥sm. */}
              <button
                onClick={() => remove(n.id)}
                aria-label={`Delete note ${n.id}`}
                disabled={readOnly}
                title={readOnly ? "Offline — deletes need the hub" : undefined}
                className="-m-2 p-2 text-xs text-muted transition disabled:opacity-50 sm:m-0 sm:p-0 sm:opacity-0 sm:group-hover:opacity-100"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {composing ? (
        <div className="mt-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Your take or question…"
            rows={2}
            autoFocus
            className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm text-ink"
          />
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <button
              onClick={save}
              disabled={!draft.trim() || saving}
              className="rounded-lg bg-accent-soft px-4 py-2 text-xs font-medium text-accent disabled:opacity-50 sm:px-3 sm:py-1"
            >
              {saving ? "Saving…" : "Save note"}
            </button>
            <button
              onClick={() => {
                setComposing(false);
                setDraft("");
              }}
              className="min-h-[44px] text-xs text-muted hover:text-ink sm:min-h-0"
            >
              Cancel
            </button>
            {error && <span className="text-xs text-red-600">{error}</span>}
          </div>
        </div>
      ) : asking ? (
        <div className="mt-2">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a follow-up about this story…"
            rows={2}
            autoFocus
            className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm text-ink"
          />
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <button
              onClick={ask}
              disabled={!question.trim() || thinking}
              className="rounded-lg bg-accent-soft px-4 py-2 text-xs font-medium text-accent disabled:opacity-50 sm:px-3 sm:py-1"
            >
              {thinking ? "Thinking…" : answer ? "Ask again" : "Ask"}
            </button>
            <button
              onClick={closeAsk}
              className="min-h-[44px] text-xs text-muted hover:text-ink sm:min-h-0"
            >
              Close
            </button>
            {thinking && <span className="text-xs text-muted">usually 10–20 seconds</span>}
            {chatError && <span className="text-xs text-red-600">{chatError}</span>}
          </div>
          {answer && (
            <div className="mt-2 rounded-lg border border-stone-200 bg-white/80 px-3 py-2">
              <div className="text-sm text-ink/90">
                <Markdown source={answer} />
              </div>
              <div className="mt-2 flex items-center gap-3 border-t border-stone-100 pt-2">
                <button
                  onClick={saveAnswerAsNote}
                  disabled={qaSaved}
                  className="min-h-[44px] text-xs font-medium text-accent disabled:text-muted sm:min-h-0"
                >
                  {qaSaved ? "Saved to notes ✓" : "Save as note"}
                </button>
                <span className="text-xs text-muted">
                  answered from this brief + model knowledge — no live web
                </span>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <button
            onClick={() => setComposing(true)}
            disabled={readOnly}
            title={readOnly ? "Offline — notes need the hub" : undefined}
            className="min-h-[44px] text-xs text-muted transition hover:text-accent disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:text-muted sm:min-h-0"
          >
            + Add note
          </button>
          <button
            onClick={() => setAsking(true)}
            disabled={readOnly}
            title={readOnly ? "Offline — Ask needs the hub" : undefined}
            className="min-h-[44px] text-xs text-muted transition hover:text-accent disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:text-muted sm:min-h-0"
          >
            Ask about this
          </button>
          {error && <span className="text-xs text-red-600">{error}</span>}
        </div>
      )}
    </div>
  );
}

function TopicSection({
  topic,
  date,
  readOnly = false,
}: {
  topic: BriefTopic;
  date: string | null;
  readOnly?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white/60 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink">{topic.title}</h2>
        {topic.as_of && <span className="text-xs text-muted">as of {topic.as_of}</span>}
      </div>

      {topic.error && (
        <div className="mt-3">
          <Banner tone="warning" title="This topic's sweep didn't validate">
            {topic.error}
          </Banner>
        </div>
      )}

      {topic.top_line && <p className="mt-3 font-medium text-ink">{topic.top_line}</p>}
      {topic.context_note && (
        <p className="mt-2 text-sm italic text-muted">{topic.context_note}</p>
      )}

      {topic.items.length > 0 && (
        <div className="mt-4 space-y-5">
          {topic.items.map((item, i) => (
            <article key={item.id || i} className="border-t border-stone-100 pt-4">
              <h3 className="font-semibold text-ink">
                {item.headline}
                {item.attribution && (
                  <span className="ml-2 text-sm font-normal text-muted">
                    — {item.attribution}
                  </span>
                )}
                {item.developing && (
                  <span
                    title={
                      item.first_seen
                        ? `This story first appeared in your ${topic.title} brief on ${item.first_seen}`
                        : "This story appeared earlier this week"
                    }
                    className="ml-2 inline-block whitespace-nowrap rounded-full bg-stone-100 px-2 py-0.5 align-middle text-[0.7rem] font-medium text-muted"
                  >
                    developing{item.first_seen ? ` · since ${humanDateShort(item.first_seen)}` : ""}
                  </span>
                )}
              </h3>
              <div className="mt-1 text-sm text-ink/90">
                <Markdown source={item.digest} inline />
              </div>
              {item.why_it_matters && (
                <p className="mt-2 text-sm">
                  <span className="font-semibold text-accent">Why it matters:</span>{" "}
                  <Markdown source={item.why_it_matters} inline />
                </p>
              )}
              {item.sources.length > 0 && (
                <p className="mt-2 text-xs text-muted">
                  {item.sources.map((s, j) => (
                    <span key={j}>
                      {j > 0 && " · "}
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent hover:underline"
                      >
                        {s.title}
                      </a>
                    </span>
                  ))}
                </p>
              )}
              {item.id && date && (
                <ItemNotes item={item} slug={topic.slug} date={date} readOnly={readOnly} />
              )}
            </article>
          ))}
        </div>
      )}

      {/* Legacy md-only day, or a json that wouldn't parse — shown whole, never dropped. */}
      {topic.raw_markdown && (
        <div className="mt-4">
          <Markdown source={topic.raw_markdown} />
        </div>
      )}
    </section>
  );
}

export default function Brief() {
  const [brief, setBrief] = useState<BriefResponse | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Bug #15: audio_available reflects the served (possibly cached) payload, but the mp3
  // itself can be unreachable — offline with an uncached copy (iOS Range → 206 → never
  // stored) or evicted by the SW's date pairing. No player beats a broken one.
  const [audioBroken, setAudioBroken] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .briefWithMeta()
      .then((r) => {
        if (!alive) return;
        setBrief(r.brief);
        setFromCache(r.fromCache);
      })
      .catch((e) => alive && setError(e.message ?? "Failed to load the brief"))
      .finally(() => alive && setLoading(false));
    // The habit metric — fire-and-forget so logging can never block the morning read.
    api.logBriefVisit().catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const stale = brief?.date != null && brief.date < localToday();
  const missingTopics = brief?.missing_topics ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Today</h1>
        <p className="mt-1 text-sm text-muted">
          {loading
            ? "Reading your morning brief…"
            : brief?.date
              ? `Your sweep from ${humanDate(brief.date)}.`
              : "Your cross-topic morning brief."}
        </p>
      </div>

      {/* M4: the ~5-min narrated cut of this sweep (sweeps/audio_brief.py + local Kokoro).
          Only rendered when the served day actually has an mp3 — no player, no 404 noise. */}
      {brief?.audio_available && !audioBroken && (
        <div className="mb-6 rounded-2xl border border-stone-200 bg-white/60 p-4">
          <p className="mb-2 text-xs font-medium text-muted">
            🎧 Listen to this brief — the ~5-minute cut
          </p>
          <audio
            controls
            preload="none"
            src={api.briefAudioUrl()}
            className="w-full"
            onError={() => setAudioBroken(true)}
          />
        </div>
      )}

      {error && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't load the brief">
            {error}
          </Banner>
        </div>
      )}

      {/* M6 offline honesty: the SW replayed the cached last brief because the hub was
          unreachable. Writes need the hub, so composers below render disabled. */}
      {fromCache && (
        <div className="mb-6">
          <Banner tone="warning" title="Offline copy">
            The hub is unreachable, so this is your cached last brief
            {brief?.date ? ` — as of ${humanDate(brief.date)}` : ""}. Notes and Ask are
            disabled until you're back online.
          </Banner>
        </div>
      )}

      {stale && !fromCache && (
        <div className="mb-6">
          <Banner tone="info" title="This brief is from a previous day">
            Run{" "}
            <code className="rounded bg-stone-100 px-1 font-mono text-[0.85em]">make sweep</code>{" "}
            for a fresh one — it takes a few minutes, then lands here on reload.
          </Banner>
        </div>
      )}

      {/* QU12: active roster topics with nothing renderable for the served day — a quiet
          topic renders a section, a crashed one gets named here instead of vanishing.
          Suppressed offline like the stale hint: `make sweep` needs the hub reachable. */}
      {missingTopics.length > 0 && !fromCache && (
        <div className="mb-6">
          <Banner
            tone="warning"
            title={
              missingTopics.length === 1
                ? "1 topic didn't run today"
                : `${missingTopics.length} topics didn't run today`
            }
          >
            {missingTopics.map((t) => t.title).join(" · ")} — the sweep failed or didn't
            validate, so there's no section below. Rerun with{" "}
            <code className="rounded bg-stone-100 px-1 font-mono text-[0.85em]">make sweep</code>{" "}
            if it persists.
          </Banner>
        </div>
      )}

      {loading && !brief && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-2xl border border-stone-200 bg-white/60"
            />
          ))}
        </div>
      )}

      {brief && !brief.has_data && !error && (
        <Banner tone="info" title="No sweeps yet">
          Run{" "}
          <code className="rounded bg-stone-100 px-1 font-mono text-[0.85em]">make sweep</code>{" "}
          to generate today's brief across your topics.
        </Banner>
      )}

      {brief && brief.topics.length > 0 && (
        <div className="space-y-4">
          {brief.topics.map((t) => (
            <TopicSection
              key={t.slug}
              topic={t}
              date={brief.date ?? null}
              readOnly={fromCache}
            />
          ))}
        </div>
      )}

      {/* M2: due reviews + active courses, surfaced after the brief (hides itself when
          there's nothing to show — it never blocks the morning read). */}
      {!loading && (
        <div className="mt-4">
          <YourLearning />
          {/* v1 habit check: mornings/notes per week vs the kickoff targets (hides itself
              until there's any signal). */}
          <HabitStrip />
        </div>
      )}
    </div>
  );
}
