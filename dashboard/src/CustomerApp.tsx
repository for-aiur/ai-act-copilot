import { AiSystems } from "./AiSystems";
import { FalsePositives } from "./FalsePositives";
import { CustomerProjects, ProjectScope, scopedPath } from "./CustomerProjects";
import { LegalSourceLine, SourceVersionFilter, sourceVersionLabel, type LegalSource } from "./LegalSourceUpdates";
import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  BookOpenCheck,
  Check,
  ChevronRight,
  CircleAlert,
  Copy,
  ExternalLink,
  FileCode2,
  KeyRound,
  GitPullRequest,
  LoaderCircle,
  LogOut,
  Network,
  Plus,
  ScanSearch,
  Shield,
  Trash2,
} from "lucide-react";
import { request } from "./api";
import { RepositoryAudits } from "./RepositoryAudits";
import { CustomerOverview, CustomerUsage } from "./CustomerOverview";
import { FindingsPanel } from "./FindingsPanel";
import recruitmentCode from "../../examples/recruitment/bias_audit.py?raw";
import biometricsCode from "../../examples/biometrics/identify.py?raw";
import chatbotCode from "../../examples/chatbot/assistant.py?raw";

type User = { id: string; tenant_id: string; email: string; workspace: string };
type Evidence = { path: string; start_line: number; end_line: number; quote: string };
type Citation = { section_id: string; quote: string; url: string };
type Finding = {
  id: string; title: string; explanation: string; kind: string; priority: string;
  evidence: Evidence; citations: Citation[]; suggested_next_action: string;
  context_question: string | null;
};
type ReviewSession = {
  status: string; context_question: string | null; finding_id: string | null;
  rag_release_id: string | null; history: { id: string; type: string; created_at: string;
    actor: string; finding_id?: string | null; question?: string | null; answer?: string | null }[];
  scan_result: { status: string; findings: Finding[]; errors: { code: string; message: string }[];
    metadata: { provider: string | null; model_id: string | null; elapsed_ms: number; corpus_version: string | null } } | null;
};
type RetrievedSource = { id: string; document_id: string; title: string; text: string; url: string };
type Job = { id: string; status: string; attempts: number; created_at: string; updated_at: string;
  filename?: string | null; legal_source?: LegalSource | null; session: ReviewSession | null; error: { code: string; message: string } | null;
  events: { revision: number; type: string; created_at: string; details: Record<string, unknown> }[];
  sources: RetrievedSource[] };
type ApiKey = { id: string; name: string; prefix: string; last_four: string; created_at: string;
  last_used_at: string | null; revoked_at: string | null };
type Sample = { name: string; filename: string; scenario: string; code: string };

const samples: Sample[] = [
  { name: "Recruitment", filename: "bias_audit.py", scenario: "A recruitment team uses a model to score candidates and reviews sensitive data for a bias audit.", code: recruitmentCode },
  { name: "Biometrics", filename: "identify.py", scenario: "A camera system compares a person's face with an enrolled gallery to return an identity.", code: biometricsCode },
  { name: "Customer chatbot", filename: "assistant.py", scenario: "A customer support chatbot generates replies that are shown to users.", code: chatbotCode },
];

async function post<T>(path: string, body: unknown, headers: Record<string, string> = {}) {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(body) });
}
function go(path: string) { window.location.assign(path); }
function time(value: string) { return new Date(value).toLocaleString(); }

