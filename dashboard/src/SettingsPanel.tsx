import { useEffect, useState } from "react";
import { Check, LoaderCircle, Save } from "lucide-react";
import type { SettingsResponse, WorkbenchSettings } from "./rag";

const groups: { title: string; description: string; fields: (keyof WorkbenchSettings)[] }[] = [
  { title: "Models", description: "Review model changes apply to the next code review. Embedding model changes need a new RAG candidate, but no app rebuild. Download that embedding model explicitly first if it is not cached.", fields: ["provider", "model", "model_temperature", "model_review_output_tokens", "model_extract_output_tokens", "ollama_url", "ollama_context_tokens", "ollama_review_output_tokens", "ollama_extract_output_tokens", "embedding_model", "embedding_revision"] },
  { title: "Langfuse", description: "Turn metadata-only traces on or off. Keys stay in the private .env file; the endpoint is fixed to the EU service.", fields: ["langfuse_enabled", "langfuse_project_id"] },
  { title: "Review limits", description: "Limits apply to the next code review. Source code is never executed.", fields: ["max_files", "max_file_bytes", "max_source_bytes", "max_passages", "max_legal_bytes", "request_seconds", "deadline_seconds"] },
  { title: "Search behavior", description: "These settings affect new RAG candidates. Build a new candidate after changing them.", fields: ["retrieval_limit", "stage_candidates", "max_intents", "max_query_terms", "fusion_k", "exact_reference_boost", "lexical_overlap_weight", "expansion_seed_limit", "expansion_per_seed", "max_query_bytes"] },
  { title: "Evaluation", description: "These settings apply the next time you evaluate cases. The local target is separate from the fixed M1 expert-gold gate.", fields: ["evaluation_k", "evaluation_preview_k", "minimum_holdout_recall"] },
];

const labels: Record<keyof WorkbenchSettings, string> = {
  provider: "Review model provider", model: "Review model name", model_temperature: "Model temperature",
  model_review_output_tokens: "Maximum review answer tokens", model_extract_output_tokens: "Maximum code summary tokens",
  ollama_url: "Local Ollama address", ollama_context_tokens: "Local model context tokens",
  ollama_review_output_tokens: "Local review answer tokens", ollama_extract_output_tokens: "Local code summary tokens",
  embedding_model: "Search embedding model", embedding_revision: "Embedding model version",
  langfuse_enabled: "Send review timing and usage metadata to Langfuse", langfuse_project_id: "Langfuse project ID",
  request_seconds: "Maximum time per model request (seconds)", deadline_seconds: "Maximum time for a full review (seconds)",
  max_query_bytes: "Maximum search query size (bytes)", max_files: "Maximum source files per review",
  max_file_bytes: "Maximum size per source file (bytes)", max_source_bytes: "Maximum source text per review (bytes)",
  max_passages: "Maximum legal passages sent to model", max_legal_bytes: "Maximum legal text sent to model (bytes)",
  retrieval_limit: "Sources returned per search", stage_candidates: "Candidates checked per search stage",
  max_intents: "Search intents per scenario", max_query_terms: "Search terms from each intent", fusion_k: "Search result blend value", exact_reference_boost: "Boost for exact legal references",
  lexical_overlap_weight: "Text overlap weight", expansion_seed_limit: "Search results expanded with nearby text",
  expansion_per_seed: "Nearby passages per result", evaluation_k: "Sources counted for main score",
  evaluation_preview_k: "Sources counted for preview score", minimum_holdout_recall: "Local target recall (0 to 1)",
};

