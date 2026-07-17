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
  projects/<id>.md       # a larger, rubric-assessed practice project, markdown (M3)
  capstones/<id>.md      # the course-ending synthesis project, markdown (M3)
  diagrams/<id>.mmd      # mermaid source (renders as SOURCE today, graph is a later enhancement)
  flashcards/<id>.json   # [{ "front": "...", "back": "..." }]
  quizzes/<id>.json      # hub quiz shape (below)
  rubrics/<id>.json      # a rubric (criteria × levels) for a project/capstone/exercise (M3)
```

Slug rules (the CLI enforces): `^[a-z0-9]+(?:-[a-z0-9]+)*$` — lowercase kebab-case, no leading/
trailing/double `-`, no `/`, no `.`. Derive from the topic: lowercase, non-alphanumerics → `-`,
collapse repeats, trim (`C++ templates` → `c-templates`).

## `course.json`

```jsonc
{
  "slug": "<kebab-case, == dir name>",
  "title": "…",
  "topic": "…",
  "level": "beginner|intermediate|advanced",
  "summary": "one paragraph",
  "prerequisites": ["assumed prior knowledge, prose"],   // optional; shown on the course page
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
          "prereq_lessons": ["…"],                          // optional; informational, not yet rendered
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
| `exercise` | `type`, `path` (`exercises/*.md`) | `title`, `rubric` | inline markdown (✏️) |
| `project` | `type`, `path` (`projects/*.md`) | `title`, `rubric` | inline markdown (🛠) + rubric self-assessment |
| `capstone` | `type`, `path` (`capstones/*.md`) | `title`, `rubric` | inline markdown (🎓) + rubric self-assessment |
| `diagram` | `type`, `path` (`diagrams/*.mmd`) | `title`, `format:"mermaid"` | **mermaid source** (not a graph yet) |
| `flashcards` | `type`, `path` (`flashcards/*.json`) | `title`, `count` | flip cards |
| `quiz` | `type`, `path` (`quizzes/*.json`) | `title`, `count`, `purpose:"formative"\|"summative"` | in-hub player + SM-2 tracking |
| `reading` | `type`, `url` | `title`, `note` | external link |
| `notebooklm` | `type` | `title`, `artifact`, `notebook_id`, `note` | cross-link card when `notebook_id` resolves in the local catalog; the `note` otherwise (⚠️ local enrichment, M4) |

`rubric` (optional, on `exercise`/`project`/`capstone`) is a **path to a `rubrics/<id>.json`** the
learner self-assesses against in the hub (see the Rubric shape below). `validate` BLOCKS on a
missing/malformed rubric file, and *warns* if a rubric is attached to any other material type.

`count` must match the file's length (validate warns otherwise). `format` (on `diagram`) and
`purpose` (on `quiz`) are preserved metadata — author them for intent, but they're not yet shown
in the UI. Every file material's `path` must stay **inside the course dir** (no `../` / absolute) —
validate blocks an escaping path.

## NotebookLM material (`notebooklm`) — M4

File-less; the **main thread owns it** (subagents never see it). Fields: optional `title`,
`note`, `artifact` (`"audio"` | `"study_guide"` | …, informational), `notebook_id`. When
`notebook_id` matches a notebook in the machine's sidecar catalog, the hub renders a real card —
the notebook's title, episode/guide/quiz counts, and an "Open notebook" link to `/topics/<id>`.
No id (or an id this machine doesn't have) degrades to the `note`, so **always author a `note`
that stands alone** ("Optional: audio deep-dive season — generate or link locally with the
audio-series skill"). `validate` warns on a non-string `notebook_id`.

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

## Project / capstone (`projects/<id>.md`, `capstones/<id>.md`) — M3

A larger, open-ended build the learner does and then **self-assesses against a rubric**. A
`capstone` is the course-ending synthesis project (combine objectives from ≥2 modules); a
`project` is a mid-course version of the same. Markdown shape:

```markdown
## The task
<a concrete deliverable to build/design, with the specific requirements it must meet>

## What a strong result looks like
<the qualities of a good answer — read AFTER attempting, so the doing is the retrieval>

## Self-assess
<tell the learner to score their result against the rubric on this page, one level per criterion>
```

Attach a rubric via the material's `rubric` field (`"rubric": "rubrics/<id>.json"`). The hub
renders the project markdown, then a rubric widget where the learner picks one level per criterion
+ an optional note; the self-assessment is tracked (it drops off the course's "what to do next").

## Rubric (`rubrics/<id>.json`) — M3

```json
{
  "criteria": [
    {
      "name": "Correctness",
      "levels": [
        { "label": "Developing", "description": "what a weak result looks like on this dimension" },
        { "label": "Meets",      "description": "the bar a solid result clears" },
        { "label": "Exceeds",    "description": "what an excellent result adds" }
      ]
    }
  ]
}
```

`validate` BLOCKS unless: a non-empty `criteria` list; each criterion a non-empty `name` + **≥2
`levels`**; each level a non-empty `label` + `description`. Author **3–4 criteria** covering the
objectives the project exercises, each with **3 observable levels** (worst → best) phrased as what
you'd *see* in the work — not "understands X". Order levels weakest-first.

## Markdown SUBSET (lessons + exercises + projects + capstones)

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
- **Don't start a lesson *or exercise* with `# Title`** — the hub already shows the material title
  above the body, so a leading `# Title` renders it twice. Begin with prose (or `##` for the first
  section, e.g. an exercise's `## Problem`); use `##`/`###` for sections.
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
# (or validate a dir whose course.json you wrote directly — use the PATH scaffold reported,
#  NOT a hardcoded data/courses/<slug>; COURSES_DIR may be overridden:)
cd backend && .venv/bin/python -m app.courses.cli validate --path "<path from scaffold output>"
cd backend && .venv/bin/python -m app.courses.cli list
```

- `scaffold` makes the dir + subfolders (`lessons/ exercises/ diagrams/ flashcards/ quizzes/`) +
  a skeleton `course.json` (sets `created_at` to today); it **errors if the slug exists** (never
  overwrites) and **prints the real `path`** it wrote — capture it for the fallback `validate`.
  Slug must be kebab-case `^[a-z0-9]+(?:-[a-z0-9]+)*$` (the CLI rejects anything else).
- **Preferred:** after authoring the material files, build the full manifest and `write` it — that
  writes `course.json` **and** validates atomically; on `ok:false` it **rolls back** (restoring the
  prior manifest, or removing a first write) so a bad write never clobbers a good course. (You may
  also write `course.json` directly with your file tools, then `validate`.)
- `validate`/`write` return `{ok, slug, errors, warnings, module_count, lesson_count,
  material_counts}` (`write` also returns `written` + `rolled_back`). **`ok` must be true** (errors
  block; warnings are advisory but worth clearing) — and both commands **exit non-zero when
  `ok:false`**, so a shell `&&` / exit-code check is enough. If `.venv` is missing, run
  `make setup` from the repo root; if that fails, report it and ask the user to check Python/deps.
