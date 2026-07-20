import { useState } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { BriefShell } from "./components/BriefShell";
import Brief from "./pages/Brief";
import BriefArchive from "./pages/BriefArchive";
import CourseDetail from "./pages/CourseDetail";
import Courses from "./pages/Courses";
import FlashcardReview from "./pages/FlashcardReview";
import Home from "./pages/Home";
import News from "./pages/News";
import Notes from "./pages/Notes";
import Progress from "./pages/Progress";
import QuizPlayer from "./pages/QuizPlayer";
import StudyGuide from "./pages/StudyGuide";
import StudyPlan from "./pages/StudyPlan";
import TopicDetail from "./pages/TopicDetail";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
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

// M6: below `sm` the header overflows a phone width, so the morning loop gets a fixed,
// thumb-reachable tab bar instead (Today · News · Notes · Learning · More — News promoted
// from the More menu post-M7 at Kyle's request). ≥sm renders nothing — the desktop top
// nav is untouched.
function MobileTabBar() {
  const [moreOpen, setMoreOpen] = useState(false);
  const close = () => setMoreOpen(false);
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-stone-200 bg-[#f7f6f3]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
    >
      {moreOpen && (
        <div className="absolute bottom-full right-2 mb-2 w-44 rounded-xl border border-stone-200 bg-white p-1 shadow-lg">
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
          Today
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
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-[#f7f6f3]/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-ink">
            <img src="/icon.svg" alt="" className="h-7 w-7 rounded-lg" />
            Home Base
          </Link>
          <nav className="hidden items-center gap-1 text-sm sm:flex">
            <NavLink to="/" end className={navLinkClass}>
              Today
            </NavLink>
            {/* M7: the general Google-News-style mode — Today stays the custom brief. */}
            <NavLink to="/news" className={navLinkClass}>
              News
            </NavLink>
            <NavLink to="/notes" className={navLinkClass}>
              Notes
            </NavLink>
            <NavLink to="/learning" className={navLinkClass}>
              Learning
            </NavLink>
            <NavLink to="/plan" className={navLinkClass}>
              Plan
            </NavLink>
            <NavLink to="/courses" className={navLinkClass}>
              Courses
            </NavLink>
            <NavLink to="/progress" className={navLinkClass}>
              Progress
            </NavLink>
          </nav>
        </div>
      </header>

      {/* pb-28 keeps content clear of the mobile tab bar; sm:pb-8 restores the desktop py-8. */}
      <main className="mx-auto max-w-6xl px-4 pb-28 pt-8 sm:pb-8">
        {/* FR15: BriefShell holds the brief payload + the single persistent audio element
            above the routes, so Today survives the Today↔News↔Notes bounce mid-walk. */}
        <BriefShell>
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
        </BriefShell>
      </main>

      <MobileTabBar />
    </div>
  );
}
