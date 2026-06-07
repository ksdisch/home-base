import { Link, NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Progress from "./pages/Progress";
import QuizPlayer from "./pages/QuizPlayer";
import StudyPlan from "./pages/StudyPlan";
import TopicDetail from "./pages/TopicDetail";

export default function App() {
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-[#f7f6f3]/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-ink">
            <img src="/icon.svg" alt="" className="h-7 w-7 rounded-lg" />
            Learning Hub
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 font-medium transition ${
                  isActive ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
                }`
              }
            >
              Topics
            </NavLink>
            <NavLink
              to="/plan"
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 font-medium transition ${
                  isActive ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
                }`
              }
            >
              Plan
            </NavLink>
            <NavLink
              to="/progress"
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 font-medium transition ${
                  isActive ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
                }`
              }
            >
              Progress
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/plan" element={<StudyPlan />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/topics/:id" element={<TopicDetail />} />
          <Route path="/topics/:id/quiz/:quizId" element={<QuizPlayer />} />
        </Routes>
      </main>
    </div>
  );
}