export function PublicHome() {
  const metrics = [
    ["128", "Reviews run"], ["47", "Findings raised"], ["8", "Repositories reviewed"], ["18.4k", "Lines scanned"],
  ];
  return <div className="public-site product-home">
    <header className="public-nav">
      <a className="public-brand" href="/"><img src="/copilot-logo.png" alt="" /><span>AI Act Copilot</span></a>
      <nav>
        <a href="#how-it-works">Workflow</a>
        <a href="#features">For teams</a>
        <a href="https://github.com/for-aiur/ai-act-copilot" target="_blank" rel="noreferrer">GitHub <ExternalLink size={14} /></a>
        <a className="button-dark" href="/onboarding">Try a review <ArrowRight size={15} /></a>
      </nav>
    </header>
    <main className="public-main">
      <section className="product-hero">
        <div className="hero-copy">
          <h1>AI Act review<br/>starts <em>in code.</em></h1>
          <p>Developers and their coding agents can check Python changes early. The GitHub bot links findings to the exact code and official EU text so engineering and legal can review the same evidence.</p>
          <div className="hero-actions">
            <a className="button-dark" href="/onboarding">Try a sample review <ArrowRight size={16} /></a>
            <a className="text-link" href="#how-it-works">See the workflow <ChevronRight size={15} /></a>
          </div>
        </div>
        <figure className="product-preview" aria-label="Illustrative review of a candidate ranking change">
          <figcaption><span><GitPullRequest size={16}/> recruitment / PR #14</span><small>Example review</small></figcaption>
          <div className="preview-code">
            <div><FileCode2 size={14}/> ranking.py <span>Changed lines</span></div>
            <pre><code>{'  41  scores = model.predict(candidates)\n+ 42  return rank_by_score(scores)'}</code></pre>
          </div>
          <div className="preview-finding">
            <div><img src="/copilot-logo.png" alt=""/><b>AI Act Copilot</b><span>Needs context</span></div>
            <strong>Can a reviewer override the ranking?</strong>
            <p>The model score changes candidate order. Check where a person can intervene before the result is used.</p>
            <div className="preview-source"><BookOpenCheck size={16}/><span><b>Official EU text</b><small>Article 14 · Human oversight</small></span></div>
          </div>
          <div className="preview-handoff"><Shield size={17}/><span><b>Legal review</b><small>Check the evidence and record a decision.</small></span></div>
        </figure>
      </section>
      <section className="product-metrics" aria-labelledby="sample-metrics">
        <h2 id="sample-metrics">Sample workspace activity</h2>
        <dl>{metrics.map(([value,label])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      </section>
      <section id="how-it-works" className="public-how">
        <div className="public-section-title"><h2>From the editor to the review decision</h2></div>
        <div className="flow-cards">
          <article><span>01</span><FileCode2/><h3>Check before you push</h3><p>Run a review on the current Python file in VS Code and see feedback in the editor.</p></article>
          <article><span>02</span><GitPullRequest/><h3>Review in GitHub</h3><p>The bot leaves evidence on the changed lines. Reply with context, acknowledge a finding or flag a false positive.</p></article>
          <article><span>03</span><Shield/><h3>Give legal a place to follow up</h3><p>Explore findings by repo and record decisions in the demo dashboard. The demo uses simulated GitHub activity.</p></article>
        </div>
      </section>
      <section id="features" className="product-team">
        <div><h2>Meet teams where they work</h2><p>VS Code and GitHub are the starting point. We’re extending the workflow to more IDEs, local diff reviews before push and shared decisions that sync with GitHub.</p></div>
        <div className="product-team-links">
          <a href="https://github.com/for-aiur/ai-act-copilot/blob/main/extensions/vscode/README.md"><FileCode2 size={17}/> VS Code setup <ExternalLink size={14}/></a>
          <a href="https://github.com/for-aiur/ai-act-copilot/blob/main/docs/GITHUB-APP.md"><GitPullRequest size={17}/> GitHub App setup <ExternalLink size={14}/></a>
          <a href="/login"><Shield size={17}/> Explore the demo dashboard <ArrowRight size={14}/></a>
        </div>
      </section>
      <footer className="public-footer"><span>AI Act Copilot by Evros Labs</span><span>Engineering review support</span><a href="/login">Sign in</a></footer>
    </main>
  </div>;
}

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function enterDemo() { setBusy(true); setError("");
    try { await post<User>("/api/auth/demo", {}); go("/app"); }
    catch (err) { setError(err instanceof Error ? err.message : "The demo could not be opened."); } finally { setBusy(false); }
  }
  return <div className="auth-page"><a className="auth-back" href="/"><img src="/copilot-logo.png" alt="" /> AI Act Copilot</a><div className="auth-card">
    <span className="public-kicker"><span /> AI ACT COPILOT</span>
    <h1>{mode === "register" ? "Create an account" : "Welcome to AI Act Copilot"}</h1>
    <p>{mode === "register" ? "Account creation is not available in this demo." : "Explore the demo with a sample review."}</p>
    {error && <div role="alert" className="inline-error"><CircleAlert size={16} />{error}</div>}
    {mode === "register" ? <button className="button-dark auth-submit" disabled>Create an account</button> : <button className="button-dark auth-submit" onClick={enterDemo} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : null}Enter the demo<ArrowRight size={16} /></button>}
    <div className="auth-switch">{mode === "register" ? <a href="/login">Back to demo sign in</a> : <button type="button" disabled>Create an account</button>}</div>
  </div></div>;
}

