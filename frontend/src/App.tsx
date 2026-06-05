import { Link, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
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
          <p className="hidden text-sm text-muted sm:block">
            a calm window over your NotebookLM notebooks
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/topics/:id" element={<TopicDetail />} />
        </Routes>
      </main>
    </div>
  );
}
