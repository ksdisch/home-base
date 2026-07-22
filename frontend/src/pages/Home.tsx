import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CatalogResponse } from "../api/types";
import { Banner } from "../components/Banner";
import { CustomTopicsSection } from "../components/CustomTopicsSection";
import { GroupSection } from "../components/GroupSection";

export default function Home() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .catalog()
      .then((c) => alive && setCatalog(c))
      .catch((e) => alive && setError(e.message ?? "Failed to load catalog"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const total =
    catalog?.groups.reduce((acc, g) => acc + g.notebooks.length, 0) ?? 0;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Your topics</h1>
        <p className="mt-1 text-sm text-muted">
          {loading
            ? "Reading your notebooks…"
            : `${total} notebooks, read live from your NotebookLM sidecars.`}
        </p>
      </div>

      {error && (
        <div className="mb-6">
          <Banner tone="warning" title="Couldn't load your catalog">
            {error}
          </Banner>
        </div>
      )}

      {catalog && !catalog.auth.ok && catalog.auth.message && (
        <div className="mb-6">
          <Banner tone="warning" title="NotebookLM sign-in needed">
            {catalog.auth.message}
          </Banner>
        </div>
      )}

      {loading && !catalog && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-36 animate-pulse rounded-2xl border border-line bg-card/60"
            />
          ))}
        </div>
      )}

      {catalog && catalog.groups.map((g) => <GroupSection key={g.key} group={g} />)}

      {/* Custom (non-NotebookLM) topics — their own section, fed by /api/custom-topics. */}
      {catalog && <CustomTopicsSection />}
    </div>
  );
}
