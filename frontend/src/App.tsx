import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { BriefShell, useBriefShell } from "./components/BriefShell";
import { NewsShell } from "./components/NewsShell";
import { ThemeToggle } from "./components/ThemeToggle";
import Brief from "./pages/Brief";
import BriefArchive from "./pages/BriefArchive";
import CourseDetail from "./pages/CourseDetail";
import Courses from "./pages/Courses";
import FlashcardReview from "./pages/FlashcardReview";
import Home from "./pages/Home";
import News from "./pages/News";
import Notes from "./pages/Notes";
import PathPlayer from "./pages/PathPlayer";
import Progress from "./pages/Progress";
import QuizPlayer from "./pages/QuizPlayer";
import StudyGuide from "./pages/StudyGuide";
import StudyPlan from "./pages/StudyPlan";
import TopicDetail from "./pages/TopicDetail";

// F5: the desktop nav splits into a daily-loop cluster (Today·News·Notes, full weight) and
// a muted reference shelf (Learning·Plan·Courses·Progress), so the seven-item bar signals
// which handful Kyle opens each morning instead of seven flat peers. The active page always
// wins (accent) in either tier; the hierarchy is in the inactive weight + the divider.
const primaryNavClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 font-medium transition ${
    isActive ? "bg-accent-soft text-accent" : "text-ink hover:text-accent"
  }`;

const refNavClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 font-medium transition ${
    isActive ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
  }`;

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-[48px] flex-1 flex-col items-center justify-center rounded-lg text-xs font-medium transition ${
    isActive ? "text-accent" : "text-muted"
  }`;

const moreLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2.5 text-sm font-medium ${
    isActive ? "bg-accent-soft text-accent" : "text-ink"
  }`;

// F5: the "Today" nav label, with a freshness dot when a newer brief has landed than the
// one Kyle last opened. The dot is aria-hidden so it never alters the link's accessible
// name ("Today"), and the inline-flex wrapper keeps it beside the label in both navs (the
// mobile tab is otherwise a flex-col). Shared by the desktop header and the mobile tab bar.
function TodayLabel({ fresh }: { fresh: boolean }) {
  return (
    <span className="inline-flex items-center">
      Today
      {fresh && (
        <span
          data-testid="today-fresh-dot"
          aria-hidden="true"
          className="ml-1 h-1.5 w-1.5 rounded-full bg-accent"
        />
      )}
    </span>
  );
}

// M6: below `sm` the header overflows a phone width, so the morning loop gets a fixed,
// thumb-reachable tab bar instead (Today · News · Notes · Learning · More — News promoted
// from the More menu post-M7 at Kyle's request). ≥sm renders nothing — the desktop top
// nav is untouched.
function MobileTabBar({ todayFresh }: { todayFresh: boolean }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const close = () => setMoreOpen(false);
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
    >
      {moreOpen && (
        <div className="absolute bottom-full right-2 mb-2 w-44 rounded-xl border border-line bg-card p-1 shadow-lg">
          <NavLink to="/plan" className={moreLinkClass} onClick={close}>
            Plan
          </NavLink>
          <NavLink to="/courses" className={moreLinkClass} onClick={close}>
            Courses
          </NavLink>
          <NavLink to="/progress" className={moreLinkClass} onClick={close}>
            Progress
          </NavLink>
        </div>
      )}
      <div className="flex items-stretch px-2 py-1">
        <NavLink to="/" end className={tabClass} onClick={close}>
          <TodayLabel fresh={todayFresh} />
        </NavLink>
        <NavLink to="/news" className={tabClass} onClick={close}>
          News
        </NavLink>
        <NavLink to="/notes" className={tabClass} onClick={close}>
          Notes
        </NavLink>
        <NavLink to="/learning" className={tabClass} onClick={close}>
          Learning
        </NavLink>
        <button
          onClick={() => setMoreOpen((v) => !v)}
          aria-expanded={moreOpen}
          className={`flex min-h-[48px] flex-1 flex-col items-center justify-center rounded-lg text-xs font-medium transition ${
            moreOpen ? "text-accent" : "text-muted"
          }`}
        >
          More
        </button>
      </div>
    </nav>
  );
}