export function Onboarding() {
  const [sample, select] = useState(samples[0]);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<{status:string; findings:Finding[]; errors:{message:string}[]} | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [consent, setConsent] = useState(false);
  const [cloudReview, setCloudReview] = useState(false);
  const [policyReady,setPolicyReady] = useState(false);
  useEffect(() => { request<{cloud_review_requires_consent:boolean}>("/api/review-policy").then(v => {setCloudReview(v.cloud_review_requires_consent);setPolicyReady(true)}).catch(() => setError("Could not load review settings.")); }, []);
  async function run() {
    setBusy(true); setResult(null); setError("");
    try { setResult(await post("/api/rag/preview", {filename:sample.filename, code:sample.code, question:question.trim(), cloud_consent:consent})); }
    catch (e) { setError(e instanceof Error ? e.message : "Review failed."); }
    finally { setBusy(false); }
  }
  return <main className="sample-demo"><header className="sample-demo-header"><a href="/"><img src="/copilot-logo.png" alt="AI Act Copilot" /></a><a href="/login">Sign in <ArrowRight size={16}/></a></header><div className="onboard-layout"><section className="panel onboard-panel"><div className="step-pill">TRY AN EXAMPLE</div><h1>Try a code review</h1><p>Choose an example to see what the reviewer finds. Sample runs stay outside your dashboard.</p>
    <div className="sample-picker">{samples.map(item => <button className={sample === item ? "sample-choice selected" : "sample-choice"} aria-pressed={sample === item} key={item.name} disabled={busy} onClick={() => {select(item); setQuestion(""); setConsent(false); setResult(null); setError("");}}><span className="sample-choice-icon"><FileCode2 size={18}/></span><span><b>{item.name}</b><small>{item.filename}</small></span>{sample === item && <Check size={17}/>}</button>)}</div>
    <h2>{sample.filename}</h2><p>{sample.scenario}</p><pre style={{overflowX:"auto"}}><code>{sample.code}</code></pre>
    <label className="field-label">Review question (optional)
      <textarea rows={2} maxLength={500} disabled={busy} value={question}
        onChange={e=>{setQuestion(e.target.value);setConsent(false);}}
        placeholder="What should the reviewer check in this example?"/>
    </label>
    {cloudReview && <label className="consent-card"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> Allow sending the sample and question to Google Gemini</label>}
    <div className="onboard-actions"><button className="button-dark" disabled={busy || !policyReady || (cloudReview && !consent)} onClick={run}>{busy ? "Reviewing…" : "Run example"}</button><a href="/login">Open dashboard</a></div>
    {error && <p role="alert">{error}</p>}{result && <section aria-live="polite"><h2>Model feedback</h2>{result.errors.map((e,i)=><p key={i}>{e.message}</p>)}<FindingList findings={result.findings}/>{result.status === "complete" && !result.findings.length && <p>No findings for this example.</p>}</section>}</section><aside className="onboard-side"><div className="onboard-side-mark"><img src="/copilot-logo.png" alt=""/></div><h3>How it works</h3><ol><li><span>1</span><div><b>Choose an example</b><small>Explore a short piece of AI code.</small></div></li><li><span>2</span><div><b>Run the review</b><small>The model reads the code and finds relevant legal sources.</small></div></li><li><span>3</span><div><b>Explore the feedback</b><small>See concerns, evidence and questions together.</small></div></li></ol></aside></div></main>;
}

