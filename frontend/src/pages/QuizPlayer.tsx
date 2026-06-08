import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  QuizGradeResponse,
  QuizPrepareResponse,
  QuizReviewItem,
} from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { cx } from "../lib/format";

type Phase = "loading" | "auth" | "error" | "playing" | "grading" | "done";

export default function QuizPlayer({ source = "topic" }: { source?: "topic" | "course" }) {
  // Topic quizzes route as /topics/:id/quiz/:quizId; course quizzes as /courses/:slug/quiz?path=…
  // (the material path can contain a slash, so it rides in the query string).
  const { id = "", quizId = "", slug = "" } = useParams();
  const [searchParams] = useSearchParams();
  const coursePath = searchParams.get("path") ?? "";

  const [phase, setPhase] = useState<Phase>("loading");
  const [prep, setPrep] = useState<QuizPrepareResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number | null>>({});
  const [hints, setHints] = useState<Record<number, boolean>>({});
  const [result, setResult] = useState<QuizGradeResponse | null>(null);

  const start = useCallback(() => {
    setPhase("loading");
    setPrep(null);
    setMessage(null);
    setCurrent(0);
    setAnswers({});
    setHints({});
    setResult(null);
    const prepare =
      source === "course"
        ? api.prepareCourseQuiz(slug, coursePath)
        : api.prepareQuiz(id, quizId);
    prepare
      .then((p) => {
        if (p.ok && p.session_id) {
          setPrep(p);
          setPhase("playing");
        } else if (!p.auth.ok) {
          setMessage(p.auth.message ?? "NotebookLM sign-in needed.");
          setPhase("auth");
        } else {
          setMessage(p.error ?? "Couldn't load this quiz.");
          setPhase("error");
        }
      })
      .catch((e) => {
        setMessage(e.message ?? "Couldn't load this quiz.");
        setPhase("error");
      });
  }, [source, id, quizId, slug, coursePath]);

  useEffect(() => start(), [start]);

  const submit = () => {
    if (!prep?.session_id) return;
    setPhase("grading");
    api
      .gradeQuiz({ session_id: prep.session_id, answers, hints })
      .then((r) => {
        setResult(r);
        setPhase("done");
      })
      .catch((e) => {
        setMessage(e.message ?? "Couldn't grade this attempt — your session may have expired.");
        setPhase("error");
      });
  };

  const backLink =
    source === "course" ? (
      <Link
        to={`/courses/${encodeURIComponent(slug)}`}
        className="text-sm text-accent hover:underline"
      >
        ← Back to course
      </Link>
    ) : (
      <Link to={`/topics/${encodeURIComponent(id)}`} className="text-sm text-accent hover:underline">
        ← Back to topic
      </Link>
    );

  if (phase === "loading") {
    return (
      <div className="space-y-4">
        {backLink}
        <div className="h-56 animate-pulse rounded-2xl border border-stone-200 bg-white/60" />
      </div>
    );
  }

  if (phase === "auth") {
    return (
      <div className="space-y-4">
        {backLink}
        <Banner tone="warning" title="NotebookLM sign-in needed">
          {message} Run <code>nlm login</code> in your terminal, then{" "}
          <button onClick={start} className="font-medium text-accent underline">
            try again
          </button>
          .
        </Banner>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="space-y-4">
        {backLink}
        <Banner tone="warning" title="Couldn't start this quiz">
          {message}{" "}
          <button onClick={start} className="font-medium text-accent underline">
            Retry
          </button>
        </Banner>
      </div>
    );
  }

  if (phase === "done" && result) {
    return <Review result={result} onRetake={start} backLink={backLink} title={prep?.title} />;
  }

  if (!prep) return null;

  const q = prep.questions[current];
  const total = prep.total;
  const selected = answers[q.index] ?? null;
  const answeredCount = prep.questions.filter((x) => answers[x.index] != null).length;
  const isLast = current === total - 1;
  const grading = phase === "grading";

  const choose = (optIndex: number) =>
    setAnswers((a) => ({ ...a, [q.index]: optIndex }));
  const revealHint = () => setHints((h) => ({ ...h, [q.index]: true }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        {backLink}
        <span className="text-xs text-muted">{answeredCount} of {total} answered</span>
      </div>

      <div>
        <div className="flex items-baseline justify-between gap-3">
          <h1 className="text-xl font-semibold text-ink">{prep.title ?? "Quiz"}</h1>
          <span className="shrink-0 text-sm text-muted">
            Question {current + 1} of {total}
          </span>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stone-200">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${((current + 1) / total) * 100}%` }}
          />
        </div>
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-card">
        <p className="text-base font-medium text-ink">{q.question}</p>

        <div className="mt-4 space-y-2" role="radiogroup" aria-label="Answer options">
          {q.options.map((opt, oi) => {
            const isSel = selected === oi;
            return (
              <button
                key={oi}
                role="radio"
                aria-checked={isSel}
                onClick={() => choose(oi)}
                className={cx(
                  "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm transition",
                  isSel
                    ? "border-accent bg-accent-soft text-ink"
                    : "border-stone-200 bg-white text-ink hover:border-accent/50",
                )}
              >
                <span
                  className={cx(
                    "grid h-5 w-5 shrink-0 place-items-center rounded-full border text-[10px] font-semibold",
                    isSel ? "border-accent bg-accent text-white" : "border-stone-300 text-muted",
                  )}
                >
                  {String.fromCharCode(65 + oi)}
                </span>
                {opt}
              </button>
            );
          })}
        </div>

        {q.hint && (
          <div className="mt-4">
            {hints[q.index] ? (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                💡 {q.hint}
              </p>
            ) : (
              <button
                onClick={revealHint}
                className="text-xs font-medium text-accent hover:underline"
              >
                Show hint
              </button>
            )}
          </div>
        )}
      </section>

      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrent((c) => Math.max(0, c - 1))}
          disabled={current === 0}
          className="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent disabled:opacity-40"
        >
          ← Back
        </button>

        {isLast ? (
          <button
            onClick={submit}
            disabled={grading}
            className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {grading ? "Grading…" : "Submit quiz"}
          </button>
        ) : (
          <button
            onClick={() => setCurrent((c) => Math.min(total - 1, c + 1))}
            className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:opacity-90"
          >
            Next →
          </button>
        )}
      </div>

      {isLast && answeredCount < total && (
        <p className="text-center text-xs text-muted">
          {total - answeredCount} unanswered — they'll be marked incorrect.
        </p>
      )}
    </div>
  );
}

