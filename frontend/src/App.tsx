import { Link, NavLink, Route, Routes } from "react-router-dom";
import Brief from "./pages/Brief";
import CourseDetail from "./pages/CourseDetail";
import Courses from "./pages/Courses";
import Home from "./pages/Home";
import Progress from "./pages/Progress";
import QuizPlayer from "./pages/QuizPlayer";
import StudyGuide from "./pages/StudyGuide";
import StudyPlan from "./pages/StudyPlan";
import TopicDetail from "./pages/TopicDetail";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 font-medium transition ${
    isActive ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
  }`;

export default function App() {
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-[#f7f6f3]/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-ink">
            <img src="/icon.svg" alt="" className="h-7 w-7 rounded-lg" />
            Home Base
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavLink to="/" end className={navLinkClass}>
              Today
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

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          {/* M1: the morning brief is the home route; the Learning Hub lives on as a tab. */}
          <Route path="/" element={<Brief />} />
          <Route path="/learning" element={<Home />} />
          <Route path="/plan" element={<StudyPlan />} />
          <Route path="/courses" element={<Courses />} />
          <Route path="/courses/:slug" element={<CourseDetail />} />
          <Route path="/courses/:slug/quiz" element={<QuizPlayer source="course" />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/topics/:id" element={<TopicDetail />} />
          <Route path="/topics/:id/quiz/:quizId" element={<QuizPlayer />} />
          <Route path="/topics/:id/guide/:artifactId" element={<StudyGuide />} />
        </Routes>
      </main>
    </div>
  );
}
