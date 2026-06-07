# course-builder — contract reference

The exact, copy-paste-able formats the `course-builder` skill must produce. SKILL.md links here;
read this when authoring files. The hub reads these read-only — get the shapes right and the
course "just works."

## Directory layout

```
<slug>/
  course.json            # manifest (below)
  lessons/<id>.md        # written lesson, markdown (the markdown SUBSET below)
  exercises/<id>.md      # practice: a Problem then a Solution, markdown
  diagrams/<id>.mmd      # mermaid source (renders as SOURCE today, graph in M2)
  flashcards/<id>.json   # [{ "front": "...", "back": "..." }]
  quizzes/<id>.json      # hub quiz shape (below)
```

Slug rules (the CLI enforces): `^[a-z0-9-]+$` — lowercase, kebab-case, no `/`, no leading `.`.
Derive from the topic: lowercase, non-alphanumerics → `-`, collapse repeats, trim (`C++ templates`
→ `c-templates`).

## `course.json`

```jsonc
{
  "slug": "<kebab-case, == dir name>",
  "title": "…",
  "topic": "…",
  "level": "beginner|intermediate|advanced",
  "summary": "one paragraph",
  "prerequisites": ["assumed prior knowledge, prose"],   // optional, course-level
  "estimated_hours": 3,                                    // ≈ sum of lesson minutes / 60
  "created_at": "YYYY-MM-DD",                              // today
  "generator": "course-builder v1",
  "modules": [
    {
      "id": "m1", "title": "…",
      "summary": "…",                                      // optional (defaults to "")
      "lessons": [
        {
          "id": "m1l1",                                    // UNIQUE across the whole course
          "title": "…",
          "objectives": ["Observable verb …", "…"],        // see Bloom's verbs in SKILL.md
          "prereq_lessons": ["…"],                          // optional, lesson ids in THIS course
          "estimated_minutes": 20,
          "materials": [ /* see per-type fields below */ ]
        }
      ]
    }
  ]
}
```

### Material objects — required fields by `type`

| `type` | Required | Optional | Renders as |
|---|---|---|---|
| `lesson` | `type`, `path` (`lessons/*.md`) | `title` | inline markdown |
| `exercise` | `type`, `path` (`exercises/*.md`) | `title` | inline markdown (✏️) |
| `diagram` | `type`, `path` (`diagrams/*.mmd`) | `title`, `format:"mermaid"` | **mermaid source** (not a graph yet) |
| `flashcards` | `type`, `path` (`flashcards/*.json`) | `title`, `count` | flip cards |
| `quiz` | `type`, `path` (`quizzes/*.json`) | `title`, `count`, `purpose:"formative"\|"summative"` | question count only (player = M2) |
| `reading` | `type`, `url` | `title`, `note` | external link |
| `notebooklm` | `type` | `title`, `artifact`, `notebook_id`, `note` | note (⚠️ local enrichment) |

`count` must match the file's length (validate warns otherwise).

## Quiz shape (`quizzes/<id>.json`)

Exactly the hub quiz shape, so the M2 player + the mastery engine consume it unchanged.
**`validate` BLOCKS unless: each question has a `question`, ≥2 `answerOptions`, exactly ONE
`isCorrect: true`, and a `rationale` on EVERY option (right and wrong).** Always author a `hint`
on every question too (strongly recommended; not blocked).

```json
{
  "title": "Module 1 check — <name>",
  "questions": [
    {
      "question": "…",
      "answerOptions": [
        { "text": "…", "isCorrect": true,  "rationale": "why it's right" },
        { "text": "…", "isCorrect": false, "rationale": "the misconception this distractor encodes" }
      ],
      "hint": "a nudge, not the answer"
    }
  ]
}
```

(`docs/fixtures/sample-quiz.json` is a longer worked example — ignore its `Ep N` titling; a
course quiz's `title` is the module/lesson name.)

## Flashcards (`flashcards/<id>.json`)

```json
[
  { "front": "Atomic prompt (one idea)", "back": "1–3 short sentences. Plain text + **bold**/`code` only." }
]
```
Backs render through the lesson markdown renderer **inside a small tile** — no headings, no code
fences, no multi-paragraph backs.

## Exercise (`exercises/<id>.md`)

A predict-then-check practice item:

```markdown
## Problem
<a concrete task / 3–5 graded-difficulty problems for skills topics>

## Solution
<full worked solution — the learner reads after attempting>
```

## Markdown SUBSET (lessons + exercises)

The hub renderer is intentionally tiny. **Supported:** `#`–`####` headings, `-`/`*` and `1.`
lists, `>` blockquotes, fenced code ```` ``` ````, inline `` `code` ``, `**bold**`, `*italic*`,
`[text](url)`, `---` horizontal rules, paragraphs.

**NOT supported — avoid:** tables (use two lists or prose); nested/indented sub-lists; images;
`_underscore italics_` (use `*italic*` — underscores are left literal so `snake_case` is safe);
`~~strike~~`; task lists `- [ ]`; setext headings; footnotes; raw HTML; headings deeper than
`####`.

**Gotchas:** `*italic*` needs non-space at both edges (so `3 * 4 * 5` stays literal — good).
A line of only `---`/`***` is always a horizontal rule, never a heading underline. A wrapped
list item must be **indented** to continue the bullet; put a **blank line** between a list and
following prose or the prose is treated as more of the list.

**Rendering reality to author around:**
- **Don't start a lesson with `# Title`** — the hub already shows the lesson title above the body;
  begin with prose, use `##`/`###` for sections.
- **Diagrams show as raw mermaid SOURCE**, not a rendered graph (M2). Keep diagrams short and
  human-legible (`flowchart`/`mindmap`/`sequenceDiagram` read better as source than
  `xychart-beta`), and **always** convey the same idea in the lesson prose too.
- **Always fence code/commands** — unfenced lines starting with `#`, `-`, `*`, `1.`, `>` get
  misparsed as headings/lists/quotes.

## CLI bridge

Run from the **`backend/` directory** with the venv:

```bash
cd backend && .venv/bin/python -m app.courses.cli scaffold \
  --slug <slug> --title "<title>" --topic "<topic>" --level <level> \
  --summary "<summary>" --estimated-hours <n>
# After authoring the material files, commit the full manifest + validate in one step:
cd backend && .venv/bin/python -m app.courses.cli write --slug <slug> --from-file <manifest.json>
# (or validate a dir whose course.json you wrote directly:)
cd backend && .venv/bin/python -m app.courses.cli validate --path data/courses/<slug>
cd backend && .venv/bin/python -m app.courses.cli list
```

- `scaffold` makes the dir + subfolders (`lessons/ exercises/ diagrams/ flashcards/ quizzes/`) +
  a skeleton `course.json` (sets `created_at` to today); it **errors if the slug exists** (never
  overwrites). Slug must be kebab-case `^[a-z0-9-]+$` (the CLI rejects anything else).
- **Preferred:** after authoring the material files, build the full manifest and `write` it — that
  writes `course.json` **and** validates atomically, so the manifest is validated-by-construction.
  (You may also write `course.json` directly with your file tools, then `validate`.)
- `validate`/`write` return `{ok, slug, errors, warnings, module_count, lesson_count,
  material_counts}`. **`ok` must be true** (errors block; warnings are advisory but worth
  clearing). If `.venv` is missing, run `make setup` from the repo root; if that fails, report it
  and ask the user to check Python/deps.
