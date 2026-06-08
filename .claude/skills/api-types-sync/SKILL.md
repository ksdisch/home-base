---
name: api-types-sync
description: Reconcile the Learning Hub's frontend API types with the backend Pydantic models — bring frontend/src/api/types.ts (and client.ts imports) back in sync with backend/app/models.py and the routers under backend/app/api/. Use when a Pydantic response/request model changed and the TS interfaces need to follow, when types.ts and the backend have drifted, or after adding a new endpoint. Cloud-safe: it only reads backend Python and edits frontend TS, then type-checks. The companion contract-reviewer agent finds drift; this skill fixes it.
---

# api-types-sync

Keep the hand-synced contract honest. `frontend/src/api/types.ts` declares it "Mirrors
backend/app/models.py" — this skill makes that true again after a backend change.

## When to use
- A Pydantic model in `backend/app/models.py` gained/lost/renamed a field, or changed a type.
- A new endpoint was added and the frontend has no interface/method for it.
- `make typecheck` fails, or the contract-reviewer agent reported drift.

## Inputs to read (read-only on the backend)
- `backend/app/models.py` — the source of truth for wire shapes.
- `backend/app/api/*.py` — each route's `response_model=` / request body type, path, and method.
- `frontend/src/api/types.ts` — the interfaces to edit.
- `frontend/src/api/client.ts` — the typed methods + paths (update imports/methods if interfaces
  were added or removed).

## Type mapping (Python → TypeScript)
| Pydantic | TypeScript |
|---|---|
| `str` | `string` |
| `int`, `float` | `number` |
| `bool` | `boolean` |
| `Optional[X]` / field with default | `field?: X \| null` (match the neighbouring fields' style) |
| `List[X]` | `X[]` |
| `Dict[str, V]` | `Record<string, V>` |
| `Literal["a","b"]` / enum | string union, or `string` if siblings use plain `string` |
| nested `BaseModel` | the matching nested interface |
| backend subclass (`class B(A)`) | `interface B extends A` (e.g. `CourseDetail extends CourseSummary`) |

## House style for types.ts (preserve exactly)
- **2-space indent, double quotes, trailing semicolons** (it's Prettier-ish TS).
- Field names are **snake_case on both sides** — do not camelCase.
- Keep the `// Mirrors backend ...` section comments and add one for any new model group.
- Order interfaces to roughly track models.py so diffs stay readable.
- Optional + nullable backend fields are written `name?: T | null` (see existing fields).

## Procedure
1. Identify what changed: `git diff -- backend/app/models.py backend/app/api`. Map each changed
   Pydantic model to its TS interface (and note any with no counterpart yet).
2. Edit `frontend/src/api/types.ts` to match — add/rename/remove fields, fix types & optionality,
   add new interfaces (with a section comment), respect `extends`.
3. If you added or removed an interface that the client uses, update the `import type { ... }`
   block and/or methods in `frontend/src/api/client.ts` (every call goes through `API_BASE`/`/api`).
4. **Preserve the answer-key-free invariant**: never add a correct-answer field to
   `QuizPlayerQuestion` / `QuizPrepareResponse`. The answer key only belongs to the post-grade
   `QuizReviewItem`.
5. Type-check and iterate until clean:
   ```bash
   make typecheck        # = cd frontend && npm run typecheck (tsc --noEmit, strict)
   ```
6. Report the interfaces changed and the typecheck result. If a backend shape can't be expressed
   cleanly in TS (e.g. an ambiguous `Any`/dynamic dict), call it out rather than papering over it
   with `any` — prefer `unknown` and a note (see how `CourseMaterialResponse.data: unknown` is
   handled today).

## Scope
Frontend-only edits + reading backend models. Do **not** change `backend/app/models.py` to match
the frontend — the backend is the source of truth. If the backend is what's wrong, stop and say so.
