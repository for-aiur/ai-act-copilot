import ReviewPanel from "./ReviewPanel";
import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Database,
  ExternalLink,
  FileText,
  FlaskConical,
  GitCompareArrows,
  Layers3,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { request } from "./api";
import type {
  Case,
  Doc,
  Domain,
  Evaluation,
  Label,
  Library,
  Manifest,
  Result,
  RRequest,
  Run,
  Versions,
} from "./rag";

const targetOf = (label: Label) => label.chunk_id || label.document_id;

type View = "corpus" | "studio" | "cases" | "versions" | "compare";
const names: Record<View, string> = {
  corpus: "Source explorer",
  studio: "Retrieval studio",
  cases: "Evaluation cases",
  versions: "RAG versions",
  compare: "Compare runs",
};
const short = (v: string) => v.slice(0, 12);
function download(name: string, value: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
const post = <T,>(url: string, body?: unknown) =>
  request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export default function Workbench() {
  const [view, setView] = useState<View>("corpus");
  const [domains, setDomains] = useState<Domain[]>([]);
  const [domain, setDomain] = useState("ai-act");
  const [library, setLibrary] = useState<Library | null>(null);
  const [versions, setVersions] = useState<Versions | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [query, setQuery] = useState(""),
    [kind, setKind] = useState("");
  const [selected, setSelected] = useState<Doc | null>(null);
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [scenario, setScenario] = useState(""),
    [actor, setActor] = useState(""),
    [deployment, setDeployment] = useState(""),
    [constraints, setConstraints] = useState("");
  const [run, setRun] = useState<Run | null>(null),
    [stage, setStage] = useState("final");
  const [labels, setLabels] = useState<Record<string, Label>>({});
  const [title, setTitle] = useState(""),
    [author, setAuthor] = useState(""),
    [area, setArea] = useState(""),
    [split, setSplit] = useState<Case["split"]>("development");
  const [editing, setEditing] = useState<Case | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [downloadModel, setDownloadModel] = useState(false),
    [lexicalOnly, setLexicalOnly] = useState(false);
  const [left, setLeft] = useState(""),
    [right, setRight] = useState("");
  const sequence = useRef(0);
  const [targetChunk, setTargetChunk] = useState("");
  const openingCase = useRef<Case | null>(null);
  const selectedDomain = domains.find((d) => d.id === domain);
  const docs = (library?.documents || []).filter(
    (d) =>
      (!kind || d.kind === kind) &&
      query
        .toLowerCase()
        .split(/\s+/)
        .every((w) =>
          (d.title + " " + d.id + " " + d.text).toLowerCase().includes(w),
        ),
  );
  docs.sort(
    (a, b) =>
      Number(b.title.toLowerCase().startsWith(query.trim().toLowerCase())) -
      Number(a.title.toLowerCase().startsWith(query.trim().toLowerCase())),
  );
  const active =
    selected && docs.some((d) => d.id === selected.id) ? selected : docs[0];
  const input: RRequest = {
    domain_id: domain,
    scenario,
    context: { actor_role: actor, deployment, constraints, language: "en" },
    intents: [],
    kinds: [],
    limit: 10,
  };
  useEffect(() => {
    setTargetChunk("");
  }, [active?.id]);
  async function refresh() {
    const [v, c, r] = await Promise.all([
      request<Versions>("/api/rag/versions?domain=" + domain),
      request<Case[]>("/api/rag/cases?domain=" + domain),
      request<{ id: string; payload: Result }[]>(
        "/api/rag/runs?domain=" + domain,
      ),
    ]);
    setVersions(v);
    setCases(c);
    setRuns(r.map((row) => ({ id: row.id, result: row.payload })));
  }
  useEffect(() => {
    request<Domain[]>("/api/rag/domains")
      .then(setDomains)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    let cancelled = false;
    setLibrary(null);
    setSelected(null);
    setQuery("");
    setKind("");
    setRun(null);
    setLabels({});
    setEditing(null);
    setEvaluation(null);
    setVersions(null);
    setError("");
    Promise.all([
      request<Library>("/api/rag/library?domain=" + domain),
      request<Versions>("/api/rag/versions?domain=" + domain),
      request<Case[]>("/api/rag/cases?domain=" + domain),
      request<{ id: string; payload: Result }[]>(
        "/api/rag/runs?domain=" + domain,
      ),
    ])
      .then(([lib, v, c, r]) => {
        if (!cancelled) {
          setLibrary(lib);
          setVersions(v);
          setCases(c);
          setRuns(r.map((row) => ({ id: row.id, result: row.payload })));
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [domain]);
  useEffect(() => {
    sequence.current++;
    setRun(null);
    setEvaluation(null);
    const c = openingCase.current;
    openingCase.current = null;
    if (c) {
      setLabels(Object.fromEntries(c.labels.map((l) => [targetOf(l), l])));
      setEditing(c);
    } else {
      setLabels({});
      setEditing(null);
    }
  }, [scenario, actor, deployment, constraints, domain]);
  async function act(name: string, fn: () => Promise<void>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "The operation failed. Check the local API.",
      );
    } finally {
      setBusy("");
    }
  }
  function addLabel(
    doc: Doc,
    label: Label["label"] = "must_retrieve",
    chunkId?: string,
  ) {
    const key = chunkId || doc.id;
    setLabels((old) => {
      const next = Object.fromEntries(
        Object.entries(old).filter(
          ([, item]) =>
            item.document_id !== doc.id ||
            Boolean(item.chunk_id) === Boolean(chunkId),
        ),
      );
      return {
        ...next,
        [key]: old[key] || {
          document_id: doc.id,
          chunk_id: chunkId || null,
          label,
          rationale: "",
        },
      };
    });
    setNotice((chunkId || doc.title) + " added to source expectations.");
    setView("studio");
  }
  async function retrieve() {
    const id = ++sequence.current;
    await act("retrieval", async () => {
      const r = await post<Run>("/api/rag/retrieve", input);
      if (sequence.current === id) {
        setRun(r);
        setStage("final");
        await refresh();
      }
    });
  }
  async function saveCase() {
    if (!run) return;
    await act("save", async () => {
      const value: Case = {
        id: editing?.id || crypto.randomUUID(),
        title: title.trim() || scenario.slice(0, 80),
        request: run.result.request,
        snapshot_id: run.result.snapshot_id,
        rag_release_id: run.result.rag_release_id,
        labels: Object.values(labels),
        author: author.trim(),
        origin: editing?.origin || "human",
        status: "draft",
        approved_by: null,
        split,
        area: area.trim() || "unspecified",
        holdout_sealed: false,
        revision: editing ? editing.revision + 1 : 1,
      };
      const saved = await post<Case>("/api/rag/cases", value);
      setEditing(saved);
      await refresh();
      setNotice(
        "Draft revision saved with its exact context and source versions.",
      );
      setView("cases");
    });
  }
  function openCase(c: Case) {
    openingCase.current =
      scenario !== c.request.scenario ||
      actor !== c.request.context.actor_role ||
      deployment !== c.request.context.deployment ||
      constraints !== c.request.context.constraints
        ? c
        : null;
    setScenario(c.request.scenario);
    setActor(c.request.context.actor_role);
    setDeployment(c.request.context.deployment);
    setConstraints(c.request.context.constraints);
    setTitle(c.title);
    setAuthor(c.author);
    setArea(c.area);
    setSplit(c.split);
    setRun(null);
    setLabels(Object.fromEntries(c.labels.map((l) => [targetOf(l), l])));
    setEditing(c);
    setView("studio");
    setNotice("Case opened. Run retrieval again before saving a new revision.");
  }
  const selectedResults =
    stage === "final"
      ? run?.result.candidates
      : run?.result.stages[stage]?.map((h) => ({
          rank: h.rank,
          chunk: { id: h.chunk_id, text: h.text },
          document: library?.documents.find((d) => h.document_id === d.id),
          scores: { [stage]: h.score },
        }));
  const a = runs.find((r) => r.id === left),
    b = runs.find((r) => r.id === right);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="AI Act Copilot home">
          <span className="brand-mark">
            <Layers3 size={24} />
          </span>
          <span>
            AI Act Copilot<small>EVROS LABS</small>
          </span>
        </a>
        <div className="workspace-label">
          RETRIEVAL WORKSPACE<span>M1</span>
        </div>
        <nav aria-label="Workbench">
          {(
            [
              ["corpus", BookOpen],
              ["studio", FlaskConical],
              ["cases", FileText],
              ["compare", GitCompareArrows],
              ["versions", Layers3],
            ] as const
          ).map(([v, Icon]) => (
            <button
              key={v}
              aria-label={names[v]}
              className={"nav-item " + (view === v ? "active" : "")}
              onClick={() => setView(v)}
            >
              <Icon size={18} />
              {names[v]}
              {v === "corpus" && <span>{library?.total || "…"}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">EVERY RESULT HAS A SOURCE</span>
          <p>Inspect the path from scenario to evidence.</p>
          <div>
            <span className="tiny-dot" />
            Local tooling · Quality under review
          </div>
        </div>
        <div className="sidebar-bottom">
          <span className="avatar">EL</span>
          <div>
            Retrieval workbench
            <small>Local embeddings · Explicit cloud consent</small>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            Workspace
            <ChevronRight size={14} />
            <strong>{names[view]}</strong>
          </div>
          <span className="local-badge">
            <span className="tiny-dot" />
            LOCAL ONLY
          </span>
        </header>
        <div className="page">
          <div className="page-heading">
            <div>
              <div className="eyebrow green">RETRIEVAL WORKBENCH</div>
              <h1>
                {view === "corpus"
                  ? "Start with the source."
                  : view === "studio"
                    ? "Make retrieval visible."
                    : view === "cases"
                      ? "Turn questions into tests."
                      : view === "versions"
                        ? "Know exactly what changed."
                        : "Compare the evidence."}
              </h1>
              <p>
                Versioned sources. Inspectable retrieval. Context that stays
                attached.
              </p>
            </div>
            <select
              className="domain-select"
              aria-label="Knowledge domain"
              value={domain}
              disabled={!!busy}
              onChange={(e) => setDomain(e.target.value)}
            >
              {domains.map((d) => (
                <option value={d.id} key={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <CircleHelp size={18} />
              <span>{error}</span>
              <button onClick={() => window.location.reload()}>
                <RefreshCw size={15} />
                Reload
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={17} />
              <span>{notice}</span>
              <button
                aria-label="Dismiss message"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <section className="stats" aria-label="Source status">
            <div>
              <span className="stat-icon">
                <Database size={19} />
              </span>
              <div>
                <span>Source documents</span>
                <strong>
                  {library?.total ?? "…"}
                  <small>{selectedDomain?.name}</small>
                </strong>
              </div>
            </div>
            <div>
              <span className="stat-icon">
                <Layers3 size={19} />
              </span>
              <div>
                <span>Indexable passages</span>
                <strong>
                  {library?.chunk_count ?? "…"}
                  <small>Exact source offsets</small>
                </strong>
              </div>
            </div>
            <div>
              <span className="stat-icon">
                <ShieldCheck size={19} />
              </span>
              <div>
                <span>Source snapshot</span>
                <strong className="status-text">
                  {library ? short(library.snapshot_id) : "Loading…"}
                </strong>
                <small>
                  {versions?.active
                    ? "Active " + short(versions.active)
                    : "Build not activated"}
                </small>
              </div>
            </div>
          </section>
          <div className="coverage-note">
            <CircleHelp size={17} />
            <span>
              {library?.complete
                ? "Pinned source inventory is complete."
                : "Checking source coverage."}{" "}
              Retrieval quality is not yet expert-approved.
            </span>
            <button onClick={() => setView("versions")}>
              Versions & setup
              <ArrowRight size={14} />
            </button>
          </div>
          {view === "corpus" && (
            <section className="explorer">
              <div className="section-header">
                <div>
                  <h2>
                    Source library <span>{selectedDomain?.name}</span>
                  </h2>
                  <p>
                    Find a source, inspect its wording, or add an expected
                    retrieval target.
                  </p>
                </div>
                <span className="quiet-label">PINNED · ENGLISH</span>
              </div>
              <div className="library-toolbar">
                <label className="search">
                  <Search size={18} />
                  <input
                    aria-label="Search sources"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={
                      selectedDomain?.reference_hint || "Search documents…"
                    }
                  />
                  {query && (
                    <button
                      aria-label="Clear search"
                      onClick={() => setQuery("")}
                    >
                      <X size={15} />
                    </button>
                  )}
                </label>
                <select
                  aria-label="Document type"
                  value={kind}
                  onChange={(e) => setKind(e.target.value)}
                >
                  <option value="">All source types</option>
                  {library?.kinds.map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </div>
              {!library ? (
                <Empty
                  title="Loading source library"
                  text="Checking the pinned source pack."
                />
              ) : (
                <div className="library-body">
                  <div className="source-list">
                    <div className="list-caption">
                      {docs.length} DOCUMENTS<span>REFERENCE</span>
                    </div>
                    {!docs.length ? (
                      <Empty
                        title="No matching documents"
                        text="Try a different reference or keyword."
                      />
                    ) : (
                      docs.map((d) => (
                        <button
                          className={
                            "source-row " +
                            (active?.id === d.id ? "selected" : "")
                          }
                          key={d.id}
                          onClick={() => setSelected(d)}
                        >
                          <span className="doc-icon">
                            <FileText size={18} />
                          </span>
                          <div>
                            <strong>{d.title}</strong>
                            <p>{d.text}</p>
                            <span>
                              {d.kind}
                              <i />
                              {d.metadata.binding === false
                                ? "Explanatory source"
                                : "Source text"}
                            </span>
                          </div>
                          <ChevronRight size={16} />
                        </button>
                      ))
                    )}
                  </div>
                  <article className="source-detail">
                    {active ? (
                      <>
                        <div className="detail-kicker">
                          <span className="green-pill">
                            {active.kind.toUpperCase()}
                          </span>
                          <span className="quiet-label">
                            EXACT NORMALIZED WORDING
                          </span>
                        </div>
                        <h2>{active.title}</h2>
                        <div className="detail-meta">
                          {active.metadata.origin} ·{" "}
                          {active.metadata.celex ||
                            "Authored technical fixture"}
                        </div>
                        <select
                          aria-label="Target passage"
                          className="passage-select"
                          value={targetChunk}
                          onChange={(e) => setTargetChunk(e.target.value)}
                        >
                          <option value="">Entire source document</option>
                          {library?.chunks
                            .filter((c) => c.document_id === active.id)
                            .map((c) => (
                              <option value={c.id} key={c.id}>
                                {c.id}
                              </option>
                            ))}
                        </select>
                        <div className="source-text">
                          {targetChunk
                            ? library?.chunks.find((c) => c.id === targetChunk)
                                ?.text
                            : active.text}
                        </div>
                        <a
                          className="official-link"
                          href={active.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open source
                          <ExternalLink size={15} />
                        </a>
                        <div className="detail-facts">
                          <div>
                            <span>Applicability</span>
                            <strong>
                              {active.metadata.applicability_date ||
                                "Conditional or unknown"}
                            </strong>
                          </div>
                          <div>
                            <span>Publication</span>
                            <strong>
                              {active.metadata.publication_date ||
                                "Not specified"}
                            </strong>
                          </div>
                          <div>
                            <span>Source ID</span>
                            <strong className="mono">{active.id}</strong>
                          </div>
                        </div>
                        {active.metadata.applicability_rules?.length > 0 && (
                          <details className="date-rules">
                            <summary>Conditional application rules</summary>
                            {active.metadata.applicability_rules.map((r) => (
                              <p key={r.date}>
                                <strong>{r.date}</strong> {r.condition}
                                <br />
                                <small>Source: {r.source_id}</small>
                              </p>
                            ))}
                          </details>
                        )}
                        <div className="source-action">
                          <div>
                            <h3>Missing from a retrieval run?</h3>
                            <p>
                              Add it as an expected source, even if it was not
                              found.
                            </p>
                          </div>
                          <button
                            className="secondary"
                            onClick={() =>
                              addLabel(
                                active,
                                "must_retrieve",
                                targetChunk || undefined,
                              )
                            }
                          >
                            <Plus size={15} />
                            Expect source
                          </button>
                        </div>
                      </>
                    ) : (
                      <Empty
                        title="Select a source"
                        text="Its text and provenance will appear here."
                      />
                    )}
                  </article>
                </div>
              )}
            </section>
          )}
          {view === "studio" && (
            <>
              <section className="studio">
                <div className="scenario-form">
                  <div className="section-header">
                    <div>
                      <h2>Scenario & context</h2>
                      <p>Changing context invalidates the displayed run.</p>
                    </div>
                    <span className="draft-pill">LOCAL RETRIEVAL</span>
                  </div>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void retrieve();
                    }}
                  >
                    <label>
                      Intended use
                      <textarea
                        required
                        rows={4}
                        maxLength={12000}
                        value={scenario}
                        onChange={(e) => setScenario(e.target.value)}
                        placeholder="What does the system do, for whom, and why?"
                      />
                    </label>
                    <div className="field-grid">
                      <label>
                        Actor role
                        <input
                          maxLength={500}
                          value={actor}
                          onChange={(e) => setActor(e.target.value)}
                          placeholder="e.g. provider, deployer"
                        />
                      </label>
                      <label>
                        Deployment setting
                        <input
                          maxLength={2000}
                          value={deployment}
                          onChange={(e) => setDeployment(e.target.value)}
                          placeholder="e.g. employment, public services"
                        />
                      </label>
                    </div>
                    <label>
                      Constraints and unknowns
                      <textarea
                        rows={2}
                        maxLength={2000}
                        value={constraints}
                        onChange={(e) => setConstraints(e.target.value)}
                        placeholder="Known exceptions, missing facts, intended boundaries…"
                      />
                    </label>
                    <div className="form-footer">
                      <span>
                        <ShieldCheck size={15} />
                        Query embedding runs on this machine
                      </span>
                      <button
                        className="primary"
                        disabled={
                          !!busy || !scenario.trim() || !versions?.active
                        }
                      >
                        {busy === "retrieval" ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : (
                          <Play size={16} />
                        )}
                        Run retrieval
                      </button>
                    </div>
                  </form>
                </div>
                <aside className="scenario-aside">
                  <h3>A useful starting point</h3>
                  <p>Editable prompts, not approved evaluation cases.</p>
                  {(domain === "ai-act"
                    ? [
                        [
                          "Applicant ranking",
                          "An employer uses AI to rank applicants and create a recruitment shortlist.",
                        ],
                        [
                          "Public service eligibility",
                          "A public authority uses an AI system to evaluate eligibility for essential public assistance benefits.",
                        ],
                        [
                          "Model documentation",
                          "A provider distributes a general-purpose AI model and needs technical documentation.",
                        ],
                      ]
                    : [
                        [
                          "Readiness checks",
                          "Which endpoint checks corpus and database readiness without inference?",
                        ],
                        [
                          "Draft persistence",
                          "How are scenario drafts saved and listed without approving a golden test?",
                        ],
                      ]
                  ).map(([name, text]) => (
                    <button
                      className="sample"
                      key={name}
                      onClick={() => setScenario(text)}
                    >
                      <FlaskConical size={16} />
                      <span>{name}</span>
                      <ArrowRight size={14} />
                    </button>
                  ))}
                  {!versions?.active && (
                    <div className="references">
                      <p>
                        Build and activate a local RAG candidate before running
                        retrieval.
                      </p>
                      <button
                        className="secondary"
                        onClick={() => setView("versions")}
                      >
                        Open setup
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </aside>
              </section>
              {run && (
                <section className="results-panel">
                  <div className="section-header">
                    <div>
                      <h2>
                        Retrieval trace <span>{run.result.elapsed_ms} ms</span>
                      </h2>
                      <p>
                        Run {short(run.id)} · RAG{" "}
                        {short(run.result.rag_release_id)} · Context{" "}
                        {short(run.result.context_fingerprint)}
                      </p>
                    </div>
                    <select
                      aria-label="Retrieval stage"
                      value={stage}
                      onChange={(e) => setStage(e.target.value)}
                    >
                      {["final", ...Object.keys(run.result.stages)].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div className="stage-strip">
                    {Object.entries(run.result.stages).map(([s, hits]) => (
                      <button
                        key={s}
                        className={stage === s ? "selected" : ""}
                        onClick={() => setStage(s)}
                      >
                        {s}
                        <strong>{hits.length}</strong>
                      </button>
                    ))}
                  </div>
                  {selectedResults?.map((c, index) => (
                    <div className="candidate" key={c.chunk.id + "-" + index}>
                      <div className="rank">{c.rank}</div>
                      <div>
                        <h3>{c.document?.title || c.chunk.id}</h3>
                        <p>{c.chunk.text}</p>
                        <div className="score-line">
                          {Object.entries(c.scores).map(([k, v]) => (
                            <span key={k}>
                              {k}: {v.toFixed(5)}
                            </span>
                          ))}
                        </div>
                        {c.document && (
                          <div className="candidate-actions">
                            <a
                              href={c.document.source_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Source
                              <ExternalLink size={12} />
                            </a>
                            <button
                              onClick={() =>
                                addLabel(c.document!, "relevant", c.chunk.id)
                              }
                            >
                              Label source
                              <Plus size={12} />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="trace-note">
                    {run.result.warnings.join(" ")}
                  </div>
                </section>
              )}
              <section className="annotation-panel">
                <div className="section-header">
                  <div>
                    <h2>
                      Expected sources & annotations{" "}
                      <span>{Object.keys(labels).length}</span>
                    </h2>
                    <p>
                      Expectations stay separate from actual hits. Missing
                      sources remain false negatives.
                    </p>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => setView("corpus")}
                  >
                    <Plus size={14} />
                    Add missing source
                  </button>
                </div>
                {Object.values(labels).map((l) => (
                  <div className="annotation" key={targetOf(l)}>
                    <div>
                      <strong>
                        {library?.documents.find((d) => d.id === l.document_id)
                          ?.title || l.document_id}
                      </strong>
                      <span className="draft-pill">
                        {run?.result.candidates.some(
                          (c) =>
                            c.document.id === l.document_id &&
                            (!l.chunk_id || c.chunk.id === l.chunk_id),
                        )
                          ? "RETRIEVED"
                          : "NOT RETRIEVED"}
                      </span>
                      <button
                        className="icon-button"
                        aria-label={"Remove " + targetOf(l)}
                        onClick={() =>
                          setLabels((old) => {
                            const next = { ...old };
                            delete next[targetOf(l)];
                            return next;
                          })
                        }
                      >
                        <X size={14} />
                      </button>
                    </div>
                    <select
                      aria-label={"Label " + targetOf(l)}
                      value={l.label}
                      onChange={(e) =>
                        setLabels((old) => ({
                          ...old,
                          [targetOf(l)]: {
                            ...l,
                            label: e.target.value as Label["label"],
                          },
                        }))
                      }
                    >
                      {[
                        "must_retrieve",
                        "relevant",
                        "not_relevant",
                        "uncertain",
                      ].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                    <input
                      aria-label={"Reason " + targetOf(l)}
                      value={l.rationale}
                      onChange={(e) =>
                        setLabels((old) => ({
                          ...old,
                          [targetOf(l)]: { ...l, rationale: e.target.value },
                        }))
                      }
                      maxLength={2000}
                      placeholder="Why is this source relevant, irrelevant or required?"
                    />
                  </div>
                ))}
                {!Object.keys(labels).length && (
                  <div className="trace-note">
                    Label retrieved documents or add an expected source from the
                    library.
                  </div>
                )}
                <div className="case-fields">
                  <label>
                    Case title
                    <input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      maxLength={160}
                      placeholder="A short name for this test"
                    />
                  </label>
                  <label>
                    Reviewer / author
                    <input
                      required
                      value={author}
                      onChange={(e) => setAuthor(e.target.value)}
                      maxLength={120}
                      placeholder="Your name"
                    />
                  </label>
                  <label>
                    Subject area
                    <input
                      value={area}
                      onChange={(e) => setArea(e.target.value)}
                      maxLength={80}
                      placeholder="e.g. employment"
                    />
                  </label>
                  <label>
                    Dataset split
                    <select
                      value={split}
                      onChange={(e) =>
                        setSplit(e.target.value as Case["split"])
                      }
                    >
                      <option value="development">Development</option>
                      <option value="critical">Critical</option>
                      <option value="holdout">Holdout draft (unsealed)</option>
                    </select>
                  </label>
                </div>
                <div className="form-footer">
                  <span>
                    Drafts do not imply expert approval. Saving persists the
                    entered context locally.
                  </span>
                  <button
                    className="primary"
                    disabled={
                      !!busy ||
                      !run ||
                      !author.trim() ||
                      Object.values(labels).some((l) => !l.rationale.trim())
                    }
                    onClick={() => void saveCase()}
                  >
                    <Check size={15} />
                    Save case draft
                  </button>
                </div>
              </section>
              {domain === "ai-act" && (
                <ReviewPanel
                  versions={versions}
                  context={[scenario, actor, deployment, constraints]
                    .filter(Boolean)
                    .join("\n")}
                />
              )}
            </>
          )}
          {view === "cases" && (
            <section className="draft-panel">
              <div className="section-header">
                <div>
                  <h2>Versioned evaluation cases</h2>
                  <p>
                    Approval is an explicit local reviewer decision.
                    Model-authored drafts stay labelled.
                  </p>
                </div>
                <button
                  className="primary"
                  disabled={!!busy || !versions?.active || !cases.length}
                  onClick={() =>
                    void act("evaluate", async () => {
                      setEvaluation(
                        await post<Evaluation>(
                          "/api/rag/evaluate?domain=" + domain,
                        ),
                      );
                    })
                  }
                >
                  {busy === "evaluate" ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <Play size={15} />
                  )}
                  Evaluate cases
                </button>
              </div>
              <div className="approval-controls">
                <label>
                  Approving reviewer
                  <input
                    value={reviewer}
                    onChange={(e) => setReviewer(e.target.value)}
                    maxLength={120}
                    placeholder="Your name for an explicit approval"
                  />
                </label>
                <p>
                  Approval records attribution. It does not establish
                  professional qualifications or legal correctness.
                </p>
              </div>
              {!cases.length ? (
                <Empty
                  title="Your test set starts with a scenario."
                  text="Run retrieval, label expected sources, then save a draft."
                />
              ) : (
                cases.map((c) => (
                  <div className="draft-row" key={c.id}>
                    <span className="doc-icon">
                      <FileText size={20} />
                    </span>
                    <div>
                      <h3>
                        {c.title}
                        <span className="draft-pill">
                          {c.status.toUpperCase()} · v{c.revision}
                        </span>
                      </h3>
                      <p>{c.request.scenario}</p>
                      <small>
                        {c.origin} · {c.author} · {c.labels.length} labelled
                        sources · {c.split}
                      </small>
                      <div className="case-labels">
                        {c.labels.map((l) => (
                          <span key={targetOf(l)}>
                            {targetOf(l)}: {l.label}
                          </span>
                        ))}
                      </div>
                    </div>
                    <button className="secondary" onClick={() => openCase(c)}>
                      Open
                      <ArrowRight size={13} />
                    </button>
                    <button
                      className="secondary"
                      disabled={
                        !!busy || !versions?.active || c.split === "holdout"
                      }
                      onClick={() =>
                        void act("evaluate", async () => {
                          setEvaluation(
                            await post<Evaluation>(
                              "/api/rag/evaluate?domain=" +
                                domain +
                                "&case_id=" +
                                encodeURIComponent(c.id),
                            ),
                          );
                        })
                      }
                    >
                      Evaluate
                    </button>
                    {c.status === "draft" && (
                      <button
                        className="secondary"
                        disabled={
                          !!busy || !reviewer.trim() || !c.labels.length
                        }
                        title={
                          !reviewer.trim()
                            ? "Enter the approving reviewer name above"
                            : ""
                        }
                        onClick={() =>
                          void act("approve", async () => {
                            await post(
                              "/api/rag/cases/" +
                                c.id +
                                "/" +
                                c.revision +
                                "/approve",
                              { reviewer },
                            );
                            await refresh();
                            setNotice(
                              "Approved as a new immutable revision. Previous draft retained.",
                            );
                          })
                        }
                      >
                        <Check size={13} />
                        Approve
                      </button>
                    )}
                    <button
                      className="icon-button"
                      aria-label={"Export " + c.title}
                      onClick={() =>
                        download(c.id + "-v" + c.revision + ".json", c)
                      }
                    >
                      <ArrowDownToLine size={17} />
                    </button>
                  </div>
                ))
              )}
              {evaluation && (
                <div className="evaluation">
                  <h3>Evaluation: {evaluation.quality_gate.status}</h3>
                  <div className="metric-grid">
                    <div>
                      <strong>{evaluation.summary.cases}</strong>
                      <span>Cases evaluated</span>
                    </div>
                    <div>
                      <strong>
                        {evaluation.summary.recall === null
                          ? "n/a"
                          : (evaluation.summary.recall * 100).toFixed(1) + "%"}
                      </strong>
                      <span>Required-source recall</span>
                    </div>
                    <div>
                      <strong>{evaluation.summary.missing_required}</strong>
                      <span>Missing required sources</span>
                    </div>
                  </div>
                  <div className="metric-grid">
                    <div>
                      <strong>
                        {evaluation.summary_at_5?.recall?.toFixed(3) ?? "n/a"}
                      </strong>
                      <span>Recall@5</span>
                    </div>
                    <div>
                      <strong>
                        {evaluation.summary.mean_precision?.toFixed(3) ?? "n/a"}
                      </strong>
                      <span>Precision@10</span>
                    </div>
                    <div>
                      <strong>
                        {evaluation.summary.mean_mrr?.toFixed(3) ?? "n/a"}
                      </strong>
                      <span>MRR@10</span>
                    </div>
                    <div>
                      <strong>
                        {evaluation.summary.mean_ndcg?.toFixed(3) ?? "n/a"}
                      </strong>
                      <span>nDCG@10</span>
                    </div>
                    <div>
                      <strong>{evaluation.summary.false_positives}</strong>
                      <span>Labelled false positives</span>
                    </div>
                  </div>
                  <ul>
                    {evaluation.quality_gate.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                  {evaluation.scores.map((s) => (
                    <div className="score-row" key={s.case_id}>
                      <span>
                        {cases.find((c) => c.id === s.case_id)?.title ||
                          s.case_id}
                      </span>
                      <strong>
                        {s.recall === null
                          ? "n/a"
                          : (s.recall * 100).toFixed(0) + "%"}
                      </strong>
                      <span>
                        Missing: {s.missed_required.join(", ") || "none"}
                      </span>
                    </div>
                  ))}
                  <button
                    className="secondary"
                    onClick={() =>
                      download(
                        "evaluation-" + evaluation.id + ".json",
                        evaluation,
                      )
                    }
                  >
                    <ArrowDownToLine size={14} />
                    Export report
                  </button>
                </div>
              )}
            </section>
          )}
          {view === "versions" && (
            <section className="draft-panel">
              <div className="section-header">
                <div>
                  <h2>Build & activate a local candidate</h2>
                  <p>
                    Models download only when explicitly selected. Activation
                    does not pass the quality gate.
                  </p>
                </div>
              </div>
              <div className="build-controls">
                <label>
                  <input
                    type="checkbox"
                    checked={downloadModel}
                    onChange={(e) => setDownloadModel(e.target.checked)}
                  />
                  Allow embedding model download (setup only, about 64 MB)
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={lexicalOnly}
                    onChange={(e) => setLexicalOnly(e.target.checked)}
                  />
                  Build an explicit lexical baseline instead of hybrid retrieval
                </label>
                <button
                  className="primary"
                  disabled={!!busy}
                  onClick={() =>
                    void act("build", async () => {
                      await post<Manifest>("/api/rag/build", {
                        domain_id: domain,
                        download_model: downloadModel,
                        lexical_only: lexicalOnly,
                      });
                      await refresh();
                      setNotice(
                        "Immutable candidate built. Activate it for local tooling tests below.",
                      );
                    })
                  }
                >
                  {busy === "build" ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Plus size={16} />
                  )}
                  Build RAG candidate
                </button>
                {busy === "build" && (
                  <p role="status">
                    Building source and vector artifacts. The first CPU build
                    can take several minutes.
                  </p>
                )}
              </div>
              {versions?.releases.map((m) => (
                <div className="version-row" key={m.rag_release_id}>
                  <div>
                    <h3>
                      {m.mode.toUpperCase()}{" "}
                      <span className="draft-pill">
                        {versions.active === m.rag_release_id
                          ? "ACTIVE"
                          : versions.previous === m.rag_release_id
                            ? "PREVIOUS"
                            : "CANDIDATE"}
                      </span>
                    </h3>
                    <p className="mono">{m.rag_release_id}</p>
                    <small>
                      {m.source_version} · {m.embedding.model} · Quality:{" "}
                      {m.quality_status}
                    </small>
                    <details>
                      <summary>Manifest</summary>
                      <pre>{JSON.stringify(m, null, 2)}</pre>
                    </details>
                  </div>
                  <button
                    className="secondary"
                    disabled={!!busy || versions.active === m.rag_release_id}
                    onClick={() =>
                      void act("activate", async () => {
                        await post(
                          "/api/rag/activate/" +
                            m.rag_release_id +
                            "?domain=" +
                            domain,
                        );
                        await refresh();
                        setNotice(
                          "Active local candidate changed. Existing runs keep their original release IDs.",
                        );
                      })
                    }
                  >
                    Use for local tests
                    <ArrowRight size={13} />
                  </button>
                </div>
              ))}
              <div className="provenance">
                <h3>Runtime configuration</h3>
                <p>
                  Review provider: {versions?.provider} · Model:{" "}
                  {versions?.model}
                  <br />
                  Cloud key:{" "}
                  {versions?.cloud_key_configured
                    ? "configured"
                    : "not configured"}{" "}
                  · Tracing:{" "}
                  {versions?.tracing_enabled ? "enabled" : "disabled"}
                </p>
                <p>
                  Retrieval uses local embeddings. Gemini review is a separate
                  explicit action with cloud consent.
                </p>
                {library?.scope_limits.map((p) => (
                  <p key={p}>{p}</p>
                ))}
              </div>
            </section>
          )}
          {view === "compare" && (
            <section className="draft-panel">
              <div className="section-header">
                <div>
                  <h2>Compare saved retrieval runs</h2>
                  <p>
                    Different context and different RAG versions are visible,
                    never silently merged.
                  </p>
                </div>
              </div>
              <div className="compare-pickers">
                {[
                  [left, setLeft],
                  [right, setRight],
                ].map(([value, setter], i) => (
                  <label key={i}>
                    {i === 0 ? "Before" : "After"}
                    <select
                      aria-label={i === 0 ? "Before run" : "After run"}
                      value={value as string}
                      onChange={(e) =>
                        (setter as (v: string) => void)(e.target.value)
                      }
                    >
                      <option value="">Select a run</option>
                      {runs.map((r) => (
                        <option value={r.id} key={r.id}>
                          {short(r.id)} ·{" "}
                          {r.result.request.scenario.slice(0, 55)}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              {a && b ? (
                <div className="comparison">
                  {[a, b].map((r, i) => (
                    <article key={i}>
                      <span className="eyebrow">
                        {i === 0 ? "BEFORE" : "AFTER"}
                      </span>
                      <h3>{r.result.request.scenario}</h3>
                      <p>
                        {r.result.request.context.actor_role} ·{" "}
                        {r.result.request.context.deployment}
                      </p>
                      <small>
                        RAG {short(r.result.rag_release_id)} · Context{" "}
                        {short(r.result.context_fingerprint)}
                      </small>
                      {[
                        ...new Set(
                          r.result.candidates.map((c) => c.document.id),
                        ),
                      ].map((id) => (
                        <div className="compare-hit" key={id}>
                          {id}
                          <span className="draft-pill">
                            {(i === 0 ? b : a).result.candidates.some(
                              (c) => c.document.id === id,
                            )
                              ? "SHARED"
                              : i === 0
                                ? "REMOVED"
                                : "ADDED"}
                          </span>
                        </div>
                      ))}
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title="Choose two runs"
                  text="Run different scenarios or versions, then inspect how their source selections change."
                />
              )}
            </section>
          )}
          <footer>
            <span>
              <Layers3 size={14} />
              AI Act Copilot
              <i />
              Grounded sources. Inspectable tools.
            </span>
            <span>M1 · Local development</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <BookOpen size={24} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