export function NewReview() {
  const [sample, setSample] = useState(() => samples.find(item => item.filename === new URLSearchParams(location.search).get("sample")) || samples[0]); const [cloudReview, setCloudReview] = useState(false);
  const [cloudConsent, setCloudConsent] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [policyReady,setPolicyReady] = useState(false);
  useEffect(() => { request<User>("/api/auth/me").then(setUser).catch(() => go("/login")); request<{cloud_review_requires_consent:boolean}>("/api/review-policy").then(v=>{setCloudReview(v.cloud_review_requires_consent);setPolicyReady(true)}).catch(()=>setError("Could not load review settings.")); }, []);
  async function start() { setBusy(true); setError(""); try {
    const idempotency = crypto.randomUUID(); const job = await post<Job>("/api/reviews", {
      code: sample.code, filename: sample.filename, context: sample.scenario, cloud_consent: cloudConsent,
    }, { "Idempotency-Key": idempotency }); go(`/app/reviews/${job.id}`);
  } catch (e) { setError(e instanceof Error ? e.message : "Review could not be started."); } finally { setBusy(false); } }
  if (!user) return <div className="loading-screen"><LoaderCircle className="spin"/>Preparing the demo</div>;
  async function logout() { await fetch("/api/auth/logout", { method: "POST" }); go("/"); }
  return <CustomerShell active="" title="Your first review" user={user} onLogout={logout} >
    <div className="onboard-layout"><section className="panel onboard-panel"><div className="step-pill">GETTING STARTED <span>1 / 2</span></div><h2>Choose a sample scenario</h2><p>These examples are short and synthetic. They contain no real people or customer data.</p>
      <div className="sample-picker">{samples.map(item => <button key={item.name} className={sample.name === item.name ? "sample-choice selected" : "sample-choice"} onClick={() => setSample(item)}><span className="sample-choice-icon"><FileCode2 size={18} /></span><span><b>{item.name}</b><small>{item.filename}</small></span>{sample.name === item.name && <Check size={17} />}</button>)}</div>
      <label className="field-label">Scenario description<textarea readOnly rows={3} value={sample.scenario} /></label>
      <section className="sample-code-preview" aria-label="Sample code to be reviewed"><div><FileCode2 size={15}/><b>Code to be reviewed</b><span>{sample.filename}</span></div><pre><code>{sample.code}</code></pre></section>
      {cloudReview && <label className="consent-card"><input type="checkbox" checked={cloudConsent} onChange={e => setCloudConsent(e.target.checked)} /><span><b>Allow this sample to be sent to Google Gemini for review.</b><small>This sends the sample code and context to Google for this review.</small></span></label>}
      {error && <div role="alert" className="inline-error"><CircleAlert size={16} />{error}</div>}
      <div className="onboard-actions"><button className="button-dark" onClick={start} disabled={busy || !policyReady || (cloudReview && !cloudConsent)}>{busy ? <LoaderCircle className="spin" size={16} /> : <BookOpenCheck size={16} />}Run sample review<ArrowRight size={16} /></button><a href="/app">Skip for now</a></div>
    </section><aside className="onboard-side"><div className="onboard-side-mark"><img src="/copilot-logo.png" alt="" /></div><h3>What happens next?</h3><ol><li><span>1</span><div><b>Your sample is reviewed</b><small>The code is read, never executed.</small></div></li><li><span>2</span><div><b>Evidence stays together</b><small>See the source line and official text side by side.</small></div></li><li><span>3</span><div><b>Answer one question</b><small>If context is missing, add it and resume.</small></div></li></ol><p>Zero findings never means certified compliance.</p></aside></div>
  </CustomerShell>;
}

function CustomerShell({ active, title, children, user, onLogout }: { active: string; title: string; children: ReactNode; user?: User; onLogout?: () => void }) {
  const [theme, setTheme] = useState<"signal" | "blueprint">(() =>
    localStorage.getItem("customer-theme") === "signal" ? "signal" : "blueprint");
  function selectTheme(next: typeof theme) {
    setTheme(next);
    localStorage.setItem("customer-theme", next);
  }
  const links = [{id:"findings",label:"Findings",href:"/app/findings",icon:Shield}, { id: "legal-review", label: "Legal review", href: "/app/legal-review", icon: Shield }, { id: "false-positives", label: "False positives", href: "/app/false-positives", icon: CircleAlert }, { id: "overview", label: "Overview", href: "/app", icon: Activity }, { id: "projects", label: "Projects", href: "/app/projects", icon: GitPullRequest }, { id: "systems", label: "AI Systems", href: "/app/ai-systems", icon: Network }, { id: "reviews", label: "Code Checks", href: "/app/reviews", icon: BookOpenCheck }, { id: "audits", label: "Repository Scans", href: "/app/audits", icon: ScanSearch }, { id: "api", label: "API", href: "/app/api", icon: KeyRound }];
  return <div className="customer-shell" data-theme={theme}><aside className="customer-sidebar"><a href="/" className="customer-logo"><img src="/copilot-logo.png" alt="" /><span>AI Act Copilot</span></a><div className="workspace-chip"><span>{(user?.workspace || "Demo team").slice(0,1).toUpperCase()}</span><div><b>{user?.workspace || "AI Act Demo"}</b>{user?.email && <small>{user.email}</small>}</div></div><nav aria-label="Main navigation">{links.map(({id,label,href,icon:Icon}) => <a className={active===id?"customer-nav active":"customer-nav"} href={scopedPath(href)} key={id}><Icon size={17}/>{label}</a>)}</nav><div className="sidebar-spacer"/><button className="customer-nav logout-link" onClick={onLogout}><LogOut size={17}/>Sign out</button></aside>
    <main className="customer-main"><div className="customer-content"><div className="customer-heading"><h1>{title}</h1>
      <div className="customer-theme-switch" role="group" aria-label="Dashboard theme">
        <button type="button" aria-pressed={theme === "signal"} onClick={()=>selectTheme("signal")}>Signal Room</button>
        <button type="button" aria-pressed={theme === "blueprint"} onClick={()=>selectTheme("blueprint")}>Blueprint</button>
      </div>
    </div>{children}</div></main></div>;
}

