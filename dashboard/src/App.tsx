import { useEffect, useState } from "react";
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
  Layers3,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { request, type Corpus, type Draft, type Section } from "./api";

type View = "corpus" | "scenario" | "drafts";
const samples = [
  {
    title: "Applicant ranking",
    scenario:
      "An AI system scores job applicants and produces a shortlist for a recruiter.",
    context:
      "The deployment role, human oversight and final decision process need clarification.",
  },
  {
    title: "Customer assistant",
    scenario:
      "A customer-facing chatbot generates answers to support questions.",
    context: "Whether users are told they are interacting with AI is unknown.",
  },
  {
    title: "Biometric matching",
    scenario: "An AI system compares face images against a reference gallery.",
    context:
      "The intended purpose, setting and verification or identification role are unknown.",
  },
];

export default function App() {
  const [view, setView] = useState<View>("corpus");
  const [corpus, setCorpus] = useState<Corpus | null>(null);
  const [selected, setSelected] = useState<Section | null>(null);
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [title, setTitle] = useState("");
  const [scenario, setScenario] = useState("");
  const [context, setContext] = useState("");
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [showProvenance, setShowProvenance] = useState(false);

  async function loadCorpus() {
    setLoading(true);
    setError("");
    try {
      const result = await request<Corpus>("/api/corpus");
      setCorpus(result);
      setSelected(result.sections[0] || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load corpus.");
    } finally {
      setLoading(false);
    }
  }
  async function loadDrafts() {
    setDraftsLoading(true);
    setError("");
    try {
      setDrafts(await request<Draft[]>("/api/drafts"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load drafts.");
    } finally {
      setDraftsLoading(false);
    }
  }
  useEffect(() => {
    void loadCorpus();
  }, []);
  useEffect(() => {
    if (view === "drafts") void loadDrafts();
  }, [view]);

  const sections =
    corpus?.sections.filter((s) => {
      const text = (s.title + " " + s.id + " " + s.text).toLowerCase();
      return (
        query
          .toLowerCase()
          .split(/\s+/)
          .every((t) => text.includes(t)) &&
        (group === "all" ||
          (group === "annex"
            ? s.id.startsWith("annex")
            : s.id.startsWith("article")))
      );
    }) || [];
  const active =
    selected && sections.some((s) => s.id === selected.id)
      ? selected
      : sections[0];
  function addSource(section: Section) {
    if (sourceIds.includes(section.id)) {
      setView("scenario");
      return;
    }
    if (sourceIds.length >= 50) {
      setError("A draft can reference at most 50 sources.");
      return;
    }
    setSourceIds((ids) => [...ids, section.id]);
    setNotice(section.title + " added to your scenario.");
  }
  function newScenario() {
    setTitle("");
    setScenario("");
    setContext("");
    setSourceIds([]);
    setNotice("");
    setView("scenario");
  }
  async function saveDraft() {
    if (!corpus) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await request<Draft>("/api/drafts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          scenario,
          context,
          source_ids: sourceIds,
          corpus_checksum: corpus.checksum,
        }),
      });
      setNotice("Scenario saved locally as a draft.");
      setView("drafts");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save draft.");
    } finally {
      setSaving(false);
    }
  }
  function exportDraft(draft: Draft) {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "scenario-" + draft.id + ".json";
    link.click();
    URL.revokeObjectURL(url);
  }

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
          LOCAL WORKSPACE <span>01</span>
        </div>
        <nav aria-label="Workbench">
          <button
            className={view === "corpus" ? "nav-item active" : "nav-item"}
            onClick={() => setView("corpus")}
          >
            <BookOpen size={18} />
            Corpus explorer<span>{corpus?.total ?? "…"}</span>
          </button>
          <button
            className={view === "scenario" ? "nav-item active" : "nav-item"}
            onClick={() => setView("scenario")}
          >
            <FlaskConical size={18} />
            Scenario studio
          </button>
          <button
            className={view === "drafts" ? "nav-item active" : "nav-item"}
            onClick={() => setView("drafts")}
          >
            <FileText size={18} />
            Saved drafts
          </button>
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">BUILD WITH EVIDENCE</span>
          <p>A clearer path from source documents to better retrieval.</p>
          <div>
            <span className="tiny-dot" /> M1 · Tooling foundation
          </div>
        </div>
        <div className="sidebar-bottom">
          <span className="avatar">EL</span>
          <div>
            Local workbench<small>No model calls enabled</small>
          </div>
          <ShieldCheck size={17} />
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            Workspace <ChevronRight size={14} />
            <strong>
              {view === "corpus"
                ? "Corpus explorer"
                : view === "scenario"
                  ? "Scenario studio"
                  : "Saved drafts"}
            </strong>
          </div>
          <span className="local-badge">
            <span className="tiny-dot" /> LOCAL ONLY
          </span>
        </header>
        <div className="page">
          <div className="page-heading">
            <div>
              <div className="eyebrow green">RETRIEVAL WORKBENCH</div>
              <h1>
                {view === "corpus"
                  ? "Start with the source."
                  : view === "scenario"
                    ? "Give your test context."
                    : "Your next good question."}
              </h1>
              <p>
                {view === "corpus"
                  ? "Explore the knowledge behind your reviews. Every passage, traceable."
                  : view === "scenario"
                    ? "Capture a use case and the sources you want to investigate."
                    : "Reopen local scenarios and build a thoughtful evaluation set."}
              </p>
            </div>
            <button className="primary" onClick={newScenario}>
              <Plus size={17} /> New scenario
            </button>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <CircleHelp size={18} />
              <span>{error}</span>
              <button
                onClick={() =>
                  void (view === "drafts" ? loadDrafts() : loadCorpus())
                }
              >
                <RefreshCw size={15} /> Retry
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
          <section className="stats" aria-label="Corpus status">
            <div>
              <span className="stat-icon">
                <Database size={19} />
              </span>
              <div>
                <span>Indexed passages</span>
                <strong>
                  {corpus?.total ?? "…"}
                  <small>Selected subset</small>
                </strong>
              </div>
            </div>
            <div>
              <span className="stat-icon">
                <ExternalLink size={19} />
              </span>
              <div>
                <span>Official source pages</span>
                <strong>
                  {corpus?.source_count ?? "…"}
                  <small>Commission reproduction</small>
                </strong>
              </div>
            </div>
            <div>
              <span className="stat-icon">
                <ShieldCheck size={19} />
              </span>
              <div>
                <span>Corpus integrity</span>
                <strong className="status-text">
                  {corpus
                    ? "Verified checksum"
                    : loading
                      ? "Checking…"
                      : "Unavailable"}
                </strong>
                <small>Local package verification</small>
              </div>
            </div>
          </section>
          <div className="coverage-note">
            <CircleHelp size={17} />
            <span>
              <strong>Legacy POC corpus.</strong> Selected provisions, not the
              full AI Act. Full-corpus ingestion and retrieval evaluation are
              next.
            </span>
            <button onClick={() => setShowProvenance(!showProvenance)}>
              {showProvenance ? "Hide details" : "View provenance"}
              <ArrowRight size={14} />
            </button>
          </div>
          {showProvenance && corpus && (
            <section className="provenance">
              <h2>Source provenance</h2>
              <p>{corpus.source_identity}</p>
              <ul>
                {corpus.scope_limits.map((limit) => (
                  <li key={limit}>{limit}</li>
                ))}
              </ul>
              <dl>
                <dt>Corpus version</dt>
                <dd>{corpus.version}</dd>
                <dt>Snapshot checksum</dt>
                <dd className="mono">{corpus.checksum}</dd>
                <dt>Recorded source verification</dt>
                <dd>{corpus.verified_at}</dd>
              </dl>
            </section>
          )}
          {view === "corpus" && (
            <section className="explorer">
              <div className="section-header">
                <div>
                  <h2>
                    Source library <span>AI Act</span>
                  </h2>
                  <p>Find a provision and inspect its exact wording.</p>
                </div>
                <span className="quiet-label">ENGLISH · PACKAGED SNAPSHOT</span>
              </div>
              <div className="library-toolbar">
                <label className="search">
                  <Search size={18} />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search passages, references or keywords…"
                    aria-label="Search corpus"
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
                  aria-label="Filter document type"
                  value={group}
                  onChange={(e) => setGroup(e.target.value)}
                >
                  <option value="all">All document types</option>
                  <option value="article">Articles</option>
                  <option value="annex">Annexes</option>
                </select>
              </div>
              {loading ? (
                <div className="empty">
                  <LoaderCircle className="spin" />
                  <h3>Loading source library</h3>
                  <p>Checking the packaged corpus and its provenance.</p>
                </div>
              ) : !corpus ? (
                <div className="empty">
                  <Database />
                  <h3>Source library unavailable</h3>
                  <p>Start the local API, then retry.</p>
                </div>
              ) : (
                <div className="library-body">
                  <div className="source-list">
                    <div className="list-caption">
                      {sections.length} PASSAGES <span>REFERENCE</span>
                    </div>
                    {sections.length === 0 ? (
                      <div className="empty">
                        <Search />
                        <h3>No matching passages</h3>
                        <p>Try a different keyword or document type.</p>
                      </div>
                    ) : (
                      sections.map((section) => (
                        <button
                          key={section.id}
                          className={
                            "source-row " +
                            (active?.id === section.id ? "selected" : "")
                          }
                          onClick={() => setSelected(section)}
                        >
                          <span className="doc-icon">
                            <FileText size={18} />
                          </span>
                          <div>
                            <strong>{section.title}</strong>
                            <p>{section.text}</p>
                            <span>
                              {section.id.startsWith("annex")
                                ? "Annex"
                                : "Article"}
                              <i />
                              Official source
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
                          <span className="green-pill">SOURCE DOCUMENT</span>
                          <span className="quiet-label">EXACT WORDING</span>
                        </div>
                        <h2>{active.title}</h2>
                        <div className="detail-meta">
                          <span className="tiny-dot" />
                          Commission reproduction · English
                        </div>
                        <div className="source-text">{active.text}</div>
                        <a
                          className="official-link"
                          href={active.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open official source
                          <ExternalLink size={15} />
                        </a>
                        <div className="detail-facts">
                          <div>
                            <span>Applicability date</span>
                            <strong>
                              {active.applicability_date ||
                                "Not independently verified"}
                            </strong>
                          </div>
                          <div>
                            <span>Reference ID</span>
                            <strong className="mono">{active.id}</strong>
                          </div>
                        </div>
                        <div className="source-action">
                          <div>
                            <h3>Useful for your scenario?</h3>
                            <p>Keep this source as a reference in a draft.</p>
                          </div>
                          <button
                            className="secondary"
                            onClick={() => addSource(active)}
                          >
                            {sourceIds.includes(active.id) ? (
                              <Check size={16} />
                            ) : (
                              <Plus size={16} />
                            )}
                            {sourceIds.includes(active.id)
                              ? "In scenario"
                              : "Add to scenario"}
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="empty">
                        <BookOpen />
                        <h3>Select a source</h3>
                        <p>Matching source text will appear here.</p>
                      </div>
                    )}
                  </article>
                </div>
              )}
            </section>
          )}
          {view === "scenario" && (
            <section className="studio">
              <div className="scenario-form">
                <div className="section-header">
                  <div>
                    <h2>Scenario draft</h2>
                    <p>Context first. Evaluation follows.</p>
                  </div>
                  <span className="draft-pill">DRAFT</span>
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void saveDraft();
                  }}
                >
                  <label>
                    Scenario name
                    <input
                      required
                      maxLength={160}
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. Applicant shortlisting with human review"
                    />
                  </label>
                  <label>
                    Intended use
                    <textarea
                      required
                      maxLength={12000}
                      rows={5}
                      value={scenario}
                      onChange={(e) => setScenario(e.target.value)}
                      placeholder="Describe what the system does and who it affects…"
                    />
                  </label>
                  <label>
                    Deployment context <span>Optional</span>
                    <textarea
                      maxLength={6000}
                      rows={4}
                      value={context}
                      onChange={(e) => setContext(e.target.value)}
                      placeholder="Actor role, deployment setting, constraints and unknowns…"
                    />
                  </label>
                  <div className="form-footer">
                    <span>
                      <ShieldCheck size={15} /> Saved in local SQLite
                    </span>
                    <button
                      className="primary"
                      disabled={
                        saving || !corpus || !title.trim() || !scenario.trim()
                      }
                    >
                      {saving ? (
                        <LoaderCircle className="spin" size={16} />
                      ) : (
                        <Check size={16} />
                      )}
                      Save draft
                    </button>
                  </div>
                </form>
              </div>
              <aside className="scenario-aside">
                <h3>A place to start</h3>
                <p>These are editable scenario prompts, not approved tests.</p>
                {samples.map((sample) => (
                  <button
                    className="sample"
                    key={sample.title}
                    onClick={() => {
                      setTitle(sample.title);
                      setScenario(sample.scenario);
                      setContext(sample.context);
                    }}
                  >
                    <FlaskConical size={17} />
                    <span>{sample.title}</span>
                    <ArrowRight size={15} />
                  </button>
                ))}
                <div className="references">
                  <h3>
                    Reference sources <span>{sourceIds.length}</span>
                  </h3>
                  {sourceIds.length === 0 ? (
                    <p>
                      Add passages from the corpus explorer. Expected retrieval
                      labels will come later.
                    </p>
                  ) : (
                    sourceIds.map((id) => (
                      <div key={id}>
                        <span>
                          {corpus?.sections.find((s) => s.id === id)?.title ||
                            id}
                        </span>
                        <button
                          aria-label={"Remove " + id}
                          onClick={() =>
                            setSourceIds((ids) => ids.filter((s) => s !== id))
                          }
                        >
                          <X size={15} />
                        </button>
                      </div>
                    ))
                  )}
                  <button
                    className="text-button"
                    onClick={() => setView("corpus")}
                  >
                    Browse sources <ArrowRight size={15} />
                  </button>
                </div>
              </aside>
            </section>
          )}
          {view === "drafts" && (
            <section className="draft-panel">
              <div className="section-header">
                <div>
                  <h2>Saved scenarios</h2>
                  <p>
                    Local drafts. No expert approval or model evaluation
                    implied.
                  </p>
                </div>
                <button className="secondary" onClick={() => void loadDrafts()}>
                  <RefreshCw size={15} />
                  Refresh
                </button>
              </div>
              {draftsLoading ? (
                <div className="empty">
                  <LoaderCircle className="spin" />
                  <p>Loading saved scenarios…</p>
                </div>
              ) : drafts.length === 0 ? (
                <div className="empty">
                  <FlaskConical />
                  <h3>Your evaluation set starts here.</h3>
                  <p>
                    Capture a scenario, attach sources and save your first
                    draft.
                  </p>
                  <button className="primary" onClick={newScenario}>
                    <Plus size={16} />
                    Create a scenario
                  </button>
                </div>
              ) : (
                drafts.map((draft) => (
                  <div className="draft-row" key={draft.id}>
                    <span className="doc-icon">
                      <FileText size={20} />
                    </span>
                    <div>
                      <h3>
                        {draft.title}
                        <span className="draft-pill">DRAFT</span>
                      </h3>
                      <p>{draft.scenario}</p>
                      <small>
                        {new Date(draft.created_at).toLocaleString()} ·{" "}
                        {draft.source_ids.length} source references
                      </small>
                    </div>
                    <button
                      className="secondary"
                      onClick={() => {
                        setTitle(draft.title);
                        setScenario(draft.scenario);
                        setContext(draft.context);
                        setSourceIds(draft.source_ids);
                        setView("scenario");
                        setNotice(
                          "Opened a saved draft. Saving creates a new snapshot.",
                        );
                      }}
                    >
                      Open
                      <ArrowRight size={14} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={"Export " + draft.title}
                      onClick={() => exportDraft(draft)}
                    >
                      <ArrowDownToLine size={18} />
                    </button>
                  </div>
                ))
              )}
            </section>
          )}
          <footer>
            <span>
              <Layers3 size={14} /> AI Act Copilot <i /> Retrieval tools,
              grounded in sources.
            </span>
            <span>Workbench v0.1 · Local development</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
