import type { Group } from "../api/types";
import { NotebookCard } from "./NotebookCard";

export function GroupSection({ group }: { group: Group }) {
  return (
    <section className="mb-10">
      <div className="mb-3 flex items-baseline gap-3">
        <h2 className="text-lg font-semibold text-ink">{group.label}</h2>
        <span className="text-sm text-muted">{group.notebooks.length}</span>
      </div>

      {group.notebooks.length === 0 ? (
        <p className="rounded-xl border border-dashed border-stone-200 bg-white/50 px-4 py-6 text-sm text-muted">
          Nothing here yet.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {group.notebooks.map((nb) => (
            <NotebookCard key={nb.notebook_id} card={nb} />
          ))}
        </div>
      )}
    </section>
  );
}
