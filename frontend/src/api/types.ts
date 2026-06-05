// Mirrors backend/app/models.py — the backend↔frontend contract.

export interface AuthState {
  ok: boolean;
  message?: string | null;
}

export interface Episode {
  n?: number | null;
  title: string;
  artifact_id: string;
  fmt?: string | null;
  length?: string | null;
  status?: string | null;
  listened: boolean;
  source: string;
}

export interface ArtifactRef {
  n?: number | null;
  title: string;
  artifact_id: string;
  type: string;
  status?: string | null;
  source: string;
}

export interface QuizRef extends ArtifactRef {
  takeable: boolean;
}

export interface NotebookCard {
  notebook_id: string;
  alias: string;
  title: string;
  group: string;
  group_label: string;
  template?: string | null;
  tags: string[];
  archived: boolean;
  notebooklm_url: string;
  topic_url: string;
  counts: Record<string, number>;
  progress_pct?: number | null;
  mastery?: number | null;
  due_for_review: boolean;
  last_touched?: string | null;
}

export interface Group {
  key: string;
  label: string;
  notebooks: NotebookCard[];
}

export interface CatalogResponse {
  generated_at: string;
  groups: Group[];
  auth: AuthState;
  warnings: string[];
  notebooklm_root: string;
}

export interface TopicDetail {
  notebook_id: string;
  alias: string;
  title: string;
  group: string;
  group_label: string;
  template?: string | null;
  tags: string[];
  archived: boolean;
  merged_into?: string | null;
  source_count?: number | null;
  notebooklm_url: string;
  episodes: Episode[];
  standalones: Episode[];
  study_guides: ArtifactRef[];
  quizzes: QuizRef[];
  other_artifacts: ArtifactRef[];
  counts: Record<string, number>;
  auth: AuthState;
  live: boolean;
  warnings: string[];
}

export interface HealthResponse {
  ok: boolean;
  nlm_available: boolean;
  nlm_version?: string | null;
  notebooklm_root: string;
  root_exists: boolean;
}