function Review({
  result,
  onRetake,
  backLink,
  title,
}: {
  result: QuizGradeResponse;
  onRetake: () => void;
  backLink: React.ReactNode;
  title?: string | null;
}) {
  const tone = result.pct >= 80 ? "accent" : result.pct >= 50 ? "amber" : "stone";
  return (
    <div className="space-y-6">
      {backLink}

      <section className="rounded-2xl border border-stone-200 bg-white p-6 text-center shadow-card">
        {title && <p className="text-sm text-muted">{title}</p>}
        <p className="mt-1 text-4xl font-semibold text-ink">
          {result.score} <span className="text-2xl text-muted">/ {result.total}</span>
        </p>
        <div className="mt-3 flex justify-center">
          <Badge tone={tone}>{Math.round(result.pct)}%</Badge>
        </div>
        <p className="mt-3 text-sm text-muted">Attempt saved · review every question below.</p>
        <div className="mt-4 flex justify-center gap-3">
          <button
            onClick={onRetake}
            className="rounded-lg border border-stone-200 bg-white px-4 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent"
          >
            Retake
          </button>
        </div>
      </section>

      <ol className="space-y-3">
        {result.review.map((item) => (
          <ReviewCard key={item.index} item={item} />
        ))}
      </ol>
    </div>
  );
}

function ReviewCard({ item }: { item: QuizReviewItem }) {
  return (
    <li
      className={cx(
        "rounded-2xl border bg-white p-5 shadow-card",
        item.is_correct ? "border-emerald-200" : "border-rose-200",
      )}
    >
      <div className="flex items-start gap-2">
        <span className={item.is_correct ? "text-emerald-600" : "text-rose-600"}>
          {item.is_correct ? "✓" : "✗"}
        </span>
        <p className="flex-1 text-sm font-medium text-ink">{item.question}</p>
        {item.used_hint && <Badge tone="amber">hint used</Badge>}
      </div>

      <ul className="mt-3 space-y-1.5">
        {item.options.map((opt, oi) => {
          const isCorrect = oi === item.correct_index;
          const isChosen = oi === item.chosen_index;
          return (
            <li
              key={oi}
              className={cx(
                "rounded-lg px-3 py-2 text-sm",
                isCorrect && "bg-emerald-50 text-emerald-900",
                isChosen && !isCorrect && "bg-rose-50 text-rose-900",
                !isCorrect && !isChosen && "text-muted",
              )}
            >
              <span className="font-mono text-xs text-stone-400">
                {String.fromCharCode(65 + oi)}{" "}
              </span>
              {opt}
              {isCorrect && <span className="ml-1 font-medium">· correct</span>}
              {isChosen && !isCorrect && <span className="ml-1 font-medium">· your answer</span>}
            </li>
          );
        })}
        {item.chosen_index == null && (
          <li className="px-3 py-1 text-xs italic text-muted">You left this one blank.</li>
        )}
      </ul>

      {(item.is_correct ? item.correct_rationale : item.chosen_rationale || item.correct_rationale) && (
        <p className="mt-3 border-t border-stone-100 pt-3 text-sm text-muted">
          {item.is_correct
            ? item.correct_rationale
            : item.chosen_rationale
              ? `Why not yours: ${item.chosen_rationale} — ${item.correct_rationale}`
              : item.correct_rationale}
        </p>
      )}
    </li>
  );
}
