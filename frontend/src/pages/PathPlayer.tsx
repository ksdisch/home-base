import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { PathResponse, PathStep } from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";
import { masteryLabel, masteryTone } from "../components/MasteryBar";
import { clampPct, confidenceDots, cx } from "../lib/format";

// M8 — the outline+detail path player (design decision 5): a left-rail table of contents over the
// whole generated path + a right pane with the active step and a live three-axis panel. Each step's
// action launches the topic's REAL artifact surfaces (the existing routes) or, for the one glue step
// with no artifact (the ✨ bridge-check), grades an open-recall answer on the M5 grounded lane.
// Vertical slice: the bundled Jacobian-Lens fixture is the only path that exists (Generate is Phase 7).

const KIND: Record<string, { icon: string; label: string }> = {
  intro: { icon: "🧭", label: "Intro" },
  audio: { icon: "🎧", label: "Listen" },
  read: { icon: "📖", label: "Read" },
  flashcards: { icon: "🃏", label: "Flashcards" },
  quiz: { icon: "❓", label: "Quiz" },
  bridge: { icon: "✨", label: "Bridge check" },
  reflect: { icon: "✍️", label: "Reflect" },
  recap: { icon: "🔁", label: "Recap" },
};
const kindOf = (k: string) => KIND[k] ?? { icon: "•", label: k };

// Kinds that carry learnable content worth a self-rating — glue steps (intro/recap/reflect) don't.
const RATEABLE = new Set(["audio", "read", "flashcards", "quiz", "bridge"]);

export default function PathPlayer() {
  const { id = "" } = useParams();
  const [path, setPath] = useState<PathResponse | null>(null);
  const [nbUrl, setNbUrl] = useState<string | null>(null); // for the audio/flashcards "open in NotebookLM" links
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); // a coverage/confidence write is in flight

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .path(id)
      .then((p) => {
        if (!alive) return;
        setPath(p);
        if (p) {
          const start = p.steps.find((s) => !s.completed) ?? p.steps[0];
          setActiveId(start?.id ?? null);
        }
      })
      .catch((e) => alive && setError(e.message ?? "Failed to load this path"))
      .finally(() => alive && setLoading(false));
    // notebooklm_url powers the external play/drill links — best-effort, the path renders without it.
    api
      .topic(id)
      .then((t) => alive && setNbUrl(t.notebooklm_url))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [id]);

  const active = path?.steps.find((s) => s.id === activeId) ?? null;

  const selectNext = () => {
    if (!path || !active) return;
    const idx = path.steps.findIndex((s) => s.id === active.id);
    const after = path.steps.slice(idx + 1);
    const next = after.find((s) => !s.completed) ?? after[0];
    if (next) setActiveId(next.id);
  };

  const onComplete = async (step: PathStep, completed: boolean) => {
    if (busy) return;
    setBusy(true);
    setWriteError(null);
    try {
      setPath(await api.completeStep(id, step.id, completed));
    } catch (e) {
      setWriteError((e as Error).message ?? "Couldn't save your progress");
    } finally {
      setBusy(false);
    }
  };

  const onRate = async (step: PathStep, rating: number) => {
    if (busy) return;
    setBusy(true);
    setWriteError(null);
    try {
      setPath(await api.rateStepConfidence(id, step.id, rating));
    } catch (e) {
      setWriteError((e as Error).message ?? "Couldn't save your rating");
    } finally {
      setBusy(false);
    }
  };

  const back = (
    <Link to="/learning" className="text-sm text-accent hover:underline">
      ← All topics
    </Link>
  );

  if (loading && !path) {
    return (
      <div className="space-y-4">
        {back}
        <div className="h-64 animate-pulse rounded-2xl border border-line bg-card/60" />
      </div>
    );
  }
  if (error && !path) {
    return (
      <div className="space-y-4">
        {back}
        <Banner tone="warning" title="Couldn't load this path">
          {error}
        </Banner>
      </div>
    );
  }
  if (!path) {
    // Reached a topic with no composed path (a stale link, or a topic the designer hasn't run on yet).
    return (
      <div className="space-y-4">
        {back}
        <Banner tone="info" title="No learning path yet">
          This topic doesn't have a composed path yet. The on-demand ✨ Generate designer arrives in a
          later phase — for now, the bundled example path is the one to explore.
        </Banner>
      </div>
    );
  }

  const totalMinutes = path.steps.reduce((n, s) => n + (s.estimated_minutes ?? 0), 0);

  return (
    <div className="space-y-6">
      {back}
      <div>
        <h1 className="text-2xl font-semibold text-ink">{path.title}</h1>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted">
          {path.topic && <span>{path.topic}</span>}
          {path.topic && <span aria-hidden>·</span>}
          <span>
            {path.step_count} step{path.step_count === 1 ? "" : "s"}
          </span>
          {totalMinutes > 0 && (
            <>
              <span aria-hidden>·</span>
              <span>~{totalMinutes} min</span>
            </>
          )}
        </div>
      </div>

      {writeError && <Banner tone="warning">{writeError}</Banner>}

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <StepRail steps={path.steps} activeId={activeId} onSelect={setActiveId} />
        <section className="rounded-2xl border border-line bg-card p-5 shadow-card sm:p-6">
          {active ? (
            <StepDetail
              notebookId={id}
              path={path}
              step={active}
              nbUrl={nbUrl}
              busy={busy}
              onComplete={onComplete}
              onRate={onRate}
              onGraded={setPath}
              onSelectNext={selectNext}
            />
          ) : (
            <p className="text-sm text-muted">Pick a step from the path to begin.</p>
          )}
        </section>
      </div>
    </div>
  );
}

