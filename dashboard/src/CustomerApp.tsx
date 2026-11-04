import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  BookOpenCheck,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Copy,
  ExternalLink,
  FileCode2,
  KeyRound,
  Layers3,
  LoaderCircle,
  LogOut,
  Plus,
  Shield,
  Trash2,
} from "lucide-react";
import { request } from "./api";
import type { Versions } from "./rag";
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
type Timing = { stage: string; elapsed_ms: number; status: string };
type RetrievedSource = { id: string; document_id: string; title: string; text: string; url: string };
type Job = { id: string; status: string; attempts: number; created_at: string; updated_at: string;
  session: ReviewSession | null; error: { code: string; message: string } | null;
  events: { revision: number; type: string; created_at: string; details: Record<string, unknown> }[];
  trace_id: string | null; trace_url: string | null; timings: Timing[];
  retrieval_request: Record<string, unknown> | null; sources: RetrievedSource[] };
type ApiKey = { id: string; name: string; prefix: string; last_four: string; created_at: string;
  last_used_at: string | null; revoked_at: string | null };
type ApiUsage = { id: string; route: string; status_code: number; elapsed_ms: number; created_at: string };
type Health = { status: string; worker: string; storage: string };
type ReviewSummary = { total: number; by_status: Record<string,number> };
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
function duration(ms: number) { return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`; }

export function PublicHome() {
  return <div className="public-site">
    <header className="public-nav">
      <a className="public-brand" href="/"><img src="/copilot-logo.png" alt="" /><span>AI Act Copilot</span></a>
      <nav><a href="#how-it-works">How it works</a><a href="https://github.com/for-aiur/ai-act-copilot" target="_blank" rel="noreferrer">GitHub <ExternalLink size={14} /></a><a className="nav-login" href="/login">Sign in</a><a className="button-dark" href="/login">View the demo <ArrowRight size={15} /></a></nav>
    </header>
    <main className="public-main">
      <section className="public-hero">
        <div className="hero-copy"><div className="public-kicker"><span /> ENGINEERING REVIEW FOR AI SYSTEMS</div>
          <h1>See the code.<br /><em>See the rule.</em></h1>
          <p>AI Act Copilot helps engineering teams inspect how AI is used in Python code, find relevant official EU text, and ask the next useful question.</p>
          <div className="hero-actions"><a className="button-dark" href="/login">Open the demo <ArrowRight size={16} /></a><a className="text-link" href="#how-it-works">See how it works <ChevronRight size={15} /></a></div>
          <div className="hero-note"><Shield size={15} /> Code is sent to Gemini only when you approve a review.</div>
        </div>
        <div className="hero-visual" aria-label="A code review connected to legal evidence">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="visual-center"><img src="/copilot-logo.png" alt="AI Act Copilot" /></div>
          <div className="visual-card code-card"><FileCode2 size={16} /><span><b>Code</b><small>Exact source line</small></span><span className="visual-dot" /></div>
          <div className="visual-card law-card"><BookOpenCheck size={16} /><span><b>Official text</b><small>Quoted and linked</small></span><span className="visual-dot" /></div>
          <div className="visual-caption">One review, with evidence attached</div>
        </div>
      </section>
      <section className="product-links"><div><span className="link-icon"><Layers3 size={18} /></span><div><b>Review tools</b><p>Explore sources, RAG versions and test cases.</p></div><a href="/workbench" aria-label="Open review tools"><ArrowRight size={17} /></a></div>
        <div><span className="link-icon"><FileCode2 size={18} /></span><div><b>VS Code extension guide</b><p>Local install and setup instructions.</p></div><a href="https://github.com/for-aiur/ai-act-copilot/blob/main/extensions/vscode/README.md" target="_blank" rel="noreferrer" aria-label="Open VS Code extension guide"><ExternalLink size={16} /></a></div>
        <div><span className="link-icon"><Activity size={18} /></span><div><b>GitHub review bot</b><p>Set up the GitHub App for repository reviews.</p></div><a href="https://github.com/for-aiur/ai-act-copilot/blob/main/docs/GITHUB-APP.md" target="_blank" rel="noreferrer" aria-label="Open GitHub App setup guide"><ExternalLink size={16} /></a></div>
      </section>
      <section id="how-it-works" className="public-how"><div className="public-section-title"><span>THE REVIEW FLOW</span><h2>From code to a useful next step.</h2></div>
        <div className="flow-cards"><article><span>01</span><FileCode2 /><h3>Share a sample</h3><p>Start with one of three short examples or your own local source.</p></article><article><span>02</span><Layers3 /><h3>Find the right text</h3><p>The active, versioned RAG retrieves official passages for the scenario.</p></article><article><span>03</span><BookOpenCheck /><h3>Review with evidence</h3><p>Inspect the code line, legal quote and any question that needs context.</p></article></div>
      </section>
      <footer className="public-footer"><span>AI Act Copilot by Evros Labs</span><span>Engineering support, not a compliance certificate.</span><a href="/login">Sign in</a></footer>
    </main>
  </div>;
}

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function enterDemo() { setBusy(true); setError("");
    try { await post<User>("/api/auth/demo", {}); go("/onboarding"); }
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
  const [sample, setSample] = useState(samples[0]); const [versions, setVersions] = useState<Versions | null>(null);
  const [cloudConsent, setCloudConsent] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => { request<User>("/api/auth/me").then(setUser).catch(() => go("/login")); request<Versions>("/api/rag/versions?domain=ai-act").then(setVersions).catch(() => setVersions(null)); }, []);
  async function start() { setBusy(true); setError(""); try {
    const idempotency = crypto.randomUUID(); const job = await post<Job>("/api/reviews", {
      code: sample.code, filename: sample.filename, context: sample.scenario, cloud_consent: cloudConsent,
    }, { "Idempotency-Key": idempotency }); go(`/app/reviews/${job.id}`);
  } catch (e) { setError(e instanceof Error ? e.message : "Review could not be started."); } finally { setBusy(false); } }
  if (!user) return <div className="loading-screen"><LoaderCircle className="spin"/>Preparing the demo</div>;
  async function logout() { await fetch("/api/auth/logout", { method: "POST" }); go("/"); }
  return <CustomerShell active="" title="Your first review" subtitle="Start with a sample. You can explore your review history after it runs." user={user} onLogout={logout} >
    <div className="onboard-layout"><section className="panel onboard-panel"><div className="step-pill">GETTING STARTED <span>1 / 2</span></div><h2>Choose a sample scenario</h2><p>These examples are short and synthetic. They contain no real people or customer data.</p>
      <div className="sample-picker">{samples.map(item => <button key={item.name} className={sample.name === item.name ? "sample-choice selected" : "sample-choice"} onClick={() => setSample(item)}><span className="sample-choice-icon"><FileCode2 size={18} /></span><span><b>{item.name}</b><small>{item.filename}</small></span>{sample.name === item.name && <Check size={17} />}</button>)}</div>
      <label className="field-label">Scenario description<textarea readOnly rows={3} value={sample.scenario} /></label>
      {versions?.provider === "gemini" && <label className="consent-card"><input type="checkbox" checked={cloudConsent} onChange={e => setCloudConsent(e.target.checked)} /><span><b>Allow this sample to be sent to Google Gemini for review.</b><small>This sends the sample code and context to Google for this review.</small></span></label>}
      {error && <div role="alert" className="inline-error"><CircleAlert size={16} />{error}</div>}
      <div className="onboard-actions"><button className="button-dark" onClick={start} disabled={busy || (versions?.provider === "gemini" && !cloudConsent)}>{busy ? <LoaderCircle className="spin" size={16} /> : <BookOpenCheck size={16} />}Run sample review<ArrowRight size={16} /></button><a href="/app">Skip for now</a></div>
      <p className="small-note">Reviews use the active RAG version selected in Review tools. <a href="/workbench">Open workbench</a></p>
    </section><aside className="onboard-side"><div className="onboard-side-mark"><img src="/copilot-logo.png" alt="" /></div><h3>What happens next?</h3><ol><li><span>1</span><div><b>Your sample is reviewed</b><small>The code is read, never executed.</small></div></li><li><span>2</span><div><b>Evidence stays together</b><small>See the source line and official text side by side.</small></div></li><li><span>3</span><div><b>Answer one question</b><small>If context is missing, add it and resume.</small></div></li></ol><p>Zero findings never means certified compliance.</p></aside></div>
  </CustomerShell>;
}

function CustomerShell({ active, title, subtitle, children, user, onLogout }: { active: string; title: string; subtitle: string; children: ReactNode; user?: User; onLogout?: () => void }) {
  const links = [{ id: "overview", label: "Overview", href: "/app", icon: Activity }, { id: "reviews", label: "Reviews", href: "/app/reviews", icon: BookOpenCheck }, { id: "keys", label: "API keys", href: "/app/api-keys", icon: KeyRound }, { id: "usage", label: "API usage", href: "/app/api-usage", icon: Clock3 }];
  return <div className="customer-shell"><aside className="customer-sidebar"><a href="/" className="customer-logo"><img src="/copilot-logo.png" alt="" /><span>AI Act Copilot<small>DEMO ACCOUNT</small></span></a><div className="workspace-chip"><span>{(user?.workspace || "Demo team").slice(0,1).toUpperCase()}</span><div><b>{user?.workspace || "AI Act Demo"}</b><small>{user?.email || "Getting started"}</small></div></div><nav aria-label="Main navigation">{links.map(({id,label,href,icon:Icon}) => <a className={active===id?"customer-nav active":"customer-nav"} href={href} key={id}><Icon size={17}/>{label}</a>)}</nav><div className="sidebar-spacer"/><a className="customer-nav" href="/workbench"><Layers3 size={17}/>RAG workbench</a><button className="customer-nav logout-link" onClick={onLogout}><LogOut size={17}/>Sign out</button><div className="sidebar-foot">Sample account<br/>Demo data</div></aside>
    <main className="customer-main"><header className="customer-top"><div><span className="live-dot"/> AI Act Copilot</div><div className="top-user"><span>{(user?.email || "").slice(0,1).toUpperCase()}</span>{user?.email}</div></header><div className="customer-content"><div className="customer-heading"><div><div className="customer-breadcrumb">DASHBOARD <ChevronRight size={13}/>{title.toUpperCase()}</div><h1>{title}</h1><p>{subtitle}</p></div></div>{children}</div></main></div>;
}

export function CustomerDashboard() {
  const [user, setUser] = useState<User | null>(null); const [path, setPath] = useState(location.pathname);
  const [reviews, setReviews] = useState<Job[]>([]); const [summary, setSummary] = useState<ReviewSummary>({total:0,by_status:{}}); const [usage, setUsage] = useState<ApiUsage[]>([]); const [health, setHealth] = useState<Health | null>(null); const [versions, setVersions] = useState<Versions | null>(null);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const [refreshToken, setRefreshToken] = useState(0);
  async function load() { try { const me=await request<User>("/api/auth/me"); setUser(me); const [jobs, counts, calls, state, v] = await Promise.all([
    request<Job[]>("/api/reviews"), request<ReviewSummary>("/api/reviews/summary"), request<ApiUsage[]>("/api/api-usage"), request<Health>("/api/system/health"), request<Versions>("/api/rag/versions?domain=ai-act")]);
    setReviews(jobs); setSummary(counts); setUsage(calls); setHealth(state); setVersions(v); setError("");
  } catch (e) { if ((e as Error).message.toLowerCase().includes("sign in")) go("/login"); else setError((e as Error).message); } finally { setLoading(false); } }
  useEffect(() => { load(); const onPop = () => setPath(location.pathname); addEventListener("popstate", onPop); return () => removeEventListener("popstate", onPop); }, []);
  useEffect(() => { if (/^\/app\/reviews\/[^/]+$/.test(path)) { const id = path.split("/").pop()!; let live=true; let timer: ReturnType<typeof setTimeout>; const poll=async()=>{ try { const job=await request<Job>(`/api/reviews/${id}`); if(live)setSelectedJob(job); if(live&&["queued","running","answer_queued"].includes(job.status)) timer=setTimeout(poll,1200); } catch(e) { if(live)setError((e as Error).message); } }; poll(); return()=>{live=false;clearTimeout(timer)}; } }, [path, refreshToken]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  async function logout() { await fetch("/api/auth/logout", { method: "POST" }); go("/"); }
  if (loading) return <div className="loading-screen"><LoaderCircle className="spin"/>Loading the dashboard</div>;
  const detail = /^\/app\/reviews\/([^/]+)$/.test(path);
  const view = path.includes("/api-keys") ? "keys" : path.includes("/api-usage") ? "usage" : path.includes("/reviews") ? "reviews" : "overview";
  const title = detail ? "Review details" : view === "keys" ? "API keys" : view === "usage" ? "API usage" : view === "reviews" ? "Review history" : "Overview";
  if (error && !user) return <div className="auth-page"><div className="auth-card"><h1>Dashboard unavailable</h1><p>{error}</p><a href="/login" className="button-dark">Sign in</a></div></div>;
  return <CustomerShell active={view} title={title} subtitle={detail ? "Review evidence, findings and the path taken." : view === "overview" ? "A clear view of review activity." : view === "reviews" ? "Reviews created by this demo account." : view === "keys" ? "Create and manage API keys." : "Measured requests made with API keys."} user={user || undefined} onLogout={logout}>
    {error && <div role="alert" className="inline-error"><CircleAlert size={16}/>{error}<button onClick={()=>{setError("");load()}}>Retry</button></div>}
      {detail ? <ReviewDetail job={selectedJob} onAnswer={()=>setRefreshToken(n=>n+1)} /> : view === "keys" ? <ApiKeys /> : view === "usage" ? <UsagePanel usage={usage} /> : view === "reviews" ? <ReviewList jobs={reviews} /> : <Overview reviews={reviews} summary={summary} usage={usage} health={health} versions={versions} />}
  </CustomerShell>;
}

function Overview({ reviews, summary, usage, health, versions }: { reviews: Job[]; summary:ReviewSummary; usage: ApiUsage[]; health: Health | null; versions: Versions | null }) {
  const completed = summary.by_status.complete||0; const running = (summary.by_status.queued||0)+(summary.by_status.running||0)+(summary.by_status.answer_queued||0);
  const durations = reviews.flatMap(r=>r.session?.scan_result?.metadata.elapsed_ms ? [r.session.scan_result.metadata.elapsed_ms] : []).sort((a,b)=>a-b);
  const median = durations.length ? durations[Math.floor((durations.length-1)/2)] : null;
  return <><div className="overview-actions"><div className="active-rag"><span className="live-dot"/><div><small>ACTIVE RAG VERSION</small><b>{versions?.active ? versions.active.slice(0,12) : "No active version"}</b><span>{versions?.provider || "Provider not set"} · {versions?.model || "model not set"}</span></div></div><a className="button-dark" href="/onboarding"><Plus size={16}/>Start a review</a></div>
    {!versions?.active && <div className="notice-card"><CircleAlert size={18}/><div><b>Build and activate a RAG version first.</b><p>Reviews use the active version selected in Review tools.</p></div><a href="/workbench">Open workbench <ArrowRight size={15}/></a></div>}
    <div className="kpi-grid"><Kpi icon={<BookOpenCheck/>} label="Total reviews" value={summary.total.toString()} note={`${running} in progress`} /><Kpi icon={<Check/>} label="Completed" value={completed.toString()} note="From saved review jobs" /><Kpi icon={<Clock3/>} label="Median review time" value={median===null?"—":duration(median)} note={durations.length ? `Recent ${durations.length} completed reviews` : "No completed reviews yet"}/><Kpi icon={<Activity/>} label="API calls" value={usage.length.toString()} note="Latest 100 key-authenticated calls" /></div>
    <div className="dashboard-columns"><section className="panel recent-panel"><div className="panel-title"><div><h2>Recent reviews</h2><p>Latest activity</p></div><a href="/app/reviews">See all <ArrowRight size={14}/></a></div>{reviews.length ? <ReviewRows jobs={reviews.slice(0,5)}/> : <Empty title="No reviews yet" text="Start with a short sample to see how reviews work." action={<a href="/onboarding" className="button-dark">Choose a sample <ArrowRight size={14}/></a>}/>}</section>
      <section className="panel health-panel"><div className="panel-title"><div><h2>System health</h2><p>Service status</p></div><span className="health-badge"><i/> {health?.status || "Checking"}</span></div><div className="health-row"><span>Review worker</span><b>{health?.worker || "—"}</b></div><div className="health-row"><span>Storage</span><b>{health?.storage || "—"}</b></div><div className="health-row"><span>Langfuse tracing</span><b>{versions?.tracing_enabled ? "Enabled" : "Not enabled"}</b></div><a className="health-link" href="/app/api-usage">View API usage <ArrowRight size={14}/></a></section></div>
    <div className="quiet-note"><Shield size={15}/> Metrics show this demo account’s activity.</div>
  </>;
}
function Kpi({ icon, label, value, note }: { icon: React.ReactNode; label: string; value: string; note: string }) { return <article className="kpi-card"><span className="kpi-icon">{icon}</span><span className="kpi-label">{label}</span><b>{value}</b><small>{note}</small></article>; }
function ReviewRows({ jobs }: { jobs: Job[] }) { return <div className="review-rows">{jobs.map(job=><a href={`/app/reviews/${job.id}`} key={job.id} className="review-row"><span className={`status-mark ${job.status}`}><BookOpenCheck size={16}/></span><div className="review-row-main"><b>{job.session?.scan_result?.findings?.[0]?.title || "Code review"}</b><small>{time(job.created_at)} · {job.session?.scan_result?.metadata.provider || "Review pending"}</small></div><span className={`status-pill ${job.status}`}>{job.status.replaceAll("_"," ")}</span><ChevronRight size={16}/></a>)}</div>; }
function ReviewList({ jobs }: { jobs: Job[] }) { return <section className="panel list-panel"><div className="panel-title"><div><h2>All reviews</h2><p>{jobs.length} saved review{jobs.length===1?"":"s"}</p></div><a className="button-dark" href="/onboarding"><Plus size={15}/>New review</a></div>{jobs.length?<ReviewRows jobs={jobs}/>:<Empty title="No reviews yet" text="Choose a sample to create your first review." action={<a href="/onboarding" className="button-dark">Start with a sample</a>}/>}</section>; }
function Empty({ title, text, action }: { title:string;text:string;action:React.ReactNode }) { return <div className="empty-state"><span><BookOpenCheck/></span><h3>{title}</h3><p>{text}</p>{action}</div>; }

function ReviewDetail({ job, onAnswer }: { job: Job | null; onAnswer: () => void }) {
  const [answer,setAnswer]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const [feedbackBusy,setFeedbackBusy]=useState(""); const [feedbackError,setFeedbackError]=useState("");
  const [feedback,setFeedback]=useState<Record<string,{label:string;reason:string}>>({});
  const [reasons,setReasons]=useState<Record<string,string>>({});
  async function submitAnswer(e:FormEvent){e.preventDefault();if(!job)return;setBusy(true);setError("");try{await post(`/api/reviews/${job.id}/answer`,{answer});setAnswer("");onAnswer()}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
  async function labelSource(source:RetrievedSource,label:"relevant"|"not_relevant"|"uncertain") { if(!job)return;setFeedbackBusy(source.id);setFeedbackError("");try{const result=await post<{case_id:string;revision:number}>(`/api/reviews/${job.id}/retrieval-feedback`,{source_id:source.id,label,reason:reasons[source.id]||""});setFeedback(old=>({...old,[source.id]:{label,reason:reasons[source.id]||""}}));setFeedbackError("");void result;}catch(err){setFeedbackError((err as Error).message)}finally{setFeedbackBusy("")}}
  if(!job)return <div className="loading-screen inline"><LoaderCircle className="spin"/>Loading review</div>;
  const findings=job.session?.scan_result?.findings||[]; const waiting=job.status==="context_needed";
  return <div className="review-detail"><section className="panel detail-summary"><div className="detail-summary-main"><span className={`status-pill ${job.status}`}>{job.status.replaceAll("_"," ")}</span><h2>{findings[0]?.title||"Code review"}</h2><p>Started {time(job.created_at)} · Attempt {job.attempts} · RAG {job.session?.rag_release_id?.slice(0,12)||"pending"}</p></div>{job.trace_url&&<a className="secondary" href={job.trace_url} target="_blank" rel="noreferrer">Open Langfuse trace <ExternalLink size={14}/></a>}</section>
    {job.error&&<div className="notice-card error-card"><CircleAlert size={18}/><div><b>Review could not finish</b><p>{job.error.message}</p></div></div>}
    {job.status==="queued"||job.status==="running"||job.status==="answer_queued"?<section className="panel progress-panel"><LoaderCircle className="spin"/><div><b>{job.status==="queued"?"Waiting to start":job.status==="answer_queued"?"Answer saved, resuming review":"Review in progress"}</b><p>The review runs against the RAG version shown above. This page refreshes automatically.</p></div></section>:null}
    {job.timings.length>0&&<section className="panel timing-panel"><div className="panel-title"><div><h2>Review steps</h2><p>Measured time for this review</p></div><span>{duration(job.timings.reduce((n,s)=>n+s.elapsed_ms,0))} total</span></div><div className="timing-list">{job.timings.map(step=><div className="timing-row" key={step.stage}><span className="timing-dot"/><b>{stageName(step.stage)}</b><span>{duration(step.elapsed_ms)}</span></div>)}</div></section>}
    {job.sources.length>0&&<section className="sources-section"><div className="sources-heading"><div><h2>Legal sources used</h2><p>Was each passage useful for this scenario?</p></div><span>{job.sources.length} passages</span></div>{job.sources.map(source=>{const saved=feedback[source.id]||job.events.reduce<{label:string;reason:string}|null>((last,event)=>event.type==="feedback_saved"&&event.details.source_id===source.id?{label:String(event.details.label),reason:String(event.details.reason||"")}:last,null);return <article className="panel source-feedback-card" key={source.id}><div className="source-feedback-top"><div><span className="source-label">LEGAL PASSAGE</span><h3>{source.title}</h3><code>{source.id}</code></div><a href={source.url} target="_blank" rel="noreferrer">Official source <ExternalLink size={13}/></a></div><blockquote>{source.text}</blockquote><div className="source-feedback-controls"><span>Rate relevance</span>{([ ["relevant","Relevant"], ["not_relevant","Not relevant"], ["uncertain","Unsure"] ] as const).map(([value,label])=><button key={value} className={saved?.label===value?"feedback-chip selected":"feedback-chip"} disabled={feedbackBusy===source.id} onClick={()=>labelSource(source,value)}>{feedbackBusy===source.id&&saved?.label===value?<LoaderCircle className="spin" size={12}/>:saved?.label===value?<Check size={12}/>:null}{label}</button>)}</div><label className="feedback-reason">Reason (optional)<input value={reasons[source.id]??saved?.reason??""} onChange={e=>setReasons(old=>({...old,[source.id]:e.target.value}))} placeholder="Add a short note" maxLength={2000}/></label>{saved&&<p className="feedback-saved"><Check size={12}/>Saved as a draft example. It does not change retrieval.</p>}</article>})}{feedbackError&&<p role="alert" className="error-text">{feedbackError}</p>}<p className="feedback-note">Feedback stays tied to this scenario and source version. It must be approved before it enters the evaluation set.</p></section>}
    {waiting&&<section className="panel question-panel"><div className="step-pill">NEEDS YOUR CONTEXT</div><h2>{job.session?.context_question||"One detail is needed to continue."}</h2><p>Your answer continues this same review. It does not start over.</p><form onSubmit={submitAnswer}><textarea rows={3} required maxLength={2000} value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Add a short explanation…"/><button className="button-dark" disabled={busy||!answer.trim()}>{busy?<LoaderCircle className="spin" size={16}/>:null}Save answer and continue<ArrowRight size={15}/></button></form>{error&&<p role="alert" className="error-text">{error}</p>}</section>}
    {job.session?.scan_result?.errors?.map(err=><div className="notice-card error-card" key={err.code}><CircleAlert size={18}/><div><b>{err.code.replaceAll("_"," ")}</b><p>{err.message}</p></div></div>)}
    {findings.map((finding,index)=><FindingCard key={finding.id} finding={finding} index={index+1}/>)}
    {job.session?.scan_result?.status==="complete"&&findings.length===0&&<section className="panel no-findings"><Check size={18}/><div><b>No findings returned.</b><p>This review is not a compliance decision.</p></div></section>}
    {job.session?.history?.length? <section className="panel history-panel"><div className="panel-title"><div><h2>Review history</h2><p>Questions and answers attached to this review</p></div></div>{job.session.history.map(event=><div className="history-event" key={event.id}><span className="history-marker"/><div><b>{event.type.replaceAll("_"," ")}</b><small>{time(event.created_at)} · {event.actor}</small>{event.question&&<p>{event.question}</p>}{event.answer&&<blockquote>{event.answer}</blockquote>}</div></div>)}</section>:null}
  </div>;
}
function stageName(stage:string){return ({code_collection:"Read source code",purpose_extraction:"Understand the use",legal_retrieval:"Find legal text",legal_review:"Review against sources",evidence_validation:"Check evidence"} as Record<string,string>)[stage]||stage.replaceAll("_"," ")}
function FindingCard({finding,index}:{finding:Finding;index:number}){return <article className="panel finding-card"><div className="finding-heading"><span className="finding-number">{String(index).padStart(2,"0")}</span><div><span className="finding-kind">{finding.kind==="context_question"?"Needs context":"Potential concern"} · {finding.priority}</span><h2>{finding.title}</h2></div></div><p className="finding-explanation">{finding.explanation}</p><div className="evidence-block"><div className="evidence-label"><FileCode2 size={15}/> CODE EVIDENCE <code>{finding.evidence.path}:{finding.evidence.start_line}{finding.evidence.end_line!==finding.evidence.start_line?`–${finding.evidence.end_line}`:""}</code></div><pre><code>{finding.evidence.quote}</code></pre></div>
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
    <aside className="panel key-help"><span className="key-help-icon"><Shield size={19}/></span><h3>Keep your key private</h3><p>Copy it to your backend. Do not commit it or put it in a browser app.</p><pre><code>Authorization: Bearer actk_…</code></pre><a href="/app/api-usage">See key usage <ArrowRight size={14}/></a></aside></div>;
}

function UsagePanel({usage}:{usage:ApiUsage[]}){const calls=usage.length;const errors=usage.filter(x=>x.status_code>=400).length;const avg=calls?Math.round(usage.reduce((n,x)=>n+x.elapsed_ms,0)/calls):0;
  return <><div className="usage-kpis"><Kpi icon={<Activity/>} label="Recent calls" value={calls.toString()} note="Latest 100 records"/><Kpi icon={<CircleAlert/>} label="Error responses" value={errors.toString()} note="HTTP 400 and above"/><Kpi icon={<Clock3/>} label="Average response" value={calls?duration(avg):"—"} note="Measured elapsed time"/></div><section className="panel usage-panel"><div className="panel-title"><div><h2>Recent API calls</h2><p>Only requests using API keys appear here.</p></div></div>{usage.length?<div className="usage-table"><div className="usage-table-head"><span>Route</span><span>Status</span><span>Time</span><span>When</span></div>{usage.map(item=><div className="usage-table-row" key={item.id}><code>{item.route}</code><span className={item.status_code>=400?"http-status failed":"http-status"}>{item.status_code}</span><span>{duration(item.elapsed_ms)}</span><span>{time(item.created_at)}</span></div>)}</div>:<Empty title="No calls recorded" text="API key requests will appear here with their actual status and response time." action={<a href="/app/api-keys" className="button-dark">Create an API key</a>}/>}</section></>;
}
