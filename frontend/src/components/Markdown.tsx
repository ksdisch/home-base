import { Fragment, type ReactNode } from "react";

// A tiny, dependency-free Markdown renderer — just enough for course lessons (headings, lists,
// blockquotes, fenced + inline code, bold, links, paragraphs). Renders to React elements (no
// dangerouslySetInnerHTML), so there's no XSS surface. Deliberately not a full CommonMark impl;
// the hub keeps its frontend dep-free (see frontend/package.json).

// -- inline: **bold**, `code`, [text](url) -------------------------------------
function renderInline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Order matters: code first (so ** inside code isn't bolded), then links, then bold, then
  // italic. Italic is `*…*` only (NOT `_…_`, which would mangle snake_case identifiers) and
  // requires non-space at both inner edges, so literal math like "3 * 4 * 5" isn't italicized.
  // The link URL allows one level of balanced parens — Wikipedia/DOI links the skill recommends
  // (e.g. ".../Foo_(disambiguation)") would otherwise truncate at the first ')'.
  const pattern =
    /(`[^`]+`)|(\[[^\]]+\]\((?:[^()]|\([^()]*\))*\))|(\*\*[^*]+\*\*)|(\*(?:\S[^*]*?\S|\S)\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    const key = `${keyBase}-${i++}`;
    if (tok.startsWith("`")) {
      nodes.push(
        <code key={key} className="rounded bg-stone-100 px-1 py-0.5 font-mono text-[0.85em] text-ink">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("[")) {
      const mm = /\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)/.exec(tok)!;
      // Scheme allowlist: the renderer also gets NotebookLM-generated content (study guides),
      // so a javascript:/data: URL renders as plain text instead of a clickable anchor.
      // Scheme-less (relative/anchor) hrefs stay clickable.
      const href = mm[2].trim();
      const scheme = /^[a-z][a-z0-9+.-]*:/i.exec(href)?.[0].toLowerCase();
      if (!scheme || scheme === "http:" || scheme === "https:" || scheme === "mailto:") {
        nodes.push(
          <a key={key} href={href} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            {mm[1]}
          </a>,
        );
      } else {
        nodes.push(tok);
      }
    } else if (tok.startsWith("**")) {
      nodes.push(
        <strong key={key} className="font-semibold text-ink">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else {
      // *italic*
      nodes.push(<em key={key}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({
  source,
  className,
  inline = false,
}: {
  source: string;
  className?: string;
  inline?: boolean;
}) {
  // Inline mode: render only inline formatting into a single <span> — no block elements. Used for
  // flashcard backs, which live inside a <button> where a <div>/<p>/<ul> would be invalid HTML.
  if (inline) {
    const text = source.replace(/\r\n/g, "\n").replace(/\s*\n\s*/g, " ").trim();
    return <span className={className}>{renderInline(text, "inl")}</span>;
  }

  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let quote: string[] = [];
  let code: string[] | null = null;
  let k = 0;

  const flushPara = () => {
    if (para.length) {
      blocks.push(
        <p key={`p${k++}`} className="text-sm leading-relaxed text-ink/90">
          {renderInline(para.join(" "), `p${k}`)}
        </p>,
      );
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map((it, i) => <li key={i}>{renderInline(it, `li${k}-${i}`)}</li>);
      blocks.push(
        list.ordered ? (
          <ol key={`o${k++}`} className="list-decimal space-y-1 pl-5 text-sm text-ink/90">{items}</ol>
        ) : (
          <ul key={`u${k++}`} className="list-disc space-y-1 pl-5 text-sm text-ink/90">{items}</ul>
        ),
      );
      list = null;
    }
  };
  const flushQuote = () => {
    if (quote.length) {
      blocks.push(
        <blockquote key={`q${k++}`} className="border-l-2 border-accent/40 pl-3 text-sm italic text-muted">
          {renderInline(quote.join(" "), `q${k}`)}
        </blockquote>,
      );
      quote = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (code !== null) {
      if (line.trim().startsWith("```")) {
        blocks.push(
          <pre key={`c${k++}`} className="overflow-x-auto rounded-lg bg-stone-900 p-3 text-xs text-stone-100">
            <code>{code.join("\n")}</code>
          </pre>,
        );
        code = null;
      } else {
        code.push(raw);
      }
      continue;
    }
    if (line.trim().startsWith("```")) {
      flushPara();
      flushList();
      flushQuote();
      code = [];
      continue;
    }

    // Horizontal rule: a line of only ---, ***, or ___ (3+).
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      flushPara(); flushList(); flushQuote();
      blocks.push(<hr key={`hr${k++}`} className="border-stone-200" />);
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    const bullet = /^[-*]\s+(.*)$/.exec(line);
    const ordered = /^\d+\.\s+(.*)$/.exec(line);
    const blockquote = /^>\s?(.*)$/.exec(line);

    if (heading) {
      flushPara(); flushList(); flushQuote();
      const level = heading[1].length;
      const text = renderInline(heading[2], `h${k}`);
      const cls = {
        1: "text-xl font-semibold text-ink",
        2: "text-lg font-semibold text-ink",
        3: "text-base font-semibold text-ink",
        4: "text-sm font-semibold text-ink",
      }[level as 1 | 2 | 3 | 4];
      blocks.push(<Fragment key={`h${k++}`}>{level <= 2 ? <h3 className={cls}>{text}</h3> : <h4 className={cls}>{text}</h4>}</Fragment>);
    } else if (bullet) {
      flushPara(); flushQuote();
      if (!list || list.ordered) { flushList(); list = { ordered: false, items: [] }; }
      list.items.push(bullet[1]);
    } else if (ordered) {
      flushPara(); flushQuote();
      if (!list || !list.ordered) { flushList(); list = { ordered: true, items: [] }; }
      list.items.push(ordered[1]);
    } else if (blockquote) {
      flushPara(); flushList();
      quote.push(blockquote[1]);
    } else if (line.trim() === "") {
      flushPara(); flushList(); flushQuote();
    } else if (list && /^\s+\S/.test(raw)) {
      // Lazy continuation: only an INDENTED wrapped line joins the last item. An unindented
      // line ends the list (so prose right after a list isn't swallowed into the last bullet).
      list.items[list.items.length - 1] += " " + line.trim();
    } else {
      flushList(); flushQuote();
      para.push(line);
    }
  }
  flushPara(); flushList(); flushQuote();

  return <div className={className ? `space-y-3 ${className}` : "space-y-3"}>{blocks}</div>;
}
