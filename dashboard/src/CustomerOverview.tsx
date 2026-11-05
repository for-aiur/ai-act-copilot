import { scopedPath } from "./CustomerProjects";
import { LegalSourceUpdates } from "./LegalSourceUpdates";
import {useEffect,useState} from "react";
import { ArrowRight, GitPullRequest } from "lucide-react";
import {codeStage, codeStages, policyLabel, type Finding} from "./FindingsPanel";
import {request} from "./api";
type QueueItem = {id:string; repository:string; pr:string; branch?:string; title:string; priority:string};
const priorities = ["high", "medium", "low"] as const;
type StageCounts = Record<(typeof priorities)[number],number>;
type Overview={open_by_code_stage?:Record<string,StageCounts>;needs_review:QueueItem[];open_high:number;awaiting_context:number;resolved_recently:number;repositories:{id:string;name:string;open:number;open_high:number;open_medium:number;open_low:number;latest_review_at:string|null;latest_review_outcome:string|null}[]};
type Repository = Overview["repositories"][number];

function reviewScore(repositories: Repository[]) {
  if (!repositories.some(repo => repo.latest_review_outcome === "complete" || repo.open > 0)) return null;
  const deduction = repositories.reduce((sum, repo) =>
    sum + 20 * repo.open_high + 8 * repo.open_medium + 3 * repo.open_low, 0);
  return Math.max(0, 100 - deduction);
}

function ProjectReviewStatus({repositories, releasedHigh}: {repositories: Repository[]; releasedHigh: number}) {
  const reviewed = repositories.filter(repo => repo.latest_review_outcome === "complete").length;
  const open = repositories.reduce((sum, repo) => sum + repo.open, 0);
  const high = repositories.reduce((sum, repo) => sum + repo.open_high, 0);
  const score = reviewScore(repositories);
  const status = high ? "Needs attention" : open ? "Review pending" : reviewed ? "No open findings" : "Awaiting review";
  const tone = score === null ? "unscored" : high ? "high" : open ? "pending" : "clear";
  return <section className="panel list-panel project-risk" data-tone={tone} aria-labelledby="project-score-heading">
    <div className="project-risk-copy">
      <h2 id="project-score-heading">Overall review score</h2>
      <span className={`findings-badge${high ? " priority-high" : open ? " priority-medium" : ""}`}>{status}</span>
      <dl className="project-score-stats">
        <div><dt>Open findings</dt><dd>{open}</dd></div>
        <div><dt>High priority</dt><dd>{high}</dd></div>
        <div><dt>Repos reviewed</dt><dd>{reviewed} / {repositories.length}</dd></div>
      </dl>
      <details><summary>How the review score works</summary>
        <p>Start at 100 and subtract 20 per open High finding, 8 per Medium and 3 per Low. The score stops at zero and measures open review work. The project score uses all findings in the selected scope.</p>
      </details>
      {releasedHigh > 0 && <a className="overview-link" href={scopedPath("/app/findings?source=github&state=open&priority=high&stage=released")}>
        {releasedHigh} open High in releases <ArrowRight size={14}/>
      </a>}
    </div>
    <div className="project-score-gauge">
      <svg viewBox="0 0 240 134" aria-hidden="true" fill="none">
        <path className="project-score-ticks" d="M 4 118 A 116 116 0 0 1 236 118" pathLength={100} strokeDasharray="0.35 4.65"/>
        <path className="project-score-track" d="M 17 118 A 103 103 0 0 1 223 118"/>
        {score !== null && score > 0 && <path className="project-score-fill" d="M 17 118 A 103 103 0 0 1 223 118"
          pathLength={100} strokeDasharray={`${score} 100`}/>}
      </svg>
      {score === null ? <strong className="project-score-unscored">Unscored</strong> :
        <strong className="project-score-number">{score}<small> / 100</small></strong>}
    </div>
  </section>;
}

function RepositoryDependencies({repositories}: {repositories: Repository[]}) {
  const caller = repositories.find(repo => repo.id === "demo-recruitment");
  const provider = repositories.find(repo => repo.id === "demo-chatbot");
  if (!caller || !provider) return null;
  return <section className="panel list-panel repository-dependencies">
    <h2>Repository dependencies</h2>
    <small>Example dependency</small>
    <div className="dependency-map">
      <DependencyNode repo={caller}/>
      <span className="dependency-edge">Calls support API <ArrowRight size={17} aria-hidden="true"/></span>
      <DependencyNode repo={provider}/>
    </div>
  </section>;
}

function DependencyNode({repo}: {repo: Repository}) {
  return <a className="dependency-node" href={scopedPath(`/app/findings?state=open&repo=${encodeURIComponent(repo.name)}`)}>
    <b>{repo.name}</b><span>{repo.open} open · {repo.open_high} High</span>
  </a>;
}