export function CustomerDashboard() {
  const [user, setUser] = useState<User | null>(null); const [path, setPath] = useState(location.pathname);
  const [reviews, setReviews] = useState<Job[]>([]);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const [refreshToken, setRefreshToken] = useState(0);
  async function load() {
    try {
      const me = await request<User>("/api/auth/me");
      if (/^\/app\/?$/.test(location.pathname)) {
        const projects = await request<{id:string}[]>("/api/customer/projects");
        if (projects.length === 0) {
          location.replace("/app/projects");
          return;
        }
      }
      setUser(me);
      if (location.pathname.replace(/\/$/, "") === "/app/reviews") {
        setReviews(await request<Job[]>("/api/reviews"));
      }
      setError("");
    } catch (e) {
      const message = (e as Error).message;
      if (message.toLowerCase().includes("sign in")) go("/login");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); const onPop = () => setPath(location.pathname); addEventListener("popstate", onPop); return () => removeEventListener("popstate", onPop); }, []);
  useEffect(() => { if (/^\/app\/reviews\/[^/]+$/.test(path)) { const id = path.split("/").pop()!; let live=true; let timer: ReturnType<typeof setTimeout>; const poll=async()=>{ try { const job=await request<Job>(`/api/reviews/${id}`); if(live)setSelectedJob(job); if(live&&["queued","running","answer_queued"].includes(job.status)) timer=setTimeout(poll,1200); } catch(e) { if(live)setError((e as Error).message); } }; poll(); return()=>{live=false;clearTimeout(timer)}; } }, [path, refreshToken]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  async function logout() { await fetch("/api/auth/logout", { method: "POST" }); go("/"); }
  if (loading) return <div className="loading-screen"><LoaderCircle className="spin"/>Loading the dashboard</div>;
  const detail = /^\/app\/reviews\/([^/]+)$/.test(path);
  const isApiPage = /^\/app\/api(?:-keys|-usage)?\/?$/.test(path);
  const view = path === "/app/ai-systems" ? "systems" : path === "/app/legal-review" ? "legal-review" : path === "/app/false-positives" ? "false-positives" : path === "/app/projects" ? "projects" : path === "/app/audits" ? "audits" : path.includes("/findings") ? "findings" : isApiPage ? "api" : path.includes("/reviews") ? "reviews" : "overview";
  const title = view === "systems" ? "AI Systems" : view === "legal-review" ? "Legal review" : view === "false-positives" ? "False positives" : view === "projects" ? "Projects" : view === "audits" ? "Repository Scans" : view === "findings" ? "Findings" : detail ? "Code check details" : view === "api" ? "API" : view === "reviews" ? "Code Checks" : "Overview";
  if (error && !user) return <div className="auth-page"><div className="auth-card"><h1>Dashboard unavailable</h1><p>{error}</p><a href="/login" className="button-dark">Sign in</a></div></div>;
  return <CustomerShell active={view} title={title} user={user || undefined} onLogout={logout}>
    {error && <div role="alert" className="inline-error"><CircleAlert size={16}/>{error}<button onClick={()=>{setError("");load()}}>Retry</button></div>}
      {["overview", "findings", "false-positives", "legal-review"].includes(view) && <ProjectScope/>}
      {view === "systems" ? <AiSystems/> : view === "legal-review" ? <FindingsPanel legalReview/> : view === "false-positives" ? <FalsePositives/> : view === "projects" ? <CustomerProjects/> : view === "audits" ? <RepositoryAudits/> : view === "findings" ? <FindingsPanel/> : detail ? <ReviewDetail job={selectedJob} onAnswer={()=>setRefreshToken(n=>n+1)} /> : view === "api" ? <div className="customer-overview"><ApiKeys /><CustomerUsage /></div> : view === "reviews" ? <ReviewList jobs={reviews} /> : <CustomerOverview />}
  </CustomerShell>;
}

