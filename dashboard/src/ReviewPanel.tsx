import { useEffect, useRef, useState } from "react";
import { ExternalLink, LoaderCircle, Play, ShieldCheck } from "lucide-react";
import { request } from "./api";
import type { Result, Versions } from "./rag";
import type { ScanResult } from "../../extensions/vscode/src/contracts";

type Review = {
  id: string;
  scan_result: ScanResult;
  rag_release_id: string;
  trace_id: string;
  trace_url: string | null;
  understanding: {
    ai_use: string;
    purpose: string;
    facts: { evidence_id: string; fact: string }[];
    unknowns: string[];
    retrieval_intents: string[];
  } | null;
  retrieval: Result | null;
  review_passages: { id: string; title: string; text: string; url: string }[];
  usage: Record<string, number> | null;
  steps: { stage: string; elapsed_ms: number; status: string }[];
};

export default function ReviewPanel({
  versions,
  context,
}: {
  versions: Versions | null;
  context: string;
}) {
  const [code, setCode] = useState(
    "def rank_applicants(model, candidates):\n    return model.predict(candidates)\n",
  );
  const [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [result, setResult] = useState<Review | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++;
    setConsent(false);
    setResult(null);
    setError("");
  }, [code, context, versions?.active, versions?.provider, versions?.model]);
  const cloud = versions?.provider === "gemini";
  async function review() {
    const current = ++generation.current;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await request<Review>("/api/rag/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          filename: "review.py",
          context,
          cloud_consent: consent,
        }),
      });
      if (current === generation.current) setResult(response);
    } catch (e) {
      if (current === generation.current)
        setError(e instanceof Error ? e.message : "Review unavailable.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="annotation-panel">
      <div className="section-header">
        <div>
          <h2>
            Grounded Python review <span>Optional inference</span>
          </h2>
          <p>
            {cloud
              ? "Gemini receives the selected code, context and retrieved official passages."
              : "Ollama runs locally without a cloud fallback."}
          </p>
        </div>
        <span className="draft-pill">
          {versions?.model || "PROVIDER SETUP"}
        </span>
      </div>
      <div className="review-input">
        <label>
          Python source
          <textarea
            aria-label="Python source"
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
              setResult(null);
            }}
            spellCheck={false}
            maxLength={24000}
            rows={8}
          />
        </label>
        <p>
          The initial snippet is synthetic. Scanned code is never executed.
          Saving a review retains its evidence and result locally.
        </p>
        {cloud && (
          <label className="cloud-consent">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            I allow this code and the current scenario context to be sent to
            Google for this review.
          </label>
        )}
        {cloud && !versions?.cloud_key_configured && (
          <div className="trace-note">
            Set GEMINI_API_KEY in the private .env file and restart the API. Do
            not paste keys into this page.
          </div>
        )}
        <button
          className="primary"
          disabled={
            busy ||
            !code.trim() ||
            !versions?.active ||
            (cloud && (!consent || !versions.cloud_key_configured))
          }
          onClick={() => void review()}
        >
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Play size={16} />
          )}
          Review & save result locally
        </button>
      </div>
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {result && (
        <div className="review-output">
          <h3>Review {result.scan_result.status}</h3>
          <p className="trace-note">
            RAG {result.rag_release_id.slice(0, 12)} ·{" "}
            {result.scan_result.metadata.elapsed_ms} ms · Zero findings does not
            certify compliance.
          </p>
          {result.scan_result.errors.map((e, i) => (
            <div className="alert error" key={i}>
              {e.code}: {e.message}
            </div>
          ))}
          {result.scan_result.findings.map((f) => (
            <article className="review-finding" key={f.id}>
              <span className="draft-pill">
                {f.kind === "context_question"
                  ? "NEEDS CONTEXT"
                  : "POTENTIAL CONCERN"}{" "}
                · {f.priority}
              </span>
              <h3>{f.title}</h3>
              <p>{f.explanation}</p>
              <pre>
                {f.evidence.path}:{f.evidence.start_line}-{f.evidence.end_line}
                {"\n"}
                {f.evidence.quote}
              </pre>
              {f.citations.map((c) => (
                <blockquote key={c.section_id + c.quote}>
                  <p>{c.quote}</p>
                  <a href={c.url} target="_blank" rel="noreferrer">
                    {c.section_id}
                    <ExternalLink size={12} />
                  </a>
                </blockquote>
              ))}
              <p>
                <strong>Next action:</strong> {f.suggested_next_action}
              </p>
              <p className="context-question">{f.context_question}</p>
            </article>
          ))}
          {result.understanding && (
            <details className="review-debug">
              <summary>Extracted purpose, facts and search intents</summary>
              <h4>{result.understanding.purpose}</h4>
              <p>AI use: {result.understanding.ai_use}</p>
              <ul>
                {result.understanding.facts.map((f) => (
                  <li key={f.evidence_id + f.fact}>
                    {f.evidence_id}: {f.fact}
                  </li>
                ))}
              </ul>
              <h4>Unknowns</h4>
              <ul>
                {result.understanding.unknowns.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
              <h4>Retrieval intents</h4>
              <ol>
                {result.understanding.retrieval_intents.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ol>
            </details>
          )}
          {result.retrieval && (
            <details className="review-debug">
              <summary>Actual retrieval stages and candidates</summary>
              <p>
                Source {result.retrieval.snapshot_id} · Context{" "}
                {result.retrieval.context_fingerprint}
              </p>
              {Object.entries(result.retrieval.stages).map(([stage, hits]) => (
                <details key={stage}>
                  <summary>
                    {stage}: {hits.length} candidates
                  </summary>
                  {hits.map((h) => (
                    <article key={h.chunk_id}>
                      <strong>
                        #{h.rank} {h.chunk_id} · {h.score.toFixed(5)}
                      </strong>
                      <p>{h.reason}</p>
                      <blockquote>{h.text}</blockquote>
                    </article>
                  ))}
                </details>
              ))}
            </details>
          )}
          <details className="review-debug">
            <summary>
              Exact passages sent to the review model (
              {result.review_passages.length})
            </summary>
            {result.review_passages.map((p) => (
              <article key={p.id}>
                <h4>
                  {p.title} · {p.id}
                </h4>
                <blockquote>{p.text}</blockquote>
                <a href={p.url} target="_blank" rel="noreferrer">
                  Open official source
                  <ExternalLink size={12} />
                </a>
              </article>
            ))}
          </details>
          <details className="review-debug">
            <summary>Coverage, model and prompt provenance</summary>
            <pre>
              {JSON.stringify(
                {
                  coverage: result.scan_result.coverage,
                  metadata: result.scan_result.metadata,
                  usage: result.usage,
                  budgets: {
                    source_bytes: 24000,
                    legal_bytes: 12000,
                    passages: 6,
                    findings: 4,
                    request_seconds: 60,
                    deadline_seconds: 120,
                  },
                },
                null,
                2,
              )}
            </pre>
          </details>
          <div className="stage-strip">
            {result.steps.map((s, i) => (
              <span key={i}>
                {s.stage}: {s.elapsed_ms} ms · {s.status}
              </span>
            ))}
          </div>
          {result.trace_url && (
            <a
              className="official-link"
              href={result.trace_url}
              target="_blank"
              rel="noreferrer"
            >
              <ShieldCheck size={14} />
              Open metadata-only Langfuse trace
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      )}
    </section>
  );
}
