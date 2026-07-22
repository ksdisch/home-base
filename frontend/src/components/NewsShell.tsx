import {
  createContext,
  useContext,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type ReactNode,
  type SetStateAction,
} from "react";

// F1 (full hoist): the News route remounts on every Today→News→Today hop, so the per-visit
// interaction state — the cards you hid, the ones you liked, the ones you noted — and your
// scroll position were lost each return (the tab already survives via sessionStorage, #118).
// This shell sits above <Routes> (like BriefShell) and owns exactly that state, so it outlives
// the route mount. The feed itself still refetches fresh on return; these id-keyed sets simply
// reconcile against it. In-memory by design — a full reload starts a fresh visit.

type NewsShellState = {
  hidden: Set<string>;
  setHidden: Dispatch<SetStateAction<Set<string>>>;
  liked: Set<string>;
  setLiked: Dispatch<SetStateAction<Set<string>>>;
  noted: Set<string>;
  setNoted: Dispatch<SetStateAction<Set<string>>>;
  /** Scroll position saved when News unmounts, restored once the feed is back. */
  scrollY: MutableRefObject<number>;
};

const NewsShellContext = createContext<NewsShellState | null>(null);

export function useNewsShell(): NewsShellState {
  const ctx = useContext(NewsShellContext);
  if (!ctx) throw new Error("useNewsShell must be used inside <NewsShell>");
  return ctx;
}

export function NewsShell({ children }: { children: ReactNode }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [liked, setLiked] = useState<Set<string>>(new Set());
  const [noted, setNoted] = useState<Set<string>>(new Set());
  const scrollY = useRef(0);

  return (
    <NewsShellContext.Provider
      value={{ hidden, setHidden, liked, setLiked, noted, setNoted, scrollY }}
    >
      {children}
    </NewsShellContext.Provider>
  );
}
