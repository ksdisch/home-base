// The ONE place the API base URL lives. Everything goes through "/api" (Vite proxies it to
// the FastAPI backend in dev). To point elsewhere, set VITE_API_BASE at build time.
import type {
  CatalogResponse,
  HealthResponse,
  TopicDetail,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<HealthResponse>("/health"),
  catalog: () => get<CatalogResponse>("/catalog"),
  topic: (id: string, live = false) =>
    get<TopicDetail>(`/topics/${encodeURIComponent(id)}${live ? "?live=true" : ""}`),
  setEpisodeListened: async (
    notebookId: string,
    artifactId: string,
    listened: boolean,
  ): Promise<boolean> => {
    const res = await fetch(
      `${API_BASE}/topics/${encodeURIComponent(notebookId)}/episodes/${encodeURIComponent(
        artifactId,
      )}/listened`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listened }),
      },
    );
    if (!res.ok) throw new ApiError(res.status, "Could not save progress");
    const body = await res.json();
    return Boolean(body.listened);
  },
};
