import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { StudyGuideResponse } from "../api/types";
import { Banner } from "../components/Banner";
import { Markdown } from "../components/Markdown";

type Phase = "loading" | "auth" | "error" | "ready";

// In-hub study guide reader. Mirrors QuizPlayer's prepare flow: the backend downloads the
// guide via nlm and degrades auth/download failures into ok=false + a banner, never a 500.
export default function StudyGuide() {
  const { id = "", artifactId = "" } = useParams();

  const [phase, setPhase] = useState<Phase>("loading");
  const [guide, setGuide] = useState<StudyGuideResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    setPhase("loading");
    setGuide(null);
    setMessage(null);
    api
      .studyGuide(id, artifactId)
      .then((g) => {
        setGuide(g);
        if (g.ok && g.markdown) {
          setPhase("ready");
        } else if (!g.auth.ok) {
          setMessage(g.auth.message ?? "NotebookLM sign-in needed.");
          setPhase("auth");
        } else {
          setMessage(g.error ?? "Couldn't load this study guide.");
          setPhase("error");
        }
      })
      .catch((e) => {
        setMessage(e.message ?? "Couldn't load this study guide.");
        setPhase("error");
      });
  }, [id, artifactId]);

  useEffect(() => load(), [load]);

  const backLink = (
    <Link to={`/topics/${encodeURIComponent(id)}`} className="text-sm text-accent hover:underline">
      ← Back to topic
    </Link>
  );

  if (phase === "loading") {
    return (
      <div className="space-y-4">
        {backLink}
        <div className="h-56 animate-pulse rounded-2xl border border-stone-200 bg-white/60" />
      </div>
    );
  }

  if (phase === "auth") {
    return (
      <div className="space-y-4">
        {backLink}
        <Banner tone="warning" title="NotebookLM sign-in needed">
          {message} Run <code>nlm login</code> in your terminal, then{" "}
          <button onClick={load} className="font-medium text-accent underline">
            try again
          </button>
          .
        </Banner>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="space-y-4">
        {backLink}
        <Banner tone="warning" title="Couldn't load this study guide">
          {message}{" "}
          <button onClick={load} className="font-medium text-accent underline">
            Retry
          </button>
        </Banner>
      </div>
    );
  }

  if (!guide?.markdown) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {backLink}
        <a
          href={guide.notebooklm_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-medium text-accent hover:underline"
        >
          Open in NotebookLM ↗
        </a>
      </div>

      {guide.title && <h1 className="text-2xl font-semibold text-ink">{guide.title}</h1>}

      <article className="rounded-2xl border border-stone-200 bg-white p-6 shadow-card">
        <Markdown source={guide.markdown} />
      </article>
    </div>
  );
}
