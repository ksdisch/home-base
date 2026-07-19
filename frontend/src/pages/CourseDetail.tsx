import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  CourseAssessment,
  CourseDetail as Detail,
  CourseFlashcardDeck,
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
  // Per-deck flashcard review state keyed by material path — same remount-refresh behavior.
  const [decks, setDecks] = useState<Record<string, CourseFlashcardDeck>>({});
  // M3: the course's ranked "what to do next" + which lesson cards are expanded (lifted here so a
  // next-up row can open the lesson it points at).
  const [next, setNext] = useState<CourseNextItem[]>([]);
  const [openLessons, setOpenLessons] = useState<Set<string>>(new Set());
  // M5 authoring loop: edit mode is offered only when the API says the course is editable
  // (a user copy exists under COURSES_DIR — bundled examples are read-only).
  const [editing, setEditing] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [reordering, setReordering] = useState(false);
  // Bumped per material path after a regeneration so the file viewers refetch their content.
  const [matVersion, setMatVersion] = useState<Record<string, number>>({});

  const loadNext = useCallback(
    () => api.courseNext(slug).then((r) => setNext(r.items)).catch(() => setNext([])),
    [slug],
  );

  const loadQuizzes = useCallback(
    () =>
      api
        .courseQuizzes(slug)
        .then((r) => setQuizzes(Object.fromEntries(r.quizzes.map((q) => [q.path, q]))))
        .catch(() => {}),
    [slug],
  );

  const loadDecks = useCallback(
    () =>
      api
        .courseFlashcards(slug)
        .then((r) => setDecks(Object.fromEntries(r.decks.map((d) => [d.path, d]))))
        .catch(() => {}),
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
      .courseFlashcards(slug)
      .then((r) => {
        if (!alive) return;
        setDecks(Object.fromEntries(r.decks.map((d) => [d.path, d])));
      })
      .catch(() => {
        /* deck stats are non-critical; flashcards still browse without them */
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

  // M5: after a structural edit, re-pull everything derived from the manifest.
  const reload = useCallback(async () => {
    await Promise.all([
      api.course(slug).then(setCourse).catch(() => {}),
      loadQuizzes(),
      loadDecks(),
      loadNext(),
    ]);
  }, [slug, loadQuizzes, loadDecks, loadNext]);

  const onRegenerated = useCallback(
    async (path: string) => {
      setMatVersion((v) => ({ ...v, [path]: (v[path] ?? 0) + 1 }));
      await reload();
    },
    [reload],
  );

  // One in-flight reorder at a time: optimistic apply, PUT the COMPLETE order, revert on failure.
  const applyOrder = useCallback(
    async (nextModules: Detail["modules"]) => {
      if (reordering || !course) return;
      setReordering(true);
      setEditErr(null);
      const prev = course;
      setCourse({ ...course, modules: nextModules });
      try {
        const res = await api.reorderCourse(slug, {
          modules: nextModules.map((m) => ({ id: m.id, lessons: m.lessons.map((l) => l.id) })),
        });
        if (!res.ok) throw new Error(res.errors.join("; ") || "Validation failed");
        void loadNext();
      } catch (e) {
        setCourse(prev); // the manifest didn't change — put the view back
        setEditErr((e as Error).message ?? "Couldn't save the new order");
      } finally {
        setReordering(false);
      }
    },
    [course, reordering, slug, loadNext],
  );

  const moveModule = (mi: number, delta: number) => {
    if (!course) return;
    const nextModules = [...course.modules];
    const [m] = nextModules.splice(mi, 1);
    nextModules.splice(mi + delta, 0, m);
    void applyOrder(nextModules);
  };

  const moveLesson = (mi: number, li: number, delta: number) => {
    if (!course) return;
    const nextModules = course.modules.map((m) => ({ ...m, lessons: [...m.lessons] }));
    const [l] = nextModules[mi].lessons.splice(li, 1);
    nextModules[mi].lessons.splice(li + delta, 0, l);
    void applyOrder(nextModules);
  };

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
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <a
              href={api.courseExportUrl(slug)}
              download
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm font-medium text-ink hover:border-accent"
            >
              ⬇ Export
            </a>
            {course.editable && (
              <button
                onClick={() => {
                  setEditing((e) => !e);
                  setEditErr(null);
                }}
                className={
                  editing
                    ? "rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
                    : "rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/10"
                }
              >
                {editing ? "Done editing" : "✏️ Edit course"}
              </button>
            )}
          </div>
          {editErr && (
            <div className="mt-3 max-w-2xl">
              <Banner tone="warning">{editErr}</Banner>
            </div>
          )}
        </div>
      </div>

      <NextUp items={next} slug={slug} onGoToLesson={goToLesson} />

      {course.modules.map((m, mi) => (
        <section key={m.id} className="space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                <span className="text-muted">Module {mi + 1}.</span> {m.title}
              </h2>
              {m.summary && <p className="mt-1 text-sm text-muted">{m.summary}</p>}
            </div>
            {editing && (
              <span className="flex shrink-0 gap-1">
                <MoveButton
                  label={`Move module ${m.title} up`}
                  disabled={mi === 0 || reordering}
                  onClick={() => moveModule(mi, -1)}
                  dir="up"
                />
                <MoveButton
                  label={`Move module ${m.title} down`}
                  disabled={mi === course.modules.length - 1 || reordering}
                  onClick={() => moveModule(mi, 1)}
                  dir="down"
                />
              </span>
            )}
          </div>
          <div className="space-y-3">
            {m.lessons.map((l, li) => (
              <LessonCard
                key={l.id}
                slug={slug}
                lesson={l}
                quizzes={quizzes}
                decks={decks}
                pending={pending.has(l.id)}
                onToggle={() => onToggle(l)}
                open={openLessons.has(l.id)}
                onToggleOpen={() => toggleLessonOpen(l.id)}
                onAssessed={onAssessed}
                editing={editing}
                matVersion={matVersion}
                onEdited={reload}
                onEditError={setEditErr}
                onRegenerated={onRegenerated}
                reorder={{
                  up: () => moveLesson(mi, li, -1),
                  down: () => moveLesson(mi, li, 1),
                  canUp: li > 0 && !reordering,
                  canDown: li < m.lessons.length - 1 && !reordering,
                }}
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
    flashcards_review: "🃏",
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
            {it.path && it.kind === "flashcards_review" ? (
              <Link
                to={`/courses/${encodeURIComponent(slug)}/flashcards?path=${encodeURIComponent(it.path)}`}
                className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
              >
                Review cards
              </Link>
            ) : it.path && (it.kind === "quiz_review" || it.kind === "quiz_new") ? (
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

type LessonReorder = { up: () => void; down: () => void; canUp: boolean; canDown: boolean };

function MoveButton({
  label,
  disabled,
  onClick,
  dir,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  dir: "up" | "down";
}) {
  return (
    <button
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-lg border border-stone-200 px-2 py-1 text-sm text-ink hover:border-accent disabled:opacity-30"
    >
      {dir === "up" ? "↑" : "↓"}
    </button>
  );
}

function LessonCard({
  slug,
  lesson,
  quizzes,
  decks,
  pending,
  onToggle,
  open,
  onToggleOpen,
  onAssessed,
  editing,
  matVersion,
  onEdited,
  onEditError,
  onRegenerated,
  reorder,
}: {
  slug: string;
  lesson: CourseLesson;
  quizzes: Record<string, CourseQuizState>;
  decks: Record<string, CourseFlashcardDeck>;
  pending: boolean;
  onToggle: () => void;
  open: boolean;
  onToggleOpen: () => void;
  onAssessed: () => void | Promise<void>;
  editing: boolean;
  matVersion: Record<string, number>;
  onEdited: () => Promise<void>;
  onEditError: (msg: string | null) => void;
  onRegenerated: (path: string) => Promise<void>;
  reorder: LessonReorder;
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
          <div className="flex items-start gap-2">
            <button
              onClick={onToggleOpen}
              aria-expanded={open}
              className="flex min-w-0 flex-1 items-center justify-between gap-2 text-left"
            >
              <span className={lesson.completed ? "font-medium text-muted line-through" : "font-medium text-ink"}>
                {lesson.title}
              </span>
              <span className="shrink-0 text-xs text-muted">
                {lesson.estimated_minutes ? `${lesson.estimated_minutes} min · ` : ""}
                {open ? "Hide" : "Open"} <span aria-hidden>{open ? "▴" : "▾"}</span>
              </span>
            </button>
            {editing && (
              <span className="flex shrink-0 gap-1">
                <MoveButton
                  label={`Move lesson ${lesson.title} up`}
                  disabled={!reorder.canUp}
                  onClick={reorder.up}
                  dir="up"
                />
                <MoveButton
                  label={`Move lesson ${lesson.title} down`}
                  disabled={!reorder.canDown}
                  onClick={reorder.down}
                  dir="down"
                />
              </span>
            )}
          </div>

          {lesson.objectives.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {lesson.objectives.map((o, i) => (
                <li key={i}>
                  <Badge tone="neutral">{o}</Badge>
                </li>
              ))}
            </ul>
          )}
          {editing && (
            <ObjectivesEditor slug={slug} lesson={lesson} onSaved={onEdited} onError={onEditError} />
          )}

          {open && (
            <div className="mt-4 space-y-5 border-t border-stone-100 pt-4">
              {lesson.materials.map((mat, i) => (
                <MaterialView
                  key={i}
                  slug={slug}
                  material={mat}
                  quizState={mat.path ? quizzes[mat.path] : undefined}
                  deck={mat.path ? decks[mat.path] : undefined}
                  onAssessed={onAssessed}
                  editing={editing}
                  lessonId={lesson.id}
                  version={mat.path ? matVersion[mat.path] ?? 0 : 0}
                  onRegenerated={onRegenerated}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// M5: edit a lesson's objectives in place — one per line, saved through the transactional
// writer (a validation failure leaves the course untouched and surfaces the errors).
function ObjectivesEditor({
  slug,
  lesson,
  onSaved,
  onError,
}: {
  slug: string;
  lesson: CourseLesson;
  onSaved: () => Promise<void>;
  onError: (msg: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  if (!open) {
    return (
      <button
        onClick={() => {
          setText(lesson.objectives.join("\n"));
          setOpen(true);
        }}
        className="mt-2 text-xs font-medium text-accent hover:underline"
      >
        ✏️ Edit objectives
      </button>
    );
  }

  const save = async () => {
    setSaving(true);
    onError(null);
    try {
      const res = await api.editLessonObjectives(slug, lesson.id, {
        objectives: text.split("\n").map((s) => s.trim()).filter(Boolean),
      });
      if (!res.ok) throw new Error(res.errors.join("; ") || "Validation failed");
      setOpen(false);
      await onSaved();
    } catch (e) {
      onError((e as Error).message ?? "Couldn't save objectives");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-2 space-y-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={Math.max(2, text.split("\n").length)}
        placeholder="One objective per line — use assessable verbs (apply, explain, build…)"
        aria-label={`Objectives for ${lesson.title}`}
        className="w-full rounded-lg border border-stone-200 p-2 text-sm text-ink focus:border-accent focus:outline-none"
        disabled={saving}
      />
      <div className="flex items-center gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save objectives"}
        </button>
        <button
          onClick={() => setOpen(false)}
          disabled={saving}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-sm text-muted hover:border-accent"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// The file-backed types M5's regeneration lane can author (mirrors the backend's set).
const REGENERABLE = new Set(["lesson", "exercise", "diagram", "flashcards", "quiz"]);

function MaterialView({
  slug,
  material,
  quizState,
  deck,
  onAssessed,
  editing,
  lessonId,
  version,
  onRegenerated,
}: {
  slug: string;
  material: CourseMaterial;
  quizState?: CourseQuizState;
  deck?: CourseFlashcardDeck;
  onAssessed: () => void | Promise<void>;
  editing: boolean;
  lessonId: string;
  version: number;
  onRegenerated: (path: string) => Promise<void>;
}) {
  const label = material.title || material.type;

  const body = (() => {
    // A quiz is launched into the answer-key-free in-hub player — never fetch its keyed JSON here.
    if (material.type === "quiz") {
      return <QuizMaterial slug={slug} material={material} label={label} state={quizState} />;
    }

    // Flashcards get a dedicated review session (per-card SM-2); the inline grid stays for browsing.
    if (material.type === "flashcards") {
      return (
        <FlashcardsMaterial
          slug={slug}
          material={material}
          label={label}
          deck={deck}
          version={version}
        />
      );
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
      return <NotebookLmMaterial material={material} label={label} />;
    }

    // Project / capstone — the markdown brief, plus a rubric self-assessment widget when one is set.
    if (material.type === "project" || material.type === "capstone") {
      return (
        <div className="space-y-3">
          <FileMaterial slug={slug} material={material} label={label} version={version} />
          {material.rubric && (
            <RubricAssessment slug={slug} material={material} onAssessed={onAssessed} />
          )}
        </div>
      );
    }

    return <FileMaterial slug={slug} material={material} label={label} version={version} />;
  })();

  if (!editing || !material.path || !REGENERABLE.has(material.type)) return body;
  return (
    <div>
      {body}
      <RegenControl slug={slug} lessonId={lessonId} material={material} onRegenerated={onRegenerated} />
    </div>
  );
}

// M5: regenerate one material via the backend's headless claude lane. Slow by web standards
// (a real authoring call, ~1–3 min), so the confirm button becomes a busy state; a deck/quiz
// warns that replaced items reset their review stats. ok:false means the model's output failed
// validation and the course is untouched.
function RegenControl({
  slug,
  lessonId,
  material,
  onRegenerated,
}: {
  slug: string;
  lessonId: string;
  material: CourseMaterial;
  onRegenerated: (path: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [guidance, setGuidance] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const path = material.path ?? "";
  const resets = material.type === "flashcards" || material.type === "quiz";

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="mt-2 text-xs font-medium text-accent hover:underline"
      >
        ↻ Regenerate this {material.type}
      </button>
    );
  }

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.regenerateMaterial(slug, lessonId, { path, guidance });
      if (!res.ok) {
        setErr(
          res.error ??
            (res.errors.length
              ? `The regenerated content failed validation — nothing was changed: ${res.errors.join("; ")}`
              : "Regeneration failed — nothing was changed."),
        );
        return;
      }
      setOpen(false);
      setGuidance("");
      await onRegenerated(path);
    } catch (e) {
      setErr((e as Error).message ?? "Regeneration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-accent/30 bg-accent/5 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-accent">
        Regenerate {material.type}
      </div>
      {resets && (
        <p className="mt-1 text-xs text-muted">
          Heads up: replacing this {material.type} resets review/attempt stats for changed items.
        </p>
      )}
      <textarea
        value={guidance}
        onChange={(e) => setGuidance(e.target.value)}
        rows={2}
        maxLength={2000}
        placeholder="Optional guidance — e.g. go deeper on X, add harder questions"
        aria-label={`Guidance for regenerating ${material.title || material.type}`}
        className="mt-2 w-full rounded-lg border border-stone-200 p-2 text-sm text-ink focus:border-accent focus:outline-none"
        disabled={busy}
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          onClick={run}
          disabled={busy}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Regenerating…" : "Regenerate"}
        </button>
        <button
          onClick={() => setOpen(false)}
          disabled={busy}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-sm text-muted hover:border-accent"
        >
          Cancel
        </button>
        {busy && (
          <span className="text-xs text-muted">
            A real authoring call — this can take a minute or two.
          </span>
        )}
      </div>
      {err && (
        <div className="mt-2">
          <Banner tone="warning">{err}</Banner>
        </div>
      )}
    </div>
  );
}

function FileMaterial({
  slug,
  material,
  label,
  version = 0,
}: {
  slug: string;
  material: CourseMaterial;
  label: string;
  version?: number;
}) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!material.path) return;
    let alive = true;
    api
      .courseMaterial(slug, material.path)
      .then((r) => {
        if (!alive) return;
        setText(r.text ?? "");
      })
      .catch((e) => alive && setErr(e.message ?? "Couldn't load material"));
    return () => {
      alive = false;
    };
  }, [slug, material.path, version]); // version bumps after a regeneration (M5)

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
  return null;
}

// Flashcards: a Review CTA (+ due chip from the per-course SM-2 state) above the browsable
// flip-card grid. The grade buttons live on the dedicated review page, not here.
function FlashcardsMaterial({
  slug,
  material,
  label,
  deck,
  version = 0,
}: {
  slug: string;
  material: CourseMaterial;
  label: string;
  deck?: CourseFlashcardDeck;
  version?: number;
}) {
  const [cards, setCards] = useState<Flashcard[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!material.path) return;
    let alive = true;
    api
      .courseMaterial(slug, material.path)
      .then((r) => {
        if (!alive) return;
        setCards(r.kind === "json" && Array.isArray(r.data) ? (r.data as Flashcard[]) : []);
      })
      .catch((e) => alive && setErr((e as Error).message ?? "Couldn't load this deck"));
    return () => {
      alive = false;
    };
  }, [slug, material.path, version]); // version bumps after a regeneration (M5)

  const path = material.path ?? "";
  const count = deck?.card_count ?? material.count ?? cards?.length ?? null;
  return (
    <div>
      <MaterialHeader type="flashcards" label={label} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Link
          to={`/courses/${encodeURIComponent(slug)}/flashcards?path=${encodeURIComponent(path)}`}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          Review deck
        </Link>
        {count != null && <span className="text-xs text-muted">{count} cards</span>}
        {deck && deck.due_cards > 0 && (
          <Badge tone="amber">🔁 {deck.due_cards} due for review</Badge>
        )}
      </div>
      {err ? (
        <Banner tone="warning">
          Couldn't load this flashcards deck{path ? ` (${path})` : ""}: {err}
        </Banner>
      ) : cards === null ? (
        <Skeleton />
      ) : (
        <Flashcards cards={cards} />
      )}
    </div>
  );
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

// M4: a notebooklm material cross-links to the real notebook in the hub catalog — episodes,
// study guides, and quizzes live on the topic page, so we link there rather than duplicating
// them here. Degrades to the note when there's no notebook_id yet, or the id isn't in this
// machine's catalog (the enrichment is local by nature).
function NotebookLmMaterial({ material, label }: { material: CourseMaterial; label: string }) {
  const nb = material.notebook;
  const n = (key: string) => nb?.counts?.[key] ?? 0;
  return (
    <div>
      <MaterialHeader type="notebooklm" label={label} />
      {nb?.found ? (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={nb.topic_url ?? `/topics/${encodeURIComponent(nb.notebook_id)}`}
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              Open notebook
            </Link>
            <span className="text-sm font-medium text-ink">{nb.title}</span>
            {n("audio") > 0 && (
              <Badge tone="neutral">🎧 {n("audio")} episode{n("audio") === 1 ? "" : "s"}</Badge>
            )}
            {n("study_guides") > 0 && (
              <Badge tone="neutral">📖 {n("study_guides")} guide{n("study_guides") === 1 ? "" : "s"}</Badge>
            )}
            {n("quizzes") > 0 && (
              <Badge tone="neutral">❓ {n("quizzes")} quiz{n("quizzes") === 1 ? "" : "zes"}</Badge>
            )}
          </div>
          {material.note && <p className="mt-1 text-xs text-muted">{material.note}</p>}
        </div>
      ) : nb ? (
        <p className="text-sm text-muted">
          Linked notebook <code className="text-xs">{nb.notebook_id}</code> isn't in this
          machine's catalog.{material.note ? ` ${material.note}` : ""}
        </p>
      ) : (
        <p className="text-sm text-muted">
          {material.note ?? "Optional NotebookLM artifact — generate locally with the audio-series skill."}
        </p>
      )}
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