const textFields = new Set<keyof WorkbenchSettings>(["model", "ollama_url", "embedding_model", "embedding_revision", "langfuse_project_id"]);
const booleanFields = new Set<keyof WorkbenchSettings>(["langfuse_enabled"]);
const bounds: Partial<Record<keyof WorkbenchSettings, [number, number, number]>> = {
  model_temperature: [0, 2, 0.1], model_review_output_tokens: [128, 8192, 128], model_extract_output_tokens: [128, 8192, 128],
  ollama_context_tokens: [1024, 32768, 1024], ollama_review_output_tokens: [128, 8192, 128], ollama_extract_output_tokens: [128, 8192, 128],
  request_seconds: [1, 60, 1], deadline_seconds: [1, 120, 1], max_query_bytes: [100, 24000, 100],
  max_files: [1, 50, 1], max_file_bytes: [1000, 1000000, 1000], max_source_bytes: [1000, 100000, 1000],
  max_passages: [1, 20, 1], max_legal_bytes: [1000, 100000, 1000], retrieval_limit: [1, 20, 1],
  stage_candidates: [1, 100, 1], max_intents: [1, 4, 1], max_query_terms: [1, 200, 1], fusion_k: [1, 200, 1],
  exact_reference_boost: [0, 10, 0.1], lexical_overlap_weight: [0, 1, 0.01],
  expansion_seed_limit: [0, 20, 1], expansion_per_seed: [0, 20, 1], evaluation_k: [1, 20, 1],
  evaluation_preview_k: [1, 20, 1], minimum_holdout_recall: [0, 1, 0.01],
};

export default function SettingsPanel({
  response,
  onSave,
}: {
  response: SettingsResponse;
  onSave: (values: WorkbenchSettings) => Promise<SettingsResponse>;
}) {
  const [values, setValues] = useState(response.values);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => setValues(response.values), [response.fingerprint]);
  function update(field: keyof WorkbenchSettings, value: WorkbenchSettings[keyof WorkbenchSettings]) {
    setValues({ ...values, [field]: value });
    setSaved(false);
  }

  async function save() {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const result = await onSave(values);
      setValues(result.values);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Settings could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settings-panel">
      <div className="section-header">
        <div><h2>All workbench settings</h2><p>One place for model, search, review limits, and evaluation targets.</p></div>
        <button className="primary" disabled={busy} onClick={() => void save()}>
          {busy ? <LoaderCircle className="spin" size={15} /> : saved ? <Check size={15} /> : <Save size={15} />}
          {saved ? "Saved" : "Save settings"}
        </button>
      </div>
      <p className="settings-secret-note">
        API keys stay in the private .env file. Gemini key {response.secrets?.gemini_api_key ? "is set" : "is not set"}; Langfuse keys {response.secrets?.langfuse_keys ? "are set" : "are not set"}.
      </p>
      {groups.map((group) => (
        <section className="settings-group" key={group.title}>
          <h3>{group.title}</h3><p>{group.description}</p>
          <div className="settings-grid">
            {group.fields.map((field) => {
              const range = bounds[field];
              return (
                <label key={field}>
                  {labels[field]}
                  {field === "provider" ? (
                    <select value={values.provider} onChange={(e) => update("provider", e.target.value as WorkbenchSettings["provider"])}>
                      <option value="gemini">Gemini</option><option value="ollama">Ollama on this machine</option>
                    </select>
                  ) : booleanFields.has(field) ? (
                    <input className="settings-toggle" type="checkbox" checked={Boolean(values[field])} onChange={(e) => update(field, e.target.checked)} />
                  ) : (
                    <input
                      type={textFields.has(field) ? "text" : "number"}
                      min={range?.[0]} max={range?.[1]} step={range?.[2]}
                      value={textFields.has(field) ? String(values[field]) : Number(values[field])}
                      onChange={(e) => update(field, textFields.has(field) ? e.target.value : Number(e.target.value))}
                    />
                  )}
                </label>
              );
            })}
          </div>
        </section>
      ))}
      {response.fixed_quality_gate && (
        <section className="settings-group fixed-gate">
          <h3>M1 expert quality gate</h3>
          <p>This acceptance standard is fixed: {response.fixed_quality_gate.approved_cases} approved cases, {response.fixed_quality_gate.source_areas} source areas, at least {response.fixed_quality_gate.holdout_recall * 100}% held-out recall, and {response.fixed_quality_gate.critical_cases}. Your local target above does not change this standard.</p>
        </section>
      )}
      {error && <p className="alert error" role="alert">{error}</p>}
      <small className="settings-fingerprint">Settings version: {response.fingerprint.slice(0, 12)}</small>
    </section>
  );
}
