import { useEffect, useState } from "react";

// Live Mermaid rendering for course diagrams (M3). `mermaid` is the frontend's ONE runtime
// dependency beyond react — judged worth it because diagrams are core course material. It's
// dynamic-import()ed, so Vite splits it into a separate chunk fetched only when a diagram is
// actually opened; the main bundle stays lean. Render output is SVG markup, which requires
// dangerouslySetInnerHTML — the one deliberate exception to the renderer-only philosophy in
// Markdown.tsx, contained here: securityLevel "strict" makes mermaid escape label HTML and
// block script/click handlers, and the source is a local course sidecar file, not remote input.

let mermaidPromise: Promise<typeof import("mermaid").default> | null = null;

function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((mod) => {
      const mermaid = mod.default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "neutral",
        fontFamily: "inherit",
      });
      return mermaid;
    });
  }
  return mermaidPromise;
}

let renderSeq = 0; // mermaid.render needs a unique element id per call

export function MermaidDiagram({ source }: { source: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setSvg(null);
    setFailed(false);
    loadMermaid()
      .then((mermaid) => mermaid.render(`hub-mermaid-${++renderSeq}`, source))
      .then((out) => alive && setSvg(out.svg))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [source]);

  // Parse/load failure → fall back to the labeled source block (the pre-M3 rendering).
  if (failed) {
    return (
      <div>
        <pre className="overflow-x-auto rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs text-ink/80">
          <code>{source}</code>
        </pre>
        <p className="mt-1 text-xs text-stone-400">
          Couldn't render this diagram — showing the Mermaid source instead.
        </p>
      </div>
    );
  }

  if (svg === null) {
    return <div className="h-24 animate-pulse rounded-lg bg-stone-100" aria-label="Rendering diagram…" />;
  }

  return (
    <div
      className="overflow-x-auto rounded-lg border border-stone-200 bg-white p-3 [&_svg]:mx-auto [&_svg]:max-w-full"
      role="img"
      aria-label="Course diagram"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
