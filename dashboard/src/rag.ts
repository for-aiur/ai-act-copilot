export type Domain = {
  id: string;
  name: string;
  description: string;
  reference_hint: string;
  active: string | null;
};
export type Doc = {
  id: string;
  title: string;
  text: string;
  source_url: string;
  kind: string;
  checksum: string;
  metadata: {
    origin: string;
    binding: boolean | null;
    celex: string | null;
    publication_date: string | null;
    entry_into_force: string | null;
    applicability_date: string | null;
    applicability_rules: {
      condition: string;
      date: string;
      quote: string;
      source_id: string;
    }[];
  };
};
export type Library = {
  domain_id: string;
  snapshot_id: string;
  source_version: string;
  complete: boolean;
  total: number;
  chunk_count: number;
  source_count: number;
  scope_limits: string[];
  kinds: string[];
  documents: Doc[];
  chunks: { id: string; document_id: string; title: string; text: string }[];
};
export type RRequest = {
  domain_id: string;
  scenario: string;
  context: {
    actor_role: string;
    deployment: string;
    constraints: string;
    language: "en";
  };
  intents: string[];
  kinds: string[];
  limit: number;
};
export type Candidate = {
  document: Doc;
  chunk: {
    id: string;
    text: string;
    start: number;
    end: number;
    references: string[];
  };
  rank: number;
  scores: Record<string, number>;
  paths: string[];
};
export type Stage = {
  chunk_id: string;
  document_id: string;
  text: string;
  rank: number;
  score: number;
  reason: string;
};
export type Result = {
  request: RRequest;
  context_fingerprint: string;
  snapshot_id: string;
  rag_release_id: string;
  candidates: Candidate[];
  stages: Record<string, Stage[]>;
  elapsed_ms: number;
  warnings: string[];
};
export type Run = { id: string; result: Result };
export type Label = {
  document_id: string;
  chunk_id?: string | null;
  label: "must_retrieve" | "relevant" | "not_relevant" | "uncertain";
  rationale: string;
};
export type Case = {
  id: string;
  title: string;
  request: RRequest;
  snapshot_id: string;
  rag_release_id: string;
  labels: Label[];
  author: string;
  origin: "human" | "model_draft";
  status: "draft" | "approved";
  approved_by: string | null;
  split: "development" | "holdout" | "critical";
  area: string;
  code_fixture?: { filename: string; text: string } | null;
  holdout_sealed: boolean;
  revision: number;
};
export type Manifest = {
  rag_release_id: string;
  domain_id: string;
  snapshot_id: string;
  source_version: string;
  mode: string;
  embedding: { model: string; revision: string; dimension: number };
  quality_status: string;
  git_revision: string;
  removal_blockers?: string[];
  equivalent_to?: string | null;
  compatible?: boolean;
  compatibility_reason?: string | null;
};
export type Versions = {
  active: string | null;
  previous: string | null;
  releases: Manifest[];
  provider: string;
  model: string;
  cloud_key_configured: boolean;
  tracing_enabled: boolean;
  active_compatible?: boolean;
};
export type Evaluation = {
  id: string;
  rag_release_id: string;
  summary: {
    cases: number;
    recall: number | null;
    mean_precision: number | null;
    mean_mrr: number | null;
    mean_ndcg: number | null;
    missing_required: number;
    false_positives: number;
  };
  summary_at_preview?: { recall: number | null };
  experiment_gate?: { status: string; target_recall: number; actual_recall: number | null; cases: number; note: string };
  configuration?: { fingerprint: string; values: Record<string, unknown>; evaluation_k: number; preview_k: number };
  quality_gate: { status: string; reasons: string[] };
  scores: {
    case_id: string;
    recall: number | null;
    missed_required: string[];
    false_positives: string[];
  }[];
};
export type WorkbenchSettings = {
  provider: "gemini" | "ollama";
  model: string;
  model_temperature: number;
  model_review_output_tokens: number;
  model_extract_output_tokens: number;
  ollama_url: string;
  ollama_context_tokens: number;
  ollama_review_output_tokens: number;
  ollama_extract_output_tokens: number;
  embedding_model: string;
  embedding_revision: string;
  langfuse_enabled: boolean;
  langfuse_project_id: string;
  request_seconds: number;
  deadline_seconds: number;
  max_query_bytes: number;
  max_files: number;
  max_file_bytes: number;
  max_source_bytes: number;
  max_passages: number;
  max_legal_bytes: number;
  retrieval_limit: number;
  stage_candidates: number;
  max_intents: number;
  max_query_terms: number;
  fusion_k: number;
  exact_reference_boost: number;
  lexical_overlap_weight: number;
  expansion_seed_limit: number;
  expansion_per_seed: number;
  evaluation_k: number;
  evaluation_preview_k: number;
  minimum_holdout_recall: number;
};
export type SettingsResponse = {
  values: WorkbenchSettings;
  fingerprint: string;
  saved: boolean;
  secrets?: { gemini_api_key: boolean; langfuse_keys: boolean };
  fixed_quality_gate?: { approved_cases: number; source_areas: number; holdout_recall: number; critical_cases: string };
};