export default function App() {
  // FR15: BriefShell holds the brief payload + the single persistent audio element and must
  // outlive the Today↔News↔Notes bounce. F5 hoists it above the navs too, so both can read
  // brief.date for the freshness dot (and the shell fetches on mount to feed it).
  return (
    <BriefShell>
      {/* F1: NewsShell holds the News page's per-visit interaction state (hidden/liked/noted
          + scroll) above the routes, so a Today→News→Today hop doesn't reset it. */}
      <NewsShell>
        <AppChrome />
      </NewsShell>
    </BriefShell>
  );
}

function AppChrome() {
  const { brief } = useBriefShell();
  const location = useLocation();
  const briefDate = brief?.date ?? null;

  // F5: the last brief date Kyle actually opened (per-device — localStorage only, no backend).
  const [lastSeen, setLastSeen] = useState<string | null>(() =>
    localStorage.getItem("lastSeenBrief"),
  );

  // Opening Today ("/") with a loaded brief marks it seen and drops the dot.
  useEffect(() => {
    if (location.pathname === "/" && briefDate && briefDate !== lastSeen) {
      localStorage.setItem("lastSeenBrief", briefDate);
      setLastSeen(briefDate);
    }
  }, [location.pathname, briefDate, lastSeen]);

  const todayFresh = Boolean(briefDate && briefDate !== lastSeen);

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-ink">
            <img src="/icon.svg" alt="" className="h-7 w-7 rounded-lg" />
            Home Base
          </Link>
          <div className="flex items-center gap-1">
            <nav className="hidden items-center gap-1 text-sm sm:flex">
              {/* Daily loop — the everyday core, at full weight. */}
              <NavLink to="/" end className={primaryNavClass}>
                <TodayLabel fresh={todayFresh} />
              </NavLink>
              {/* M7: the general Google-News-style mode — Today stays the custom brief. */}
              <NavLink to="/news" className={primaryNavClass}>
                News
              </NavLink>
              <NavLink to="/notes" className={primaryNavClass}>
                Notes
              </NavLink>

              {/* F5: the divider marks where the daily loop ends and the muted reference
                  shelf begins — the priority signal the seven flat peers lacked. */}
              <span
                aria-hidden="true"
                data-testid="nav-cluster-divider"
                className="mx-1.5 h-5 w-px bg-line"
              />

              {/* Reference shelf — opened occasionally; muted so it recedes behind the loop. */}
              <NavLink to="/learning" className={refNavClass}>
                Learning
              </NavLink>
              <NavLink to="/plan" className={refNavClass}>
                Plan
              </NavLink>
              <NavLink to="/courses" className={refNavClass}>
                Courses
              </NavLink>
              <NavLink to="/progress" className={refNavClass}>
                Progress
              </NavLink>
            </nav>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* pb-28 keeps content clear of the mobile tab bar; sm:pb-8 restores the desktop py-8. */}
      <main className="mx-auto max-w-6xl px-4 pb-28 pt-8 sm:pb-8">
        <Routes>
          {/* M1: the morning brief is the home route; the Learning Hub lives on as a tab. */}
          <Route path="/" element={<Brief />} />
          {/* QU1: an archived morning by date — read-only walk over the sweep record. */}
          <Route path="/brief/:date" element={<BriefArchive />} />
          {/* M7: the general news mode — RSS-backed categories, sibling of the brief. */}
          <Route path="/news" element={<News />} />
          {/* M2: every note attached to a brief item, browsable per topic. */}
          <Route path="/notes" element={<Notes />} />
          <Route path="/learning" element={<Home />} />
          {/* M8: the outline+detail learning-path player over a NotebookLM topic. */}
          <Route path="/learning/path/:id" element={<PathPlayer />} />
          <Route path="/plan" element={<StudyPlan />} />
          <Route path="/courses" element={<Courses />} />
          <Route path="/courses/:slug" element={<CourseDetail />} />
          <Route path="/courses/:slug/quiz" element={<QuizPlayer source="course" />} />
          <Route path="/courses/:slug/flashcards" element={<FlashcardReview />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/topics/:id" element={<TopicDetail />} />
          <Route path="/topics/:id/quiz/:quizId" element={<QuizPlayer />} />
          <Route path="/topics/:id/guide/:artifactId" element={<StudyGuide />} />
        </Routes>
      </main>

      <MobileTabBar todayFresh={todayFresh} />
    </div>
  );
}