// Left rail — the whole path as a table of contents. Done steps are muted + checked, the active step
// is accented, and an unfinished bridge-check wears a ✨ so the one generated step is visible at a glance.
function StepRail({
  steps,
  activeId,
  onSelect,
}: {
  steps: PathStep[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="lg:sticky lg:top-20 lg:self-start">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        The path · {steps.length} step{steps.length === 1 ? "" : "s"}
      </div>
      <ol className="space-y-0.5">
        {steps.map((s, i) => {
          const k = kindOf(s.kind);
          const isActive = s.id === activeId;
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSelect(s.id)}
                aria-current={isActive ? "step" : undefined}
                className={cx(
                  "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition",
                  isActive
                    ? "bg-accent-soft font-medium text-accent"
                    : s.completed
                      ? "text-muted hover:bg-line-soft"
                      : "text-ink hover:bg-line-soft",
                )}
              >
                <span className="w-4 shrink-0 text-center text-xs text-muted" aria-hidden>
                  {s.completed ? "✓" : i + 1}
                </span>
                <span aria-hidden>{k.icon}</span>
                <span
                  className={cx(
                    "min-w-0 flex-1 truncate",
                    s.completed && !isActive && "line-through",
                  )}
                >
                  {s.title}
                </span>
                {s.kind === "bridge" && !s.completed && (
                  <span className="shrink-0 text-xs text-amber-700" aria-hidden title="Generated bridge-check">
                    ✨
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}

function StepDetail({
  notebookId,
  path,
  step,
  nbUrl,
  busy,
  onComplete,
  onRate,
  onGraded,
  onSelectNext,
}: {
  notebookId: string;
  path: PathResponse;
  step: PathStep;
  nbUrl: string | null;
  busy: boolean;
  onComplete: (step: PathStep, completed: boolean) => void;
  onRate: (step: PathStep, rating: number) => void;
  onGraded: (path: PathResponse) => void;
  onSelectNext: () => void;
}) {
  const k = kindOf(step.kind);
  const idx = path.steps.findIndex((s) => s.id === step.id);
  const total = path.steps.length;
  const hasNext = idx >= 0 && idx < total - 1;

  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-muted">
        <span aria-hidden>{k.icon}</span> {k.label} · step {idx + 1} of {total}
        {step.estimated_minutes ? ` · ${step.estimated_minutes} min` : ""}
      </div>
      <h2 className="mt-1 text-lg font-semibold text-ink">{step.title}</h2>

      {step.focus && <p className="mt-2 text-sm text-muted">✨ Focus: {step.focus}</p>}
      {step.kind !== "bridge" && step.body && (
        <div className="mt-3">
          <Markdown source={step.body} className="text-sm text-ink/90" />
        </div>
      )}

      <div className="mt-4 space-y-4">
        {step.kind === "bridge" ? (
          <BridgeStep notebookId={notebookId} step={step} disabled={busy} onGraded={onGraded} />
        ) : (
          <StepLaunch
            notebookId={notebookId}
            step={step}
            nbUrl={nbUrl}
            busy={busy}
            onComplete={onComplete}
          />
        )}

        {RATEABLE.has(step.kind) && (
          <ConfidenceRating
            value={step.confidence}
            disabled={busy}
            onRate={(n) => onRate(step, n)}
          />
        )}
      </div>

      {hasNext && (
        <div className="mt-5 border-t border-line-soft pt-3 text-right">
          <button onClick={onSelectNext} className="text-sm font-medium text-accent hover:underline">
            Next step →
          </button>
        </div>
      )}

      <AxisPanel path={path} />
    </div>
  );
}

// The non-bridge action row: a kind-appropriate launch into the real surface + a coverage checkbox.
// audio/flashcards open the topic on NotebookLM (there's no in-hub topic player for those yet); read
// and quiz deep-link into the existing hub routes — the quiz is the one step that earns Mastery.
function StepLaunch({
  notebookId,
  step,
  nbUrl,
  busy,
  onComplete,
}: {
  notebookId: string;
  step: PathStep;
  nbUrl: string | null;
  busy: boolean;
  onComplete: (step: PathStep, completed: boolean) => void;
}) {
  const primaryBtn =
    "rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90";
  const secondaryBtn =
    "rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/10";

  let launch: React.ReactNode = null;
  if (step.kind === "quiz" && step.artifact_id) {
    launch = (
      <Link
        to={`/topics/${encodeURIComponent(notebookId)}/quiz/${encodeURIComponent(step.artifact_id)}`}
        className={primaryBtn}
      >
        Take the quiz ▸
      </Link>
    );
  } else if (step.kind === "read" && step.artifact_id) {
    launch = (
      <Link
        to={`/topics/${encodeURIComponent(notebookId)}/guide/${encodeURIComponent(step.artifact_id)}`}
        className={primaryBtn}
      >
        Read the study guide ▸
      </Link>
    );
  } else if (step.kind === "audio" && nbUrl) {
    launch = (
      <a href={nbUrl} target="_blank" rel="noreferrer" className={primaryBtn}>
        Play in NotebookLM ↗
      </a>
    );
  } else if (step.kind === "flashcards" && nbUrl) {
    launch = (
      <a href={nbUrl} target="_blank" rel="noreferrer" className={secondaryBtn}>
        Drill on NotebookLM ↗
      </a>
    );
  }

  const note =
    step.kind === "quiz"
      ? "The one step that earns Mastery — a graded quiz moves your recall score."
      : step.kind === "flashcards"
        ? "In-hub flashcard drills are a later upgrade; the deck lives on NotebookLM for now."
        : null;

  return (
    <div className="space-y-2.5">
      {(launch || note) && (
        <div className="flex flex-wrap items-center gap-3">
          {launch}
          {note && <span className="text-xs text-muted">{note}</span>}
        </div>
      )}
      <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          checked={step.completed}
          disabled={busy}
          onChange={() => onComplete(step, !step.completed)}
          className="h-4 w-4 rounded border-line-strong text-accent focus:ring-accent disabled:opacity-50"
        />
        {step.completed ? "Done ✓" : step.kind === "audio" ? "Mark listened" : "Mark this step done"}
      </label>
    </div>
  );
}

// The one LLM step: an open-recall answer graded formatively against the topic's real sources (the
// M5 grounded lane). The server marks the step done on submit regardless of the grade (coverage) and
// NEVER moves Mastery — so it fills a gap where no study guide exists without inflating the score.
function BridgeStep({
  notebookId,
  step,
  disabled,
  onGraded,
}: {
  notebookId: string;
  step: PathStep;
  disabled: boolean;
  onGraded: (path: PathResponse) => void;
}) {
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; feedback?: string | null; error?: string | null } | null>(
    null,
  );
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    const a = answer.trim();
    if (!a || submitting || disabled) return;
    setSubmitting(true);
    setErr(null);
    try {
      const res = await api.gradeBridge(notebookId, step.id, a);
      setResult({ ok: res.ok, feedback: res.feedback, error: res.error });
      onGraded(res.path); // refreshes the three axes + reflects the step as done
    } catch (e) {
      setErr((e as Error).message ?? "Couldn't submit your answer");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-3">
      {step.body && <Markdown source={step.body} className="text-sm text-ink/90" />}
      <p className="text-xs text-muted">
        ✨ Generated bridge-check — this topic has no study guide, so recall is checked here instead.
        Graded against the real sources for feedback only; it never moves your Mastery score.
      </p>
      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        rows={4}
        placeholder="Answer in a sentence or two…"
        aria-label="Your bridge-check answer"
        disabled={submitting || disabled}
        className="w-full rounded-lg border border-line p-2 text-sm text-ink focus:border-accent focus:outline-none disabled:opacity-50"
      />
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={submit}
          disabled={submitting || disabled || !answer.trim()}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Checking…" : result ? "Submit again" : "Submit answer"}
        </button>
        {submitting && (
          <span className="text-xs text-muted">Grading against the sources — a real model call, ~5–20s.</span>
        )}
      </div>
      {err && <Banner tone="warning">{err}</Banner>}
      {result &&
        (result.ok ? (
          <div className="rounded-xl border border-accent/30 bg-accent/5 p-3">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-accent">Feedback</div>
            {result.feedback ? (
              <Markdown source={result.feedback} className="text-sm text-ink/90" />
            ) : (
              <p className="text-sm text-muted">Answer recorded — this step is marked done.</p>
            )}
          </div>
        ) : (
          <Banner tone="warning" title="Couldn't grade that just now">
            {result.error ??
              "The grader hiccuped — your step is still marked done. Try again for feedback."}
          </Banner>
        ))}
    </div>
  );
}

// A 1–5 self-rating for the active step. Feeds Confidence (never Mastery); the panel above shows the
// path-wide mean.
function ConfidenceRating({
  value,
  disabled,
  onRate,
}: {
  value?: number | null;
  disabled: boolean;
  onRate: (n: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted">How well do you know this?</span>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((n) => {
          const on = value != null && n <= value;
          return (
            <button
              key={n}
              type="button"
              disabled={disabled}
              onClick={() => onRate(n)}
              aria-label={`Rate your confidence ${n} of 5`}
              aria-pressed={on}
              className={cx(
                "text-base leading-none transition disabled:opacity-50",
                on ? "text-accent" : "text-line-strong hover:text-muted",
              )}
            >
              {on ? "●" : "○"}
            </button>
          );
        })}
      </div>
      {value != null && <span className="text-xs text-muted">{value}/5</span>}
    </div>
  );
}

// The three honest axes, live from the store: Progress (coverage — every step counts), Mastery
// (recall — earned only by testing, SM-2-decayed, "—" until then), Confidence (self-rated mean).
function AxisPanel({ path }: { path: PathResponse }) {
  return (
    <div className="mt-6 space-y-3 border-t border-line-soft pt-4">
      <div>
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-medium text-ink">
            Progress <span className="font-normal text-muted">· coverage</span>
          </span>
          <span className="text-muted">
            {path.completed_steps}/{path.step_count} · {path.progress_pct}%
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-line-soft">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${clampPct(path.progress_pct)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-ink">
          Mastery <span className="font-normal text-muted">· recall</span>
        </span>
        {path.mastery != null ? (
          <Badge
            tone={masteryTone(path.mastery)}
            title="Estimated current retention — earned only by testing, and it decays over time"
          >
            {Math.round(path.mastery * 100)}% · {masteryLabel(path.mastery)}
          </Badge>
        ) : (
          <span className="text-muted" title="Take the quiz (or drill flashcards) to start earning recall">
            — not tested yet
          </span>
        )}
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-ink">
          Confidence <span className="font-normal text-muted">· self-rated</span>
        </span>
        {path.confidence != null ? (
          <span className="text-ink" title={`Mean self-rating ${path.confidence.toFixed(1)} / 5`}>
            <span aria-hidden className="text-accent">
              {confidenceDots(path.confidence)}
            </span>{" "}
            <span className="text-muted">{path.confidence.toFixed(1)}</span>
          </span>
        ) : (
          <span className="text-muted">—</span>
        )}
      </div>
    </div>
  );
}
