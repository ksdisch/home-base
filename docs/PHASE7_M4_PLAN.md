# Phase 7 — Courses M4: NotebookLM enrichment in-flow

_The fourth course-pipeline milestone (see `docs/COURSE_PIPELINE_SPEC.md`). M1 made courses
readable + trackable; M2 made quizzes playable (+ the flashcard review remainder, shipped
2026-07-16); M3 added projects/rubrics + the course next-up. M4 closes the spec's
"NotebookLM enrichment in-flow" line: a `notebooklm` material stops being a dead placeholder
note and becomes a **real cross-link into the hub's topic surfaces**, and the `course-builder`
skill's enrichment step becomes a concrete, gated flow that records the link._

## The insight — the enrichment notebook is a real catalog citizen

A course's NotebookLM notebook isn't course-namespaced state: it's an ordinary notebook with an
ordinary sidecar under `$NOTEBOOKLM_ROOT`, so its episodes/study guides/quizzes already have
first-class surfaces at `/topics/<id>`. M4 therefore **joins, never duplicates**: the course
page shows title + counts + an "Open notebook" link, and everything else (listening, guide
reading, quiz taking) happens on the topic page it links to. The "keep courses out of notebook
surfaces" boundary is untouched — this is traffic in the *other* direction.

## Design decisions (don't relitigate)

- **Join at read time in the course-detail endpoint** (`_attach_notebook_refs`), not in the
  manifest layer: one `load_sidecars` per request *only when* a `notebooklm` material carries an
  id, indexed by `notebook_id`, reusing `catalog.build.to_card` for title/urls/counts. Same
  per-request posture as `/api/catalog` itself.
- **Best-effort by contract.** A missing root, unparseable sidecars, or an unknown id can never
  break the course page: no id → no `notebook` ref; unknown id → `{found: false}`; catalog
  trouble → the join silently skips. The UI degrades to the material's `note` — which the skill
  contract now requires to stand alone (the enrichment is local by nature; another machine's
  clone won't resolve the id).
- **Two enrichment paths in the skill, both gated:** *link an existing notebook* (no quota — find
  the id, `cli write` it into the manifest) and *create + generate* (hands off to
  `notebook-init` / `audio-series`, which own the `nlm` mechanics; explicit confirm because it
  spends NotebookLM generation quota). The manifest update always goes through the CLI bridge.
- **Validator stays light:** `notebooklm` has nothing on disk to check; it only *warns* on a
  non-string `notebook_id`. A yet-unlinked material (no id) is a normal authoring state, not a
  warning.

## What shipped

1. **models.py** — `CourseNotebookRef` (`notebook_id`, `found`, `title`, `topic_url`,
   `notebooklm_url`, `counts`); `CourseMaterial.notebook`.
2. **api/courses.py** — `_attach_notebook_refs(course)`, called from `GET /courses/{slug}`
   after the assessment merge.
3. **courses/manifest.py** — the non-string `notebook_id` warning.
4. **frontend** — `CourseNotebookRef` type; `NotebookLmMaterial` card in `CourseDetail.tsx`
   with the three states (linked → Open-notebook button + title + 🎧/📖/❓ count chips + note;
   id-not-found → calm "isn't in this machine's catalog" + note; no id → the note placeholder).
5. **skill** — `course-builder` SKILL.md §5 rewritten as the two-path gated flow;
   `references/contract.md` gains the `notebooklm` section + updated taxonomy row.
6. **tests** — `backend/tests/test_courses_notebooklm.py` (found join incl. counts from a
   synthetic sidecar, not-found degrade, no-id passthrough, missing-root never 500s, validator
   warning both ways); 3 CourseDetail vitest cases for the three render states.

## Live proof (separate from this PR — content, not code)

Kyle's chosen case: a compact course on **"Global Workspace in LLMs — the Jacobian Lens Paper
(Gurnee et al. 2026)"** built via `/build-course`, enriched by **linking the existing
`jlens-workspace` notebook** (`f84dc873-0dc7-407d-9b2a-dbde7eeb66c4` — 8 sources, a 6-episode
audio season, study guide, quiz already generated on 2026-07-11; the *link-existing* path, so
no quota is spent). The course lands under `COURSES_DIR` (gitignored); the verification record
lives in MASTER_PLAN's entry for this milestone.

## Out of scope (M5)

In-hub authoring/regeneration (edit objectives, reorder modules, regenerate a lesson) — breaks
the read-only invariant and needs its own architectural decision. Embedding the audio player or
study-guide reader inside the course page (the topic page owns those). Auto-syncing sidecars
from `nlm` in the hub.
