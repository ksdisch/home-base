import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Flashcard, FlashcardCardState, FlashcardRating } from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";

// Session order: due cards first, then never-reviewed ("new"), then the rest — file order within
// each group. Built once from the state fetch; the queue then lives locally for the session.
function buildQueue(states: FlashcardCardState[]): number[] {
  const due = states.filter((s) => s.due).map((s) => s.index);
  const fresh = states.filter((s) => !s.due && !s.tracked).map((s) => s.index);
  const later = states.filter((s) => !s.due && s.tracked).map((s) => s.index);
  return [...due, ...fresh, ...later];
}

// A dedicated review session over one deck: flip → self-grade (again/hard/good). Each grade
// advances the card's per-course SM-2 state server-side; an "again" card re-queues at the end of
// the session so you leave having recalled everything once.
export default function FlashcardReview() {
  const { slug = "" } = useParams();
  const [params] = useSearchParams();
  const path = params.get("path") ?? "";

  const [cards, setCards] = useState<Flashcard[] | null>(null);
  const [queue, setQueue] = useState<number[]>([]);
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [grading, setGrading] = useState(false);
  const [tally, setTally] = useState({ again: 0, hard: 0, good: 0 });
  const [dueCount, setDueCount] = useState(0);
  const [title, setTitle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gradeError, setGradeError] = useState<string | null>(null);

  // Bug #20: the deck lives in a search param, so the router re-runs load() on the SAME
  // mounted component — each invocation takes a token and a superseded load drops its
  // results, or grade() would POST the stale deck's index against the current path.
  const loadToken = useRef(0);

  const load = useCallback(() => {
    const token = ++loadToken.current;
    setError(null);
    setCards(null);
    setQueue([]);
    setPos(0);
    setFlipped(false);
    setGradeError(null);
    setTally({ again: 0, hard: 0, good: 0 });
    Promise.all([
      api.courseMaterial(slug, path),
      api.courseFlashcardState(slug, path),
      api.courseFlashcards(slug).catch(() => null), // deck meta (title) is a nicety
    ])
      .then(([mat, state, decks]) => {
        if (token !== loadToken.current) return; // a newer load owns the screen now
        const deck =
          mat.kind === "json" && Array.isArray(mat.data) ? (mat.data as Flashcard[]) : null;
        if (!deck) throw new Error("This material isn't a flashcards deck.");
        setCards(deck);
        setQueue(buildQueue(state.cards));
        setDueCount(state.cards.filter((c) => c.due).length);
        const meta = decks?.decks.find((d) => d.path === path);
        if (meta) setTitle(meta.title);
      })
      .catch((e) => {
        if (token !== loadToken.current) return;
        setError((e as Error).message ?? "Couldn't load this deck");
      });
  }, [slug, path]);

  useEffect(() => {
    load();
    return () => {
      loadToken.current += 1; // param change/unmount: retire any in-flight load
    };
  }, [load]);

  const grade = async (rating: FlashcardRating) => {
    const index = queue[pos];
    if (index === undefined || grading) return;
    setGrading(true);
    setGradeError(null);
    try {
      await api.reviewFlashcard(slug, path, { index, rating });
      setTally((t) => ({ ...t, [rating]: t[rating] + 1 }));
      // An "again" card comes back at the end of this session (its SM-2 relearn is tomorrow,
      // but you shouldn't walk away without recalling it once).
      setQueue((q) => (rating === "again" ? [...q, index] : q));
      setPos((p) => p + 1);
      setFlipped(false);
    } catch (e) {
      setGradeError((e as Error).message ?? "Couldn't save that grade");
    } finally {
      setGrading(false);
    }
  };

  const back = (
    <Link to={`/courses/${encodeURIComponent(slug)}`} className="text-sm text-accent hover:underline">
      ← Back to course
    </Link>
  );

  if (error) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        {back}
        <Banner tone="warning" title="Couldn't start this review">
          {error}
        </Banner>
      </div>
    );
  }
  if (cards === null) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        {back}
        <div className="h-48 animate-pulse rounded-2xl border border-line bg-card/60" />
      </div>
    );
  }

  const reviewed = tally.again + tally.hard + tally.good;
  const finished = pos >= queue.length;

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <div className="flex items-center justify-between">
        {back}
        {!finished && queue.length > 0 && (
          <span className="text-xs text-muted">
            {pos + 1} / {queue.length}
          </span>
        )}
      </div>

      <div>
        <h1 className="text-xl font-semibold text-ink">
          <span aria-hidden>🃏</span> {title ?? "Flashcards"}
        </h1>
        <div className="mt-1 flex items-center gap-2 text-xs text-muted">
          <span>{cards.length} cards</span>
          {dueCount > 0 && <Badge tone="amber">🔁 {dueCount} due</Badge>}
        </div>
      </div>

      {queue.length === 0 ? (
        <Banner tone="info">This deck has no cards to review.</Banner>
      ) : finished ? (
        <div className="rounded-2xl border border-line bg-card p-6 shadow-card">
          <h2 className="text-lg font-semibold text-ink">Session done 🎉</h2>
          <p className="mt-2 text-sm text-muted">
            {reviewed} card{reviewed === 1 ? "" : "s"} graded — {tally.good} good · {tally.hard}{" "}
            hard · {tally.again} again. Grades feed the same spaced-repetition scheduler as your
            course quizzes, so cards come back when they're due.
          </p>
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={load}
              className="rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/10"
            >
              Review again
            </button>
            <Link
              to={`/courses/${encodeURIComponent(slug)}`}
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              Back to course
            </Link>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-card p-6 shadow-card">
          <p className="text-base font-medium text-ink">{cards[queue[pos]]?.front}</p>
          {flipped && (
            <div className="mt-4 border-t border-line-soft pt-4">
              <Markdown source={cards[queue[pos]]?.back ?? ""} className="text-sm text-ink/90" />
            </div>
          )}
          <div className="mt-5">
            {!flipped ? (
              <button
                onClick={() => setFlipped(true)}
                className="w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                Reveal answer
              </button>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => grade("again")}
                  disabled={grading}
                  className="rounded-lg border border-line-strong px-3 py-2 text-sm font-medium text-muted hover:bg-line-soft disabled:opacity-50"
                >
                  Again
                </button>
                <button
                  onClick={() => grade("hard")}
                  disabled={grading}
                  className="rounded-lg border border-amber-300 px-3 py-2 text-sm font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50"
                >
                  Hard
                </button>
                <button
                  onClick={() => grade("good")}
                  disabled={grading}
                  className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
                >
                  Good
                </button>
              </div>
            )}
          </div>
          {gradeError && <Banner tone="warning">{gradeError}</Banner>}
        </div>
      )}
    </div>
  );
}
