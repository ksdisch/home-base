import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  CourseDetail as Detail,
  CourseLesson,
  CourseMaterial,
  Flashcard,
} from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";

export default function CourseDetail() {
  const { slug = "" } = useParams();
  const [course, setCourse] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .course(slug)
      .then((c) => alive && setCourse(c))
      .catch((e) => alive && setError(e.message ?? "Failed to load course"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [slug]);

  const onToggle = async (lesson: CourseLesson) => {
    if (!course) return;
    const next = !lesson.completed;
    const apply = (done: boolean) =>
      setCourse((c) =>
        c
          ? {
              ...c,
              modules: c.modules.map((m) => ({
                ...m,
                lessons: m.lessons.map((l) =>
                  l.id === lesson.id ? { ...l, completed: done } : l,
                ),
              })),
            }
          : c,
      );
    apply(next); // optimistic
    try {
      const res = await api.setLessonComplete(slug, lesson.id, next);
      setCourse((c) => (c ? { ...c, progress_pct: res.progress_pct, completed_lessons: res.completed_lessons } : c));
    } catch {
      apply(!next); // revert
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
          <div className="mt-4 max-w-md">
            <div className="mb-1 flex items-center justify-between text-xs text-muted">
              <span>{course.completed_lessons}/{course.lesson_count} lessons done</span>
              <span>{course.progress_pct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${course.progress_pct}%` }} />
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
              <LessonCard key={l.id} slug={slug} lesson={l} onToggle={() => onToggle(l)} />
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
  onToggle,
}: {
  slug: string;
  lesson: CourseLesson;
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
          className="mt-1 h-4 w-4 rounded border-stone-300 text-accent focus:ring-accent"
          aria-label={`Mark "${lesson.title}" complete`}
        />
        <div className="min-w-0 flex-1">
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex w-full items-center justify-between gap-2 text-left"
          >
            <span className={lesson.completed ? "font-medium text-muted line-through" : "font-medium text-ink"}>
              {lesson.title}
            </span>
            <span className="shrink-0 text-xs text-muted">
              {lesson.estimated_minutes ? `${lesson.estimated_minutes} min · ` : ""}
              {open ? "Hide ▴" : "Open ▾"}
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
                <MaterialView key={i} slug={slug} material={mat} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MaterialView({ slug, material }: { slug: string; material: CourseMaterial }) {
  const label = material.title || material.type;

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

  return <FileMaterial slug={slug} material={material} label={label} />;
}

function FileMaterial({
  slug,
  material,
  label,
}: {
  slug: string;
  material: CourseMaterial;
  label: string;
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

  if (err) return <Banner tone="warning">{err}</Banner>;

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
          <pre className="overflow-x-auto rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs text-ink/80">
            <code>{text}</code>
          </pre>
        )}
        <p className="mt-1 text-xs text-stone-400">Mermaid source — renders as a graph in M2.</p>
      </div>
    );
  }
  if (material.type === "flashcards") {
    return (
      <div>
        <MaterialHeader type="flashcards" label={label} />
        {data === null ? <Skeleton /> : <Flashcards cards={data as Flashcard[]} />}
      </div>
    );
  }
  if (material.type === "quiz") {
    const quiz = data as { questions?: unknown[] } | null;
    return (
      <div>
        <MaterialHeader type="quiz" label={label} />
        <p className="text-sm text-muted">
          {quiz?.questions ? `${quiz.questions.length} questions` : "Quiz"} — taking it in the
          in-hub quiz player lands in M2.
        </p>
      </div>
    );
  }
  return null;
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
        <span className="text-ink/90"><Markdown source={card.back} /></span>
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