export function CustomerOverview(){
 const [data,setData]=useState<Overview|null>(null);
 const [error,setError]=useState("");
 const [chartRevision,setChartRevision]=useState(0);
 const [busy,setBusy]=useState(false);
 const [demo,setDemo]=useState(false);
 useEffect(()=>{request<{enabled:boolean}>("/api/demo/status").then(v=>setDemo(v.enabled)).catch(()=>setDemo(false))},[]);
 useEffect(()=>{request<Overview>(scopedPath("/api/customer/overview")).then(setData).catch(e=>setError(e.message))},[]);
 if(!data)return error ? <p role="alert">{error}</p> : <p>Loading overview…</p>;
 async function loadSamples() {
   setBusy(true); setError("");
   try {
     await request("/api/demo/seed", {method:"POST"});
     setData(await request<Overview>(scopedPath("/api/customer/overview")));
     setChartRevision(value => value + 1);
   } catch(e) { setError((e as Error).message); }
   finally { setBusy(false); }
 }
 const cutoff = encodeURIComponent(new Date(Date.now() - 30 * 86400000).toISOString());
 const releasedHigh = data.open_by_code_stage?.released?.high ?? 0;
 const metrics = [
   { label: "High priority in releases", value: releasedHigh, query: "state=open&priority=high&stage=released", critical: releasedHigh > 0 },
   { label: "Open high priority", value: data.open_high, query: "state=open&priority=high" },
   { label: "Awaiting context", value: data.awaiting_context, query: "state=open&context=1" },
   { label: "Resolved in 30 days", value: data.resolved_recently, query: `state=resolved&since=${cutoff}` },
 ];
 const repositories = [...data.repositories].sort(
   (a,b) => b.open_high - a.open_high || b.open - a.open || a.name.localeCompare(b.name),
 );
 return <div className="customer-overview">
   {demo && <div className="overview-bar">
     <span>Demo workspace</span>
     <button className="findings-button" disabled={busy} onClick={loadSamples}>
       {busy ? "Loading…" : "Load demo examples"}
     </button>
   </div>}
   {error && <p className="findings-error" role="alert">{error}</p>}
   <div className="kpi-grid overview-metrics overview-priority-metrics">
     {metrics.map(metric => <a className={metric.critical ? "kpi-card critical-kpi" : "kpi-card"} href={scopedPath(`/app/findings?source=github&${metric.query}`)} key={metric.label}>
       <span>{metric.label}</span><b>{metric.value}</b><ArrowRight size={16} aria-hidden="true"/>
     </a>)}
   </div>
   <ProjectReviewStatus repositories={repositories} releasedHigh={releasedHigh}/>
   <FindingCharts repositories={repositories} revision={chartRevision}/>
   <div className="overview-panels">
     <section className="panel list-panel overview-queue">
       <h2>Needs review</h2>
       {(data.needs_review ?? []).map(item =>
         <a className="findings-row" href={scopedPath(`/app/findings?finding=${encodeURIComponent(item.id)}`)} key={item.id}>
           <GitPullRequest size={17} aria-hidden="true"/>
           <span className="findings-row-copy">
             <b>{item.title}</b>
             <small>{item.repository} · PR #{item.pr}{item.branch && ` · ${item.branch}`}</small>
           </span>
           <span className={`findings-badge priority-${item.priority}`}>{item.priority}</span>
         </a>
       )}
       {!data.needs_review?.length && <p className="overview-empty">No open repository findings.</p>}
       <a className="overview-link" href={scopedPath("/app/findings?source=github")}>View open findings <ArrowRight size={14}/></a>
     </section>
     <div className="overview-side"><section className="panel list-panel overview-repositories">
       <h2>Repositories</h2>
       {repositories.map(repo =>
         <a className="review-row repository-overview-row" key={repo.id} href={scopedPath(`/app/findings?state=&repo=${encodeURIComponent(repo.name)}`)}>
           <span><b>{repo.name}</b><small>{repo.latest_review_at
             ? `Last review: ${repo.latest_review_outcome || "recorded"} · ${new Date(repo.latest_review_at).toLocaleDateString()}`
             : "Never reviewed"}</small></span>
           <span className="repository-counts"><b>{reviewScore([repo]) === null ? "Unscored" : `${reviewScore([repo])} / 100`}</b><small>{repo.open} open · {repo.open_high} High</small></span>
         </a>
       )}
       {!repositories.length && <p className="overview-empty">No repositories yet.</p>}
     </section>
     </div>
   </div>
   {demo && <RepositoryDependencies repositories={repositories}/>}
   <details className="overview-source-details">
     <summary>AI Act sources and updates</summary>
     <LegalSourceUpdates key={data.needs_review?.length ?? 0}/>
   </details>
   <a className="button-dark" href="/app/new">Start a code review</a>
 </div>;
}
type FindingLink = (filters: Record<string, string>) => string;