function ReviewRows({ jobs }: { jobs: Job[] }) { return <div className="review-rows">{jobs.map(job=><a href={`/app/reviews/${job.id}`} key={job.id} className="review-row"><span className={`status-mark ${job.status}`}><BookOpenCheck size={16}/></span><div className="review-row-main"><b>{job.session?.scan_result?.findings?.[0]?.title || "Code review"}</b><small>{time(job.created_at)} · AI Act · {sourceVersionLabel(job.legal_source?.version || "unknown")}</small></div><span className={`status-pill ${job.status}`}>{job.status.replaceAll("_"," ")}</span><ChevronRight size={16}/></a>)}</div>; }
function ReviewList({ jobs }: { jobs: Job[] }) {
  const [version, setVersion] = useState(() => new URLSearchParams(location.search).get("source_version") || "");
  const filtered = jobs.filter(job=>!version || (job.legal_source?.version || "unknown") === version);
  return <section className="panel list-panel">
    <div className="panel-title"><div><h2>Saved checks</h2><p>{filtered.length} saved check{filtered.length===1?"":"s"}</p></div>
      <a className="button-dark" href="/app/new"><Plus size={15}/>New code check</a>
    </div>
    {jobs.length > 0 && <div className="finding-search-tools">
      <SourceVersionFilter value={version} versions={jobs.map(job=>job.legal_source?.version || "unknown")} onChange={setVersion}/>
    </div>}
    {filtered.length > 0 ? <ReviewRows jobs={filtered}/> : jobs.length > 0
      ? <Empty title="No matching reviews" text="No saved reviews use this source version." action={<button className="findings-button" onClick={()=>setVersion("")}>Clear filter</button>}/>
      : <Empty title="No reviews yet" text="Choose a sample to create your first review." action={<a href="/app/new" className="button-dark">Start with a sample</a>}/>}
  </section>;
}
function Empty({ title, text, action }: { title:string;text:string;action:React.ReactNode }) { return <div className="empty-state"><span><BookOpenCheck/></span><h3>{title}</h3><p>{text}</p>{action}</div>; }

