import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  FlashcardGrade,
  FlashcardSessionCard,
  FlashcardSessionResponse,
} from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";
import { cx } from "../lib/format";

type Phase = "loading" | "error" | "empty" | "reviewing" | "done";

// The four self-grade buttons (M3): again/hard/good/easy → SM-2 quality 2/3/4/5 server-side.
const GRADES: Array<{ grade: FlashcardGrade; label: string; cls: string }> = [
  { grade: "again", label: "Again", cls: "border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-400" },
  { grade: "hard", label: "Hard", cls: "border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-400" },
  { grade: "good", label: "Good", cls: "border-accent/30 bg-accent-soft text-accent hover:border-accent" },
  { grade: "easy", label: "Easy", cls: "border-emerald-200 bg-emerald-50 text-emerald-700 hover:border-emerald-400" },
];

const ZERO_COUNTS: Record<FlashcardGrade, number> = { again: 0, hard: 0, good: 0, easy: 0 };

export default function FlashcardPlayer() {
  // Deck paths can contain a slash, so the path rides in the query string (like course quizzes).
  const { slug = "" } = useParams();
  const [searchParams] = useSearchParams();
  const path = searchParams.get("path") ?? "";

  const [phase, setPhase] = useState<Phase>("loading");
  const [session, setSession] = useState<FlashcardSessionResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [queue, setQueue] = useState<FlashcardSessionCard[]>([]);
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [grading, setGrading] = useState(false);
  const [gradeError, setGradeError] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<FlashcardGrade, number>>(ZERO_COUNTS);

  const start = useCallback(() => {
    setPhase("loading");
    setSession(null);
    setMessage(null);
    setQueue([]);
    setPos(0);
    setFlipped(false);
    setGradeError(null);
    setCounts(ZERO_COUNTS);
    api
      .flashcardSession(slug, path)
      .then((s) => {
        if (!s.ok || s.total === 0) {
          setMessage(s.error ?? (s.ok ? "This deck has no cards." : "Couldn't load this deck."));
          setPhase("error");
          return;
        }
        setSession(s);
        // The default queue is what's due (new cards count as due). Nothing due → offer the
        // whole deck as an optional extra pass instead of a dead end.
        const due = s.cards.filter((c) => c.due);
        if (due.length === 0) {
          setPhase("empty");
        } else {
          setQueue(due);
          setPhase("reviewing");
        }
      })
      .catch((e) => {
        setMessage(e.message ?? "Couldn't load this deck.");
        setPhase("error");
      });
  }, [slug, path]);

  useEffect(() => start(), [start]);

  const reviewAnyway = () => {
    if (!session) return;
    setQueue(session.cards);
    setPos(0);
    setFlipped(false);
    setCounts(ZERO_COUNTS);
    setPhase("reviewing");
  };

  const grade = (g: FlashcardGrade) => {
    const card = queue[pos];
    if (!card || grading) return;
    setGrading(true);
    setGradeError(null);
    api
      .gradeFlashcard(slug, { path, card_key: card.card_key, grade: g })
      .then(() => {
        setCounts((c) => ({ ...c, [g]: c[g] + 1 }));
        setFlipped(false);
        if (pos + 1 >= queue.length) setPhase("done");
        else setPos(pos + 1);
      })
      .catch((e) => {
        // The card stays up — grading again just retries the POST.
        setGradeError(e.message ?? "Couldn't save that grade — try again.");
      })
      .finally(() => setGrading(false));
  };

  const backLink = (
    <Link
      to={`/courses/${encodeURIComponent(slug)}`}
      className="text-sm text-accent hover:underline"
    >
      ← Back to course
    </Link>
  );
  const title = session?.title || "Flashcards";

  if (phase === "loading") {
    return (
      <div className="space-y-4">
        {backLink}
        <div className="h-56 animate-pulse rounded-2xl border border-stone-200 bg-white/60" />
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="space-y-4">
        {backLink}
        <Banner tone="warning" title="Couldn't start this review">
          {message}{" "}
          <button onClick={start} className="font-medium text-accent underline">
            Retry
          </button>
        </Banner>
      </div>
    );
  }

  if (phase === "empty" && session) {
    return (
      <div className="space-y-5">
        {backLink}
        <section className="rounded-2xl border border-stone-200 bg-white p-6 text-center shadow-card">
          <h1 className="text-xl font-semibold text-ink">{title}</h1>
          <p className="mt-2 text-sm text-muted">
            Nothing due — all {session.total} cards are scheduled ahead. 🎉
          </p>
          <div className="mt-4 flex justify-center gap-3">
            <button
              onClick={reviewAnyway}
              className="rounded-lg border border-stone-200 bg-white px-4 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent"
            >
              Review anyway
            </button>
          </div>
        </section>
      </div>
    );
  }

  if (phase === "done") {
    const reviewed = counts.again + counts.hard + counts.good + counts.easy;
    return (
      <div className="space-y-5">
        {backLink}
        <section className="rounded-2xl border border-stone-200 bg-white p-6 text-center shadow-card">
          <p className="text-sm text-muted">{title}</p>
          <p className="mt-1 text-4xl font-semibold text-ink">
            {reviewed} <span className="text-2xl text-muted">reviewed</span>
          </p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {counts.again > 0 && <Badge tone="stone">↺ {counts.again} again</Badge>}
            {counts.hard > 0 && <Badge tone="amber">{counts.hard} hard</Badge>}
            {counts.good > 0 && <Badge tone="accent">{counts.good} good</Badge>}
            {counts.easy > 0 && <Badge tone="neutral">{counts.easy} easy</Badge>}
          </div>
          <p className="mt-3 text-sm text-muted">
            {counts.again > 0
              ? `${counts.again} ${counts.again === 1 ? "card comes" : "cards come"} back tomorrow; the rest are scheduled out.`
              : "Every card is scheduled out — come back when they're due."}
          </p>
          <div className="mt-4 flex justify-center gap-3">
            <button
              onClick={start}
              className="rounded-lg border border-stone-200 bg-white px-4 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent"
            >
              Review again
            </button>
          </div>
        </section>
      </div>
    );
  }

  const card = queue[pos];
  if (!card) return null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        {backLink}
        <span className="text-xs text-muted">
          Card {pos + 1} of {queue.length}
        </span>
      </div>

      <div>
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stone-200">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${((pos + 1) / queue.length) * 100}%` }}
          />
        </div>
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-card">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-stone-400">
            {flipped ? "Back" : "Front"}
          </span>
          {card.new && <Badge tone="accent">new</Badge>}
        </div>
        <p className="mt-3 text-lg font-medium text-ink">{card.front}</p>

        {flipped ? (
          <div className="mt-4 border-t border-stone-100 pt-4">
            <Markdown source={card.back} className="text-ink/90" />
          </div>
        ) : (
          <div className="mt-6">
            <button
              onClick={() => setFlipped(true)}
              className="w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white hover:opacity-90"
            >
              Show answer
            </button>
          </div>
        )}
      </section>

      {flipped && (
        <div>
          <p className="mb-2 text-center text-xs text-muted">How well did you know it?</p>
          <div className="grid grid-cols-4 gap-2">
            {GRADES.map(({ grade: g, label, cls }) => (
              <button
                key={g}
                onClick={() => grade(g)}
                disabled={grading}
                className={cx(
                  "rounded-xl border px-3 py-2.5 text-sm font-medium transition disabled:opacity-50",
                  cls,
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {gradeError && (
            <p className="mt-2 text-center text-xs text-rose-700">{gradeError}</p>
          )}
        </div>
      )}
    </div>
  );
}
