import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  CourseAssessment,
  CourseDetail as Detail,
  CourseLesson,
  CourseMaterial,
  CourseNextItem,
  CourseQuizState,
  CourseRubric,
  Flashcard,
} from "../api/types";
import { Badge } from "../components/Badge";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";

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
  // M3: the course's ranked "what to do next" + which lesson cards are expanded (lifted here so a
  // next-up row can open the lesson it points at).
  const [next, setNext] = useState<CourseNextItem[]>([]);
  const [openLessons, setOpenLessons] = useState<Set<string>>(new Set());

  const loadNext = useCallback(
    () => api.courseNext(slug).then((r) => setNext(r.items)).catch(() => setNext([])),
    [slug],
  );

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
      .courseNext(slug)
      .then((r) => alive && setNext(r.items))
      .catch(() => {
        /* the next-up panel is a nicety; the course still renders without it */
      });
    return () => {
      alive = false;
    };
  }, [slug]);

  // After a self-assessment saves, refresh the merged detail (so the material shows its saved
  // ratings) and the next-up list (so the assessed project drops off it).
  const onAssessed = useCallback(async () => {
    await Promise.all([
      api.course(slug).then(setCourse).catch(() => {}),
      loadNext(),
    ]);
  }, [slug, loadNext]);

  const toggleLessonOpen = useCallback((lessonId: string) => {
    setOpenLessons((s) => {
      const n = new Set(s);
      if (n.has(lessonId)) n.delete(lessonId);
      else n.add(lessonId);
      return n;
    });
  }, []);

  const goToLesson = useCallback((lessonId: string) => {
    setOpenLessons((s) => new Set(s).add(lessonId));
    requestAnimationFrame(() =>
      document
        .getElementById(`lesson-${lessonId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }, []);

  const onToggle = async (lesson: CourseLesson) => {
    if (pending.has(lesson.id)) return; // ignore a re-click while this lesson's POST is in flight
    const done = !lesson.completed;
    setPending((p) => new Set(p).add(lesson.id));
    setCourse((c) => (c ? setLessonDone(c, lesson.id, done) : c)); // optimistic + derived progress
    try {
      await api.setLessonComplete(slug, lesson.id, done);
      void loadNext(); // completing/uncompleting a lesson changes what's next
    } catch {
      setCourse((c) => (c ? setLessonDone(c, lesson.id, !done) : c)); // revert this lesson
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

      <NextUp items={next} slug={slug} onGoToLesson={goToLesson} />

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
                pending={pending.has(l.id)}
                onToggle={() => onToggle(l)}
                open={openLessons.has(l.id)}
                onToggleOpen={() => toggleLessonOpen(l.id)}
                onAssessed={onAssessed}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// M3: a compact "what to do next" panel — the course-scoped mirror of the global Review queue.
// Quiz items launch the player; lesson/project items expand + scroll to their card.
function NextUp({
  items,
  slug,
  onGoToLesson,
}: {
  items: CourseNextItem[];
  slug: string;
  onGoToLesson: (lessonId: string) => void;
}) {
  if (items.length === 0) return null;
  const icon: Record<string, string> = {
    quiz_review: "🔁",
    lesson: "▶️",
    quiz_new: "❓",
    project: "🎓",
  };
  return (
    <section className="rounded-2xl border border-accent/30 bg-accent/5 p-5">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-accent">What to do next</h2>
      <ul className="mt-3 space-y-2">
        {items.map((it, i) => (
          <li
            key={i}
            className="flex items-center justify-between gap-3 rounded-xl border border-stone-200 bg-white p-3"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span aria-hidden>{icon[it.kind] ?? "•"}</span>
                <span className="truncate font-medium text-ink">{it.title}</span>
              </div>
              <p className="mt-0.5 text-xs text-muted">{it.reason}</p>
            </div>
            {it.path && (it.kind === "quiz_review" || it.kind === "quiz_new") ? (
              <Link
                to={`/courses/${encodeURIComponent(slug)}/quiz?path=${encodeURIComponent(it.path)}`}
                className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
              >
                {it.kind === "quiz_review" ? "Review" : "Take quiz"}
              </Link>
            ) : it.lesson_id ? (
              <button
                onClick={() => onGoToLesson(it.lesson_id as string)}
                className="shrink-0 rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/10"
              >
                {it.kind === "project" ? "Open" : "Continue"}
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function LessonCard({
  slug,
  lesson,
  quizzes,
  pending,
  onToggle,
  open,
  onToggleOpen,
  onAssessed,
}: {
  slug: string;
  lesson: CourseLesson;
  quizzes: Record<string, CourseQuizState>;
  pending: boolean;
  onToggle: () => void;
  open: boolean;
  onToggleOpen: () => void;
  onAssessed: () => void | Promise<void>;
}) {
  return (
    <div
      id={`lesson-${lesson.id}`}
      className="scroll-mt-4 rounded-2xl border border-stone-200 bg-white p-5 shadow-card"
    >
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
            onClick={onToggleOpen}
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
                  onAssessed={onAssessed}
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
  onAssessed,
}: {
  slug: string;
  material: CourseMaterial;
  quizState?: CourseQuizState;
  onAssessed: () => void | Promise<void>;
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

  // Project / capstone — the markdown brief, plus a rubric self-assessment widget when one is set.
  if (material.type === "project" || material.type === "capstone") {
    return (
      <div className="space-y-3">
        <FileMaterial slug={slug} material={material} label={label} />
        {material.rubric && (
          <RubricAssessment slug={slug} material={material} onAssessed={onAssessed} />
        )}
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

  if (
    material.type === "lesson" ||
    material.type === "exercise" ||
    material.type === "project" ||
    material.type === "capstone"
  ) {
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
        <p className="mt-1 text-xs text-stone-400">
          Mermaid source — graph rendering is a later enhancement.
        </p>
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
  return null;
}

// M3: a rubric self-assessment. The rubric (criteria × levels) lives on disk; the learner picks one
// level per criterion + an optional note, and it's saved to the store (content on disk, progress in
// SQLite — the same split as the lesson checkbox). Pre-fills from any saved assessment.
function RubricAssessment({
  slug,
  material,
  onAssessed,
}: {
  slug: string;
  material: CourseMaterial;
  onAssessed: () => void | Promise<void>;
}) {
  const [rubric, setRubric] = useState<CourseRubric | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>(
    material.assessment?.ratings ?? {},
  );
  const [note, setNote] = useState(material.assessment?.note ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<boolean>(Boolean(material.assessment));
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!material.rubric) return;
    let alive = true;
    api
      .courseMaterial(slug, material.rubric)
      .then((r) => {
        if (alive && r.kind === "json") setRubric(r.data as CourseRubric);
      })
      .catch(() => {
        /* the markdown brief still renders even if the rubric can't load */
      });
    return () => {
      alive = false;
    };
  }, [slug, material.rubric]);

  if (!material.rubric) return null;

  const save = async () => {
    if (!material.path) return;
    setSaving(true);
    setErr(null);
    try {
      const res: CourseAssessment = await api.assessProject(slug, material.path, {
        ratings: choices,
        note,
        self_rating: null,
      });
      setSaved(Boolean(res.updated_at) || true);
      await onAssessed();
    } catch (e) {
      setErr((e as Error).message ?? "Couldn't save your self-assessment");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-stone-200 bg-stone-50 p-4">
      <div className="mb-2 flex items-center gap-2">
        <span aria-hidden>📋</span>
        <span className="text-xs font-semibold uppercase tracking-wide text-stone-400">
          Rubric — self-assess
        </span>
        {saved && <span className="text-xs text-accent">saved ✓</span>}
      </div>
      {rubric === null ? (
        <Skeleton />
      ) : (
        <div className="space-y-3">
          {rubric.criteria.map((c) => (
            <fieldset key={c.name}>
              <legend className="text-sm font-medium text-ink">{c.name}</legend>
              <div className="mt-1 space-y-1">
                {c.levels.map((lv) => (
                  <label key={lv.label} className="flex cursor-pointer items-start gap-2 text-sm">
                    <input
                      type="radio"
                      name={`${material.path}:${c.name}`}
                      checked={choices[c.name] === lv.label}
                      onChange={() => setChoices((ch) => ({ ...ch, [c.name]: lv.label }))}
                      className="mt-1 h-3.5 w-3.5 border-stone-300 text-accent focus:ring-accent"
                    />
                    <span>
                      <span className="font-medium text-ink">{lv.label}</span>{" "}
                      <span className="text-muted">— {lv.description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note — e.g. what you'll fix before you run it"
            rows={2}
            className="w-full rounded-lg border border-stone-200 p-2 text-sm text-ink focus:border-accent focus:outline-none"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Saving…" : saved ? "Update self-assessment" : "Save self-assessment"}
            </button>
          </div>
          {err && <Banner tone="warning">{err}</Banner>}
        </div>
      )}
    </div>
  );
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
    project: "🛠",
    capstone: "🎓",
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