function ReviewDetail({ job, onAnswer }: { job: Job | null; onAnswer: () => void }) {
  const [rescanBusy, setRescanBusy] = useState(false);
  const [rescanError, setRescanError] = useState("");
  const [rescanCloud, setRescanCloud] = useState<boolean | null>(null);
  const [rescanConsent, setRescanConsent] = useState(false);
  useEffect(() => {
    request<{cloud_review_requires_consent:boolean}>("/api/review-policy")
      .then(policy=>setRescanCloud(policy.cloud_review_requires_consent))
      .catch(e=>setRescanError(e.message));
  }, []);
  async function rescan() {
    if (!job) return;
    setRescanBusy(true);
    setRescanError("");
    try {
      const next = await post<Job>(`/api/reviews/${job.id}/rescan`, {cloud_consent:rescanConsent},
        {"Idempotency-Key":crypto.randomUUID()});
      go(`/app/reviews/${next.id}`);
    } catch (e) {
      setRescanError((e as Error).message);
    } finally {
      setRescanBusy(false);
    }
  }
  const [answer,setAnswer]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const [feedbackBusy,setFeedbackBusy]=useState(""); const [feedbackError,setFeedbackError]=useState("");
  const [feedback,setFeedback]=useState<Record<string,{label:string;reason:string}>>({});
  const [reasons,setReasons]=useState<Record<string,string>>({});
  async function submitAnswer(e:FormEvent){e.preventDefault();if(!job)return;setBusy(true);setError("");try{await post(`/api/reviews/${job.id}/answer`,{answer});setAnswer("");onAnswer()}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
  async function labelSource(source:RetrievedSource,label:"relevant"|"not_relevant"|"uncertain") { if(!job)return;setFeedbackBusy(source.id);setFeedbackError("");try{const result=await post<{case_id:string;revision:number}>(`/api/reviews/${job.id}/retrieval-feedback`,{source_id:source.id,label,reason:reasons[source.id]||""});setFeedback(old=>({...old,[source.id]:{label,reason:reasons[source.id]||""}}));setFeedbackError("");void result;}catch(err){setFeedbackError((err as Error).message)}finally{setFeedbackBusy("")}}
  if(!job)return <div className="loading-screen inline"><LoaderCircle className="spin"/>Loading review</div>;
  const findings=job.session?.scan_result?.findings||[]; const waiting=job.status==="context_needed";
  const reviewErrors=[...(job.error?[job.error]:[]),...(job.session?.scan_result?.errors||[])];
  const failureMessage=job.status==="failed"?(reviewErrors[0]?.message||"The review stopped before it could finish."):null;
  return <div className="review-detail"><section className="panel detail-summary"><div className="detail-summary-main"><span className={`status-pill ${job.status}`}>{job.status.replaceAll("_"," ")}</span><h2>{findings[0]?.title||"Code review"}</h2><p>Started {time(job.created_at)} · Attempt {job.attempts}</p>
    {job.legal_source && <LegalSourceLine source={job.legal_source}/>}
    {job.legal_source && ["complete", "partial", "failed", "context_needed"].includes(job.status) && <details className="review-rescan">
      <summary>Rescan with the active AI Act source</summary>
      {rescanCloud && <label><input type="checkbox" checked={rescanConsent} onChange={event=>setRescanConsent(event.target.checked)}/> Allow sending the saved code and original context to Google Gemini</label>}
      <button className="button-dark" disabled={rescanBusy || rescanCloud === null || (rescanCloud && !rescanConsent)}
        onClick={rescan}>{rescanBusy ? "Starting…" : "Start new review"}</button>
      {rescanError && <p role="alert">{rescanError}</p>}
    </details>}
    </div></section>
    {failureMessage&&<div role="alert" className="notice-card error-card"><CircleAlert size={18}/><div><b>Review could not finish</b><p>{failureMessage}</p></div>{job.filename&&<a className="retry-sample" href={`/app/new?sample=${encodeURIComponent(job.filename)}`}>Run this sample again<ArrowRight size={14}/></a>}</div>}
    {job.status==="queued"||job.status==="running"||job.status==="answer_queued"?<section className="panel progress-panel"><LoaderCircle className="spin"/><div><b>{job.status==="queued"?"Waiting to start":job.status==="answer_queued"?"Answer saved, resuming review":"Review in progress"}</b><p>This review is still being processed. This page refreshes automatically.</p></div></section>:null}
    {waiting&&<section className="panel question-panel"><h2>{job.session?.context_question||"One detail is needed to continue."}</h2><form onSubmit={submitAnswer}><textarea rows={3} required maxLength={2000} value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Add a short explanation…"/><button className="button-dark" disabled={busy||!answer.trim()}>{busy?<LoaderCircle className="spin" size={16}/>:null}Save answer and continue<ArrowRight size={15}/></button></form>{error&&<p role="alert" className="error-text">{error}</p>}</section>}
    {!failureMessage&&job.session?.scan_result?.errors?.map(err=><div className="notice-card error-card" key={err.code}><CircleAlert size={18}/><div><b>{err.code.replaceAll("_"," ")}</b><p>{err.message}</p></div></div>)}
    <FindingList findings={findings}/>
    {job.session?.scan_result?.status==="complete"&&findings.length===0&&<section className="panel no-findings"><Check size={18}/><div><b>No findings returned.</b><p>This review is not a compliance decision.</p></div></section>}
    {job.sources.length>0&&<details className="sources-section"><summary className="sources-summary">Legal sources used ({job.sources.length}) · view passages and rate relevance</summary>{job.sources.map(source=>{const saved=feedback[source.id]||job.events.reduce<{label:string;reason:string}|null>((last,event)=>event.type==="feedback_saved"&&event.details.source_id===source.id?{label:String(event.details.label),reason:String(event.details.reason||"")}:last,null);return <article className="panel source-feedback-card" key={source.id}><div className="source-feedback-top"><div><span className="source-label">LEGAL PASSAGE</span><h3>{source.title}</h3><code>{source.id}</code></div><a href={source.url} target="_blank" rel="noreferrer">Official source <ExternalLink size={13}/></a></div><blockquote>{source.text}</blockquote><div className="source-feedback-controls"><span>Rate relevance</span>{([ ["relevant","Relevant"], ["not_relevant","Not relevant"], ["uncertain","Unsure"] ] as const).map(([value,label])=><button key={value} className={saved?.label===value?"feedback-chip selected":"feedback-chip"} disabled={feedbackBusy===source.id} onClick={()=>labelSource(source,value)}>{feedbackBusy===source.id&&saved?.label===value?<LoaderCircle className="spin" size={12}/>:saved?.label===value?<Check size={12}/>:null}{label}</button>)}</div><label className="feedback-reason">Reason (optional)<input value={reasons[source.id]??saved?.reason??""} onChange={e=>setReasons(old=>({...old,[source.id]:e.target.value}))} placeholder="Add a short note" maxLength={2000}/></label>{saved&&<p className="feedback-saved"><Check size={12}/>Saved as a draft example. It does not change retrieval.</p>}</article>})}{feedbackError&&<p role="alert" className="error-text">{feedbackError}</p>}<p className="feedback-note">Feedback stays tied to this scenario and source version. It must be approved before it enters the evaluation set.</p></details>}
    {job.session?.history?.length? <section className="panel history-panel"><div className="panel-title"><div><h2>Review history</h2><p>Questions and answers attached to this review</p></div></div>{job.session.history.map(event=><div className="history-event" key={event.id}><span className="history-marker"/><div><b>{event.type.replaceAll("_"," ")}</b><small>{time(event.created_at)} · {event.actor}</small>{event.question&&<p>{event.question}</p>}{event.answer&&<blockquote>{event.answer}</blockquote>}</div></div>)}</section>:null}
  </div>;
}
function FindingList({findings}:{findings:Finding[]}){const firstByLocation=new Map<string,{id:string;index:number}>();return <>{findings.map((finding,index)=>{const location=[finding.evidence.path,finding.evidence.start_line,finding.evidence.end_line].join(":");const first=firstByLocation.get(location);if(!first)firstByLocation.set(location,{id:finding.id,index:index+1});return <FindingCard key={finding.id} finding={finding} index={index+1} evidenceReference={first}/>;})}</>;}
function FindingCard({finding,index,evidenceReference}:{finding:Finding;index:number;evidenceReference?:{id:string;index:number}}){return <article className="panel finding-card"><div className="finding-heading"><span className="finding-number">{String(index).padStart(2,"0")}</span><div><span className="finding-kind">{finding.kind==="context_question"?"Needs context":"Potential concern"} · {finding.priority}</span><h2>{finding.title}</h2></div></div><p className="finding-explanation">{finding.explanation}</p>{evidenceReference?<div className="evidence-reference">Same code location as <a href={`#evidence-${evidenceReference.id}`}>finding {evidenceReference.index}</a>.</div>:<div className="evidence-block" id={`evidence-${finding.id}`}><div className="evidence-label"><FileCode2 size={15}/> CODE EVIDENCE <code>{finding.evidence.path}:{finding.evidence.start_line}{finding.evidence.end_line!==finding.evidence.start_line?`–${finding.evidence.end_line}`:""}</code></div><pre><code>{finding.evidence.quote}</code></pre></div>}
    {finding.citations.map(c=><div className="citation-block" key={c.section_id}><div className="evidence-label"><BookOpenCheck size={15}/> OFFICIAL TEXT <span>{c.section_id}</span></div><blockquote>{c.quote}</blockquote><a href={c.url} target="_blank" rel="noreferrer">Open official source <ExternalLink size={13}/></a></div>)}
    <div className="next-step"><b>Next step</b><p>{finding.suggested_next_action}</p></div>
    {finding.context_question&&<div className="finding-question"><b>Question</b><p>{finding.context_question}</p></div>}
  </article>}

function ApiKeys(){const [keys,setKeys]=useState<ApiKey[]>([]);const [name,setName]=useState("");const [secret,setSecret]=useState("");const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  async function reload(){try{setKeys(await request<ApiKey[]>("/api/api-keys"))}catch(e){setError((e as Error).message)}}useEffect(()=>{reload()},[]);
  async function create(e:FormEvent){e.preventDefault();setBusy(true);setError("");try{const result=await post<ApiKey & {key:string}>("/api/api-keys",{name});setSecret(result.key);setName("");await reload()}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
  async function revoke(id:string){if(!confirm("Revoke this API key? Requests using it will stop working."))return;try{await request(`/api/api-keys/${id}`,{method:"DELETE"});await reload()}catch(e){setError((e as Error).message)}}
  return <div className="keys-layout"><section className="panel keys-panel"><div className="panel-title"><div><h2>Create an API key</h2><p>Use a key to call reviews from a script.</p></div><KeyRound size={19}/></div><form className="create-key-form" onSubmit={create}><label>Key name<input value={name} onChange={e=>setName(e.target.value)} required maxLength={100} placeholder="Review script"/></label><button className="button-dark" disabled={busy||!name.trim()}>{busy?<LoaderCircle className="spin" size={15}/>:<Plus size={15}/>}Create key</button></form>
    {secret&&<div className="secret-once"><div><Check size={16}/><b>Copy this key now. It will not be shown again.</b></div><code>{secret}</code><button className="secondary" onClick={()=>navigator.clipboard.writeText(secret)}><Copy size={14}/>Copy key</button><button className="secret-dismiss" onClick={()=>setSecret("")} aria-label="Hide key">×</button></div>}
    {error&&<p className="error-text">{error}</p>}<div className="table-heading"><h3>Your keys</h3><span>{keys.length}</span></div>{keys.length?<div className="key-list">{keys.map(k=><div className="key-row" key={k.id}><span className="key-avatar"><KeyRound size={16}/></span><div className="key-info"><b>{k.name}</b><code>{k.prefix}••••{k.last_four}</code></div><div className="key-meta"><span>{k.revoked_at?"Revoked":k.last_used_at?`Last used ${time(k.last_used_at)}`:"Never used"}</span><small>Created {time(k.created_at)}</small></div>{!k.revoked_at&&<button className="icon-button danger" aria-label={`Revoke ${k.name}`} onClick={()=>revoke(k.id)}><Trash2 size={16}/></button>}</div>)}</div>:<Empty title="No API keys" text="Create a key for a review script." action={null}/>}</section>
    <aside className="panel key-help"><span className="key-help-icon"><Shield size={19}/></span><h3>Keep your key private</h3><p>Copy it to your backend. Do not commit it or put it in a browser app.</p><pre><code>Authorization: Bearer actk_…</code></pre></aside></div>;
}