function FindingCharts({repositories, revision}: {repositories: Repository[]; revision: number}) {
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState("");
  const [repo, setRepo] = useState("");
  const [priority, setPriority] = useState("");
  useEffect(() => {
    let active = true;
    setError("");
    request<Finding[]>(scopedPath("/api/findings")).then(rows => {
      if (active) setFindings(rows.filter(row =>
        row.payload.source_type !== "local_review" && row.state !== "false_positive"));
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [revision]);

  const visible = (findings ?? []).filter(row =>
    (!repo || row.name === repo) && (!priority || row.priority === priority));
  const open = visible.filter(row => row.state === "open");
  const findingsLink: FindingLink = filters => {
    const params = new URLSearchParams({source: "github", state: "open"});
    if (repo) params.set("repo", repo);
    if (priority) params.set("priority", priority);
    for (const [key, value] of Object.entries(filters)) params.set(key, value);
    return scopedPath(`/app/findings?${params}`);
  };

  return <section className="overview-analytics" aria-labelledby="overview-analytics-heading">
    <header>
      <h2 id="overview-analytics-heading">Repository findings</h2>
      <div className="overview-chart-filters">
        <label>Repository <select value={repo} onChange={event => setRepo(event.target.value)}>
          <option value="">All repositories</option>
          {repositories.map(item => <option key={item.id} value={item.name}>{item.name}</option>)}
        </select></label>
        <label>Priority <select value={priority} onChange={event => setPriority(event.target.value)}>
          <option value="">All priorities</option>
          {priorities.map(level => <option key={level} value={level}>{level[0].toUpperCase() + level.slice(1)}</option>)}
        </select></label>
      </div>
    </header>
    {error ? <p role="alert">{error}</p> : findings === null ? <p role="status">Loading charts…</p> :
      <div className="overview-chart-grid">
        <PriorityChart rows={open} link={findingsLink}/>
        <CodeLifecycle rows={open} link={findingsLink}/>
        <PolicyBreakdown rows={open} link={findingsLink}/>
        <FindingTrend rows={visible}/>
      </div>}
  </section>;
}

function PolicyBreakdown({rows, link}: {rows: Finding[]; link: FindingLink}) {
  const counts = new Map<string, number>();
  for (const row of rows) {
    for (const policy of row.policies?.length ? row.policies : ["uncategorized"]) {
      counts.set(policy, (counts.get(policy) ?? 0) + 1);
    }
  }
  const policies = [...counts].sort(([a, countA], [b, countB]) => countB - countA || a.localeCompare(b)).slice(0, 5);
  const max = policies[0]?.[1] ?? 1;
  return <section className="panel list-panel policy-breakdown">
    <h3>Top policies</h3><p>Open findings by AI Act provision</p>
    {policies.length === 0 && <p className="chart-empty">No open findings in this selection.</p>}
    {policies.map(([id, count]) => <a className="policy-count-row" key={id} href={link({policy: id})}>
      <b>{policyLabel(id)}</b>
      <span className="policy-track" aria-hidden="true"><i style={{width: `${count / max * 100}%`}}/></span>
      <strong>{count}</strong>
    </a>)}
  </section>;
}

function CodeLifecycle({rows, link}: {rows: Finding[]; link: FindingLink}) {
  const counts = new Map(codeStages.map(([stage]) => [stage, {high: 0, medium: 0, low: 0}]));
  for (const row of rows) {
    const stage = counts.get(codeStage(row)[0])!;
    const priority = priorities.find(level => level === row.priority);
    if (priority) stage[priority] += 1;
  }
  const stages = codeStages.map(([key, label]) => {
    const parts = priorities.map(priority => counts.get(key)![priority]);
    return {key, label, parts, total: parts.reduce((sum, value) => sum + value, 0)};
  });
  const scale = Math.max(1, ...stages.map(stage => stage.total));
  return <section className="panel list-panel lifecycle-panel">
    <h3>Open findings by code stage</h3><p>From open pull requests to releases</p>
    <div className="lifecycle-stages">{stages.filter(stage => stage.key !== "unknown" || stage.total > 0).map(stage =>
      <a key={stage.key} href={link({stage: stage.key})}
        aria-label={`${stage.label}: ${stage.parts[0]} high, ${stage.parts[1]} medium, ${stage.parts[2]} low`}>
        <b>{stage.label}</b>
        <span className="lifecycle-track" aria-hidden="true">{stage.parts.map((count, index) =>
          <i key={priorities[index]} className={`lifecycle-${priorities[index]}`} style={{width: `${count / scale * 100}%`}}/>
        )}</span>
        <strong>{stage.total}</strong>
      </a>
    )}</div>
  </section>;
}

function PriorityChart({rows, link}: {rows: Finding[]; link: FindingLink}) {
  const colors = ["#a4543c", "#b18335", "#639279"];
  const segments = priorities.map((level, index) => ({
    level, color: colors[index], count: rows.filter(row => row.priority === level).length,
  }));
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  const high = total ? segments[0].count / total * 100 : 0;
  const mediumEnd = total ? high + segments[1].count / total * 100 : 0;
  const fill = total
    ? `conic-gradient(${colors[0]} 0 ${high}%, ${colors[1]} ${high}% ${mediumEnd}%, ${colors[2]} ${mediumEnd}% 100%)`
    : "var(--theme-inset)";
  return <section className="panel list-panel priority-panel">
    <h3>Open findings by priority</h3><p>{total} open in this selection</p>
    <div className="priority-chart">
      <div className="priority-ring" style={{background: fill}} aria-hidden="true"><b>{total}</b></div>
      <ul>{segments.map(({level, color, count}) => {
        const label = <><span style={{background: color}} aria-hidden="true"/>{level}<b>{count}</b></>;
        return <li key={level}>{count > 0 ? <a href={link({priority: level})}>{label}</a> : label}</li>;
      })}</ul>
    </div>
  </section>;
}

function FindingTrend({rows}: {rows: Finding[]}) {
  const day = 86_400_000;
  const today = Math.floor(Date.now() / day) * day;
  const firstDay = today - 41 * day;
  const counts = Array<number>(6).fill(0);
  for (const row of rows) {
    const week = Math.floor((Date.parse(row.created_at) - firstDay) / (7 * day));
    if (week >= 0 && week < counts.length) counts[week] += 1;
  }
  const max = Math.max(1, ...counts);
  const date = (offset: number) => new Date(firstDay + offset * day)
    .toLocaleDateString(undefined, {month: "short", day: "numeric", timeZone: "UTC"});
  return <section className="panel list-panel overview-trend">
    <h3>New findings over time</h3><p>Last 6 weeks · UTC</p>
    <div className="overview-trend-plot" role="list" aria-label="New findings by week">
      {counts.map((count, index) => <div role="listitem" key={index}
        aria-label={`${date(index * 7)} to ${date(index * 7 + 6)}: ${count} new findings`}
        title={`${date(index * 7)} to ${date(index * 7 + 6)}`}>
        <div className="overview-trend-track" aria-hidden="true">
          <span style={{height: `${count / max * 72}px`}}><b>{count}</b></span>
        </div>
        <small aria-hidden="true">{date(index * 7)}</small>
      </div>)}
    </div>
  </section>;
}

type Usage = {
  completed_reviews: number;
  api_requests: number;
  estimated_charge: number | null;
  currency: string | null;
  daily_requests: {date: string; requests: number}[];
};

export function CustomerUsage() {
  const [data, setData] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    request<Usage>("/api/customer/usage").then(setData).catch(e => setError(e.message));
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p role="status">Loading usage…</p>;
  const days = data.daily_requests ?? [];
  const maximum = Math.max(1, ...days.map(day => day.requests));
  const formatDate = (date: string) => new Date(date + "T00:00:00Z")
    .toLocaleDateString(undefined, {month:"short", day:"numeric", timeZone:"UTC"});
  const metrics = [
    {label:"API requests", value:data.api_requests},
    {label:"Completed reviews", value:data.completed_reviews},
    {label:"Estimated charge", value:data.estimated_charge === null
      ? "Unavailable" : `${data.currency} ${data.estimated_charge.toFixed(2)}`},
  ];
  return <div className="customer-overview">
    <section className="usage-month">
      <h2>This month</h2>
      <div className="kpi-grid overview-metrics">{metrics.map(metric =>
        <article className="kpi-card" key={metric.label}><span>{metric.label}</span><b>{metric.value}</b></article>
      )}</div>
    </section>
    <section className="panel list-panel usage-chart-panel">
      <h2>Daily API requests</h2>
      <p>Last 14 days · UTC</p>
      <div className="usage-chart" role="list" aria-label="Daily request counts">
        {days.map(day => <div role="listitem" key={day.date} title={`${formatDate(day.date)} · ${day.requests} requests`}
          aria-label={`${formatDate(day.date)} · ${day.requests} requests`}>
          <span style={{height:`${day.requests / maximum * 100}%`}} aria-hidden="true"/>
        </div>)}
      </div>
      {days.length > 0 && <div className="usage-chart-dates">
        <span>{formatDate(days[0].date)}</span><span>{formatDate(days[days.length - 1].date)}</span>
      </div>}
      {days.every(day => day.requests === 0) && <p>No API requests in this period.</p>}
    </section>
  </div>;
}
