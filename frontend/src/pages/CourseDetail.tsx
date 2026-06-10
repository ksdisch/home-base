import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  CourseDetail as Detail,
  CourseFlashcardDeckState,
  CourseLesson,
  CourseMaterial,
  CourseQuizState,
  Flashcard,
} from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";
import { MermaidDiagram } from "../components/MermaidDiagram";

const clampPct = (n: number) => Math.max(0, Math.min(100, n));

// Set one lesson's completion and re-derive course progress locally. Progress is a pure function
// of which lessons are done, so deriving it here (rather than trusting each POST's response)
// keeps the bar correct even when concurrent toggles resolve out of order.
function setLessonDone(c: Detail, lessonId: string, done: boolean): Detail {
  const modules = c.modules.map((m) => ({
    ...m,
    lessons: m.lessons.map((l) => (l.id === lessonId ? { ...l, completed: done } : l)),
  }));
  const completed = modules.reduce(
    (n, m) => n + m.lessons.filter((l) => l.completed).length,
    0,
  );
  const pct = c.lesson_count ? Math.round((completed / c.lesson_count) * 100) : 0;
  return { ...c, modules, completed_lessons: completed, progress_pct: pct };
}

export default function CourseDetail() {
  const { slug = "" } = useParams();
  const [course, setCourse] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<Set<string>>(new Set());
  // Per-quiz attempt/SM-2 state keyed by material path. Re-fetched on mount, so returning from a
  // quiz attempt (a separate route → this remounts) shows the fresh score + due count.
  const [quizzes, setQuizzes] = useState<Record<string, CourseQuizState>>({});
  // Per-deck flashcard review state, same lifecycle (M3).
  const [decks, setDecks] = useState<Record<string, CourseFlashcardDeckState>>({});

  useEffect(() => {
    let alive = true;
    api
      .course(slug)
      .then((c) => alive && setCourse(c))
      .catch((e) => alive && setError(e.message ?? "Failed to load course"))
      .finally(() => alive && setLoading(false));
    api
      .courseQuizzes(slug)
      .then((r) => {
        if (!alive) return;
        setQuizzes(Object.fromEntries(r.quizzes.map((q) => [q.path, q])));
      })
      .catch(() => {
        /* quiz stats are non-critical; the lessons still render without them */
      });
    api
      .courseFlashcards(slug)
      .then((r) => {
        if (!alive) return;
        setDecks(Object.fromEntries(r.decks.map((d) => [d.path, d])));
      })
      .catch(() => {
        /* deck stats are non-critical; cards still browse without them */
      });
    return () => {
      alive = false;
    };
  }, [slug]);

  const onToggle = async (lesson: CourseLesson) => {
    if (pending.has(lesson.id)) return; // ignore a re-click while this lesson's POST is in flight
    const next = !lesson.completed;
    setPending((p) => new Set(p).add(lesson.id));
    setCourse((c) => (c ? setLessonDone(c, lesson.id, next) : c)); // optimistic + derived progress
    try {
      await api.setLessonComplete(slug, lesson.id, next);
    } catch {
      setCourse((c) => (c ? setLessonDone(c, lesson.id, !next) : c)); // revert this lesson
    } finally {
      setPending((p) => {
        const n = new Set(p);
        n.delete(lesson.id);
        return n;
      });
    }
  };

  if (loading && !course) {
    return <div className="h-40 animate-pulse rounded-2xl border border-stone-200 bg-white/60" />;
  }
  if (error && !course) {
    return (
      <div className="space-y-4">
        <Link to="/courses" className="text-sm text-accent hover:underline">
          ← All courses
        </Link>
        <Banner tone="warning" title="Couldn't load this course">
          {error}
        </Banner>
      </div>
    );
  }
  if (!course) return null;

  return (
    <div className="space-y-8">
      <div>
        <Link to="/courses" className="text-sm text-accent hover:underline">
          ← All courses
        </Link>
        <div className="mt-3">
          <h1 className="text-2xl font-semibold text-ink">{course.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone="accent">{course.level}</Badge>
            {course.topic && <span className="text-xs text-muted">{course.topic}</span>}
            {course.estimated_hours ? (
              <span className="text-xs text-muted">· ~{course.estimated_hours}h</span>
            ) : null}
          </div>
          {course.summary && <p className="mt-3 max-w-2xl text-sm text-muted">{course.summary}</p>}
          {course.prerequisites.length > 0 && (
            <p className="mt-2 max-w-2xl text-xs text-muted">
              <span className="font-semibold text-stone-500">Prerequisites:</span>{" "}
              {course.prerequisites.join("; ")}
            </p>
          )}
          <div className="mt-4 max-w-md">
            <div className="mb-1 flex items-center justify-between text-xs text-muted">
              <span>{course.completed_lessons}/{course.lesson_count} lessons done</span>
              <span>{course.progress_pct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${clampPct(course.progress_pct)}%` }} />
            </div>
          </div>
        </div>
      </div>

      {course.modules.map((m, mi) => (
        <section key={m.id} className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              <span className="text-muted">Module {mi + 1}.</span> {m.title}
            </h2>
            {m.summary && <p className="mt-1 text-sm text-muted">{m.summary}</p>}
          </div>
          <div className="space-y-3">
            {m.lessons.map((l) => (
              <LessonCard
                key={l.id}
                slug={slug}
                lesson={l}
                quizzes={quizzes}
                decks={decks}
                pending={pending.has(l.id)}
                onToggle={() => onToggle(l)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function LessonCard({
  slug,
  lesson,
  quizzes,
  decks,
  pending,
  onToggle,
}: {
  slug: string;
  lesson: CourseLesson;
  quizzes: Record<string, CourseQuizState>;
  decks: Record<string, CourseFlashcardDeckState>;
  pending: boolean;
  onToggle: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-card">
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={lesson.completed}
          onChange={onToggle}
          disabled={pending}
          className="mt-1 h-4 w-4 rounded border-stone-300 text-accent focus:ring-accent disabled:opacity-50"
          aria-label={`Mark "${lesson.title}" complete`}
        />
        <div className="min-w-0 flex-1">
          <button
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex w-full items-center justify-between gap-2 text-left"
          >
            <span className={lesson.completed ? "font-medium text-muted line-through" : "font-medium text-ink"}>
              {lesson.title}
            </span>
            <span className="shrink-0 text-xs text-muted">
              {lesson.estimated_minutes ? `${lesson.estimated_minutes} min · ` : ""}
              {open ? "Hide" : "Open"} <span aria-hidden>{open ? "▴" : "▾"}</span>
            </span>
          </button>

          {lesson.objectives.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {lesson.objectives.map((o, i) => (
                <li key={i}>
                  <Badge tone="neutral">{o}</Badge>
                </li>
              ))}
            </ul>
          )}

          {open && (
            <div className="mt-4 space-y-5 border-t border-stone-100 pt-4">
              {lesson.materials.map((mat, i) => (
                <MaterialView
                  key={i}
                  slug={slug}
                  material={mat}
                  quizState={mat.path ? quizzes[mat.path] : undefined}
                  deckState={mat.path ? decks[mat.path] : undefined}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MaterialView({
  slug,
  material,
  quizState,
  deckState,
}: {
  slug: string;
  material: CourseMaterial;
  quizState?: CourseQuizState;
  deckState?: CourseFlashcardDeckState;
}) {
  const label = material.title || material.type;

  // A quiz is launched into the answer-key-free in-hub player — never fetch its keyed JSON here.
  if (material.type === "quiz") {
    return <QuizMaterial slug={slug} material={material} label={label} state={quizState} />;
  }

  // Materials with no file body — render from manifest metadata directly.
  if (material.type === "reading") {
    return (
      <div>
        <MaterialHeader type="reading" label={label} />
        <a href={material.url ?? "#"} target="_blank" rel="noreferrer" className="text-sm text-accent hover:underline">
          {material.url} ↗
        </a>
        {material.note && <p className="mt-1 text-xs text-muted">{material.note}</p>}
      </div>
    );
  }
  if (material.type === "notebooklm") {
    return (
      <div>
        <MaterialHeader type="notebooklm" label={label} />
        <p className="text-sm text-muted">
          {material.note ?? "Optional NotebookLM artifact — generate locally with the audio-series skill."}
        </p>
      </div>
    );
  }

  return <FileMaterial slug={slug} material={material} label={label} deckState={deckState} />;
}

function FileMaterial({
  slug,
  material,
  label,
  deckState,
}: {
  slug: string;
  material: CourseMaterial;
  label: string;
  deckState?: CourseFlashcardDeckState;
}) {
  const [data, setData] = useState<unknown>(null);
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!material.path) return;
    let alive = true;
    api
      .courseMaterial(slug, material.path)
      .then((r) => {
        if (!alive) return;
        if (r.kind === "json") setData(r.data);
        else setText(r.text ?? "");
      })
      .catch((e) => alive && setErr(e.message ?? "Couldn't load material"));
    return () => {
      alive = false;
    };
  }, [slug, material.path]);

  if (err) {
    return (
      <div>
        <MaterialHeader type={material.type} label={label} />
        <Banner tone="warning">
          Couldn't load this {material.type}
          {material.path ? ` (${material.path})` : ""}: {err}
        </Banner>
      </div>
    );
  }

  if (material.type === "lesson" || material.type === "exercise") {
    return (
      <div>
        <MaterialHeader type={material.type} label={label} />
        {text === null ? <Skeleton /> : <Markdown source={text} />}
      </div>
    );
  }
  if (material.type === "diagram") {
    return (
      <div>
        <MaterialHeader type="diagram" label={label} />
        {text === null ? (
          <Skeleton />
        ) : (
          <>
            <MermaidDiagram source={text} />
            <details className="mt-1">
              <summary className="cursor-pointer text-xs text-stone-400 hover:text-stone-600">
                Mermaid source
              </summary>
              <pre className="mt-1 overflow-x-auto rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs text-ink/80">
                <code>{text}</code>
              </pre>
            </details>
          </>
        )}
      </div>
    );
  }
  if (material.type === "flashcards") {
    return (
      <div>
        <MaterialHeader type="flashcards" label={label} />
        {material.path && (
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Link
              to={`/courses/${encodeURIComponent(slug)}/flashcards?path=${encodeURIComponent(material.path)}`}
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              Review deck
            </Link>
            {deckState && (
              <span className="text-xs text-muted">{deckState.card_count} cards</span>
            )}
            {deckState && deckState.due_cards > 0 && (
              <Badge tone="amber">🔁 {deckState.due_cards} due</Badge>
            )}
            {deckState && deckState.tracked_cards > 0 && deckState.due_cards === 0 && (
              <Badge tone="neutral">all scheduled</Badge>
            )}
          </div>
        )}
        {data === null ? <Skeleton /> : <Flashcards cards={data as Flashcard[]} />}
      </div>
    );
  }
  return null;
}

// A quiz card: launches the in-hub player (answer-key-free) and surfaces the learner's last score
// + how many questions are due for review (from the per-course SM-2 state). No keyed JSON is
// fetched here — the player's prepare step stashes the key server-side.
function QuizMaterial({
  slug,
  material,
  label,
  state,
}: {
  slug: string;
  material: CourseMaterial;
  label: string;
  state?: CourseQuizState;
}) {
  const path = material.path ?? "";
  const count = state?.question_count ?? material.count ?? null;
  const taken = (state?.attempts ?? 0) > 0;
  const pct = state?.last_pct ?? null;
  const scoreTone = pct == null ? "neutral" : pct >= 80 ? "accent" : pct >= 50 ? "amber" : "stone";
  return (
    <div>
      <MaterialHeader type="quiz" label={label} />
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to={`/courses/${encodeURIComponent(slug)}/quiz?path=${encodeURIComponent(path)}`}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          {taken ? "Retake quiz" : "Take quiz"}
        </Link>
        {count != null && <span className="text-xs text-muted">{count} questions</span>}
        {taken && state?.last_score != null && (
          <Badge tone={scoreTone}>
            Last: {state.last_score}/{state.last_total}
          </Badge>
        )}
        {state && state.due_questions > 0 && (
          <Badge tone="amber">🔁 {state.due_questions} due for review</Badge>
        )}
      </div>
    </div>
  );
}

function MaterialHeader({ type, label }: { type: string; label: string }) {
  const icon: Record<string, string> = {
    lesson: "📖",
    exercise: "✏️",
    diagram: "📊",
    flashcards: "🃏",
    quiz: "❓",
    reading: "🔗",
    notebooklm: "🎧",
  };
  return (
    <div className="mb-1.5 flex items-center gap-2">
      <span aria-hidden>{icon[type] ?? "•"}</span>
      <span className="text-xs font-semibold uppercase tracking-wide text-stone-400">{type}</span>
      <span className="text-sm font-medium text-ink">{label}</span>
    </div>
  );
}

function Flashcards({ cards }: { cards: Flashcard[] }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {cards.map((c, i) => (
        <FlashcardItem key={i} card={c} />
      ))}
    </div>
  );
}

function FlashcardItem({ card }: { card: Flashcard }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <button
      onClick={() => setFlipped((f) => !f)}
      className="rounded-xl border border-stone-200 bg-stone-50 p-3 text-left text-sm transition hover:border-accent"
    >
      {flipped ? (
        <Markdown source={card.back} inline className="text-ink/90" />
      ) : (
        <span className="font-medium text-ink">{card.front}</span>
      )}
      <span className="mt-1 block text-xs text-stone-400">{flipped ? "tap to hide" : "tap to reveal"}</span>
    </button>
  );
}

function Skeleton() {
  return <div className="h-16 animate-pulse rounded-lg bg-stone-100" />;
}
