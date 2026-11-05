import { fpCategories } from "./fpCategories";
import { scopedPath } from "./CustomerProjects";
import { useEffect, useState } from "react";
import { SourceVersionFilter, sourceVersionLabel } from "./LegalSourceUpdates";
import { request } from "./api";

export type Finding = {legal_request?:{actor:string;reason:string;created_at:string} | null;fp_mark?:{pending:boolean;actor:string;reason:string;category?:string} | null;source_version?:string | null;policies?:string[];id:string; name:string; pr:string; head:string; priority:string; state:string; created_at:string; updated_at:string; payload:{code_stage?:string;release_tag?:string;branch?:string;title?:string; explanation?:string;context_question?:string;source_type?:string;source_review_id?:string;review_status?:string;code_sample?:string;evidence?:{path:string;start_line?:number;end_line?:number;quote:string}; citations?:{section_id?:string;quote:string;url:string}[]}};
export const codeStages = [
  ["open_pr", "Open PR"],
  ["merged", "Merged"],
  ["released", "Released"],
  ["unknown", "Stage unknown"],
] as const;

export function policyLabel(id: string) {
  const names: Record<string,string> = {
    "article-14": "Article 14 · Human oversight",
    "article-50": "Article 50 · Transparency",
    "annex-iii": "Annex III · High-risk use cases",
    uncategorized: "Uncategorized",
  };
  if (names[id]) return names[id];
  if (id.startsWith("annex-")) return `Annex ${id.slice(6).toUpperCase()}`;
  return id.replaceAll("-", " ").replace(/^./, value => value.toUpperCase());
}

function findingSource(finding: Finding) {
  return finding.source_version || "unknown";
}

export function codeStage(finding: Finding) {
  return codeStages.find(([key]) => key === finding.payload.code_stage) ?? codeStages[3];
}
function githubCodeUrl(finding: Finding) {
  const evidence = finding.payload.evidence;
  const path = evidence?.path.split("/") ?? [];
  if (finding.payload.source_type === "local_review" || finding.id.startsWith("demo-")
    || !/^[\w.-]+\/[\w.-]+$/.test(finding.name) || !/^[a-f0-9]{7,64}$/i.test(finding.head)
    || !evidence?.start_line || path.some(part=>!part || part === "." || part === "..")) return null;
  const lines = `#L${evidence.start_line}${evidence.end_line && evidence.end_line !== evidence.start_line ? `-L${evidence.end_line}` : ""}`;
  return `https://github.com/${finding.name}/blob/${finding.head}/${path.map(encodeURIComponent).join("/")}${lines}`;
}

type Decision = {id:string;actor:string;action:string;reason:string;created_at:string;sync_status:string};
export function FindingsPanel({falsePositives = false,legalReview = false,onDecision}: {falsePositives?:boolean;legalReview?:boolean;onDecision?:()=>void} = {}) {
  const [showAll, setShowAll] = useState(false);
  const [category,setCategory] = useState("");
  const [rows,setRows]=useState<Finding[]>([]);
  const [repo,setRepo]=useState(new URLSearchParams(location.search).get("repo") || "");
  const [priority,setPriority]=useState(new URLSearchParams(location.search).get("priority") || "");
  const [state,setState]=useState(new URLSearchParams(location.search).get("state") ?? (falsePositives ? "" : "open"));
  const [selected,setSelected]=useState<Finding|null>(null);
  const [history,setHistory]=useState<Decision[]>([]);
  const [reason,setReason]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [saved,setSaved]=useState("");
  const [savedFinding,setSavedFinding]=useState<Finding|null>(null);
  const actions = [
    {value:"unsure",label:"Unsure · send to Legal",help:"Ask Legal to review the finding."},
    {value:"acknowledged",label:"Acknowledge",help:"Record that you have reviewed this finding."},
    {value:"false_positive",label:"Mark false positive",help:"Explain why this concern does not apply."},
    {value:"resolved",label:"Resolve",help:"Explain how the concern was addressed."},
    {value:"open",label:"Reopen",help:"Return this finding to the open list."},
    {value:"context",label:"Add context",help:"Save an explanation for further review."},
  ];
  async function load() {
    try {
      const loaded = await request<Finding[]>(scopedPath("/api/findings"));
      setRows(loaded);
      setError("");
      return loaded;
    }
    catch(e){setError((e as Error).message);}
    finally {setLoading(false);}
  }
  useEffect(()=>{
    load().then(loaded=>{
      const id = new URLSearchParams(location.search).get("finding");
      const target = loaded?.find(row=>row.id===id);
      if (target) void open(target);
    });
  },[]);
  async function open(row:Finding) {
    setSelected(row);setHistory([]);setReason("");setCategory("");setError("");
    try {setHistory(await request<Decision[]>(`/api/findings/${encodeURIComponent(row.id)}/history`));}
    catch(e){setError((e as Error).message);}
  }
  useEffect(() => {
    if (selected) {
      document.getElementById("finding-detail")?.focus();
    }
  }, [selected]);
  async function decide(action:string, fromPr=false) {
    if(!selected)return;
    setBusy(true);setError("");
    try {
      const decision = await request<{action:string}>(fromPr ? `/api/demo/findings/${encodeURIComponent(selected.id)}/pr-reply` : `/api/findings/${encodeURIComponent(selected.id)}/decision`,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({head:selected.head,action,reason,category:action === "false_positive" && category ? category : null,event_id:crypto.randomUUID()})});
      setSaved(decision.action === "unsure" ? "Sent to Legal review." : decision.action === "fp_pending" ? "Mark saved. Awaiting approval." : fromPr ? "Simulated PR reply saved." : "Decision saved.");
      setSavedFinding(selected);
      setSelected(null);await load();onDecision?.();
    }catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  }
  const [stage, setStage] = useState(() => new URLSearchParams(location.search).get("stage") || "");
  const [sourceVersion, setSourceVersion] = useState(() => {
    const version = new URLSearchParams(location.search).get("source_version");
    return version === "synthetic" ? "unknown" : version || "";
  });
  const [policy, setPolicy] = useState(() => new URLSearchParams(location.search).get("policy") || "");
  const [query, setQuery] = useState("");
  const [contextOnly, setContextOnly] = useState(() => new URLSearchParams(location.search).has("context"));
  const [githubOnly, setGithubOnly] = useState(() => new URLSearchParams(location.search).get("source") === "github");
  const [since, setSince] = useState(() => new URLSearchParams(location.search).get("since") || "");
  const [order, setOrder] = useState("priority");
  const releasedHigh = stage === "released" && priority === "high" && state === "open";
  function clearFilters() {
    setRepo(""); setPriority(""); setState(""); setStage("");
    setQuery(""); setPolicy(""); setSourceVersion(""); setContextOnly(false); setGithubOnly(false); setSince("");
  }
  function toggleReleasedHigh() {
    setStage(releasedHigh ? "" : "released");
    setPriority(releasedHigh ? "" : "high");
    setState(releasedHigh ? "" : "open");
    setSince("");
  }
  const filters = [
    {label:query.trim() && `Search: ${query.trim()}`, clear:()=>setQuery("")},
    {label:sourceVersion && sourceVersionLabel(sourceVersion), clear:()=>setSourceVersion("")},
    {label:policy && policyLabel(policy), clear:()=>setPolicy("")},
    {label:repo, clear:()=>setRepo("")},
    {label:priority && `Priority: ${priority}`, clear:()=>setPriority("")},
    {label:state && `Status: ${state.replaceAll("_", " ")}`, clear:()=>setState("")},
    {label:stage && codeStages.find(([key])=>key===stage)?.[1], clear:()=>setStage("")},
    {label:contextOnly && "Needs context", clear:()=>setContextOnly(false)},
    {label:githubOnly && "GitHub findings", clear:()=>setGithubOnly(false)},
    {label:since && "Last 30 days", clear:()=>setSince("")},
  ].filter(filter=>filter.label);
  const priorityRank: Record<string,number> = {high:0, medium:1, low:2};
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const availablePolicies = [...new Set(rows.flatMap(row => row.policies ?? []))].sort();
  const filtered = rows.filter(row => {
    const payload = row.payload;
    const local = payload.source_type === "local_review";
    const text = [payload.title, payload.evidence?.path, local ? "" : `PR #${row.pr} ${row.pr}`,
      payload.release_tag, payload.branch, row.name, findingSource(row), ...(row.policies ?? []).map(policyLabel)].join(" ").toLowerCase();
    return terms.every(term=>text.includes(term))
      && (!legalReview || Boolean(row.legal_request))
      && (!falsePositives || showAll || Boolean(row.fp_mark))
      && (!sourceVersion || findingSource(row) === sourceVersion)
      && (!policy || row.policies?.includes(policy))
      && (!stage || (!local && codeStage(row)[0] === stage))
      && (!githubOnly || !local)
      && (!repo || row.name === repo)
      && (!priority || row.priority === priority)
      && (!state || row.state === state)
      && (!contextOnly || (row.state === "open" && Boolean(payload.context_question)))
      && (!since || row.updated_at >= since);
  }).sort((a,b) => {
    const age = a.created_at.localeCompare(b.created_at);
    if (order === "newest") return -age;
    if (order === "oldest") return age;
    return (priorityRank[a.priority] ?? 3) - (priorityRank[b.priority] ?? 3) || age;
  });
  return <section className="panel list-panel findings-panel"><div className="findings-toolbar"><h2>Results <span className="findings-count" aria-live="polite">{filtered.length}</span></h2><button className="findings-button" onClick={async()=>{try{await request("/api/demo/seed",{method:"POST"});await load()}catch(e){setError((e as Error).message)}}}>Load demo examples</button></div>
    {falsePositives && <div className="finding-quick-filters">
      <button type="button" aria-pressed={!showAll} onClick={()=>{clearFilters();setShowAll(false);}}>Marked findings</button>
      <button type="button" aria-pressed={showAll} onClick={()=>{clearFilters();setShowAll(true);}}>All findings</button>
    </div>}
    <div className="finding-search-tools">
      <label>Search findings <input type="search" placeholder="Title, file, PR or release" value={query} onChange={e=>setQuery(e.target.value)}/></label>
      <label>Sort by <select value={order} onChange={e=>setOrder(e.target.value)}>
        <option value="priority">Priority, then oldest</option><option value="oldest">Oldest first</option><option value="newest">Newest first</option>
      </select></label>
    </div>
    <div className="finding-quick-filters" aria-label="Quick filters">
      <button type="button" aria-pressed={contextOnly} onClick={()=>{
        if (!contextOnly) {setState("open");setSince("");}
        setContextOnly(!contextOnly);
      }}>Needs context</button>
      <button type="button" aria-pressed={releasedHigh} onClick={toggleReleasedHigh}>Open High in releases</button>
    </div>
    <div className="findings-filters"><label>Repository <select value={repo} onChange={e=>setRepo(e.target.value)}><option value="">All</option>{[...new Set(rows.map(r=>r.name))].map(n=><option key={n}>{n}</option>)}</select></label>
    <label>Priority <select value={priority} onChange={e=>setPriority(e.target.value)}><option value="">All</option>{["high","medium","low"].map(n=><option key={n}>{n}</option>)}</select></label>
    <label>Status <select value={state} onChange={e=>setState(e.target.value)}><option value="">All</option>{[["open","Open"],["acknowledged","Acknowledged"],["false_positive","False positive"],["resolved","Resolved"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    <label>Code stage <select value={stage} onChange={e=>setStage(e.target.value)}>
      <option value="">All</option>
      {codeStages.map(([key,label])=><option value={key} key={key}>{label}</option>)}
    </select></label>
    <label>Policy <select value={policy} onChange={e=>setPolicy(e.target.value)}>
      <option value="">All</option>
      {policy && !availablePolicies.includes(policy) && <option value={policy}>{policyLabel(policy)}</option>}
      {availablePolicies.map(id=><option key={id} value={id}>{policyLabel(id)}</option>)}
    </select></label>
    </div>
    <details className="finding-extra-filters">
      <summary>More filters</summary>
      <div className="finding-search-tools">
        <SourceVersionFilter value={sourceVersion} versions={rows.map(findingSource)} onChange={setSourceVersion}/>
      </div>
    </details>
    {filters.length > 0 && <div className="finding-active-filters" aria-label="Active filters">
      {filters.map((filter,index)=><button type="button" key={index} onClick={filter.clear}
        aria-label={`Remove filter ${filter.label}`}>{filter.label} <span aria-hidden="true">×</span></button>)}
      <button type="button" className="clear-finding-filters" onClick={clearFilters}>Clear all</button>
    </div>}
    {error&&<p className="findings-error" role="alert">{error}</p>}{saved&&<p className="findings-success" role="status">{saved} {savedFinding&&<button className="findings-text-button" onClick={()=>open(rows.find(row=>row.id === savedFinding.id) || savedFinding)}>View decision history</button>} <button className="findings-text-button" onClick={clearFilters}>View all findings</button></p>}
    {loading && <p>Loading findings…</p>}
    {!loading && filtered.length > 0 && <div className="finding-list">
      <div className="finding-grid finding-list-header" aria-hidden="true">
        <span>Priority</span><span>Finding</span><span>Code stage</span><span>Status</span><span/>
      </div>
      {filtered.map(row => {
        const local = row.payload.source_type === "local_review";
        const released = codeStage(row)[0] === "released";
        const critical = row.priority === "high" && row.state === "open";
        const location = local ? "Code review" : [`PR #${row.pr}`, row.payload.branch].filter(Boolean).join(" · ");
        const age = Math.max(0,Math.floor((Date.now()-new Date(row.created_at).getTime())/86400000));
        return <button type="button" className={`findings-row finding-grid${critical ? " finding-row-critical" : ""}`}
          key={row.id} aria-expanded={selected?.id === row.id} onClick={()=>open(row)}>
          <span className={`findings-badge priority-${row.priority}`}>{row.priority}</span>
          <span className="findings-row-copy">
            <b>{row.payload.title || "Review finding"}</b>
            <small>{row.name} · {location}{row.payload.evidence?.path && ` · ${row.payload.evidence.path}`}</small>
            <small className="finding-policy-labels">
              {row.policies?.map(policyLabel).join(" · ")}
              {row.source_version && <> <span className="finding-source-meta">· AI Act {row.source_version}</span></>}
            </small>
          </span>
          <span className="finding-row-stage">
            <span className={`findings-badge${released && critical ? " priority-high" : ""}`}>{local ? "Local review" : codeStage(row)[1]}</span>
            {row.payload.release_tag && <small>{row.payload.release_tag}</small>}
          </span>
          <span className="finding-row-stage">
            <span className="findings-badge">{row.fp_mark?.pending ? "Awaiting approval" : row.legal_request ? "Legal review" : row.state.replaceAll("_"," ")}</span>
            <small>{age === 0 ? "Today" : `${age}d ago`}</small>
          </span>
          <span className="finding-row-arrow" aria-hidden="true">›</span>
        </button>;
      })}
    </div>}
    {!loading&&!filtered.length&&<div className="empty-state"><p>No matching findings.</p><button className="findings-button" onClick={clearFilters}>Reset filters</button></div>}
    {selected && <section className="findings-detail" id="finding-detail" tabIndex={-1}><div className="findings-detail-heading"><h3>{selected.payload.title}</h3><button className="findings-button" onClick={()=>setSelected(null)}>Close</button></div><p>{selected.payload.explanation}</p><small className="finding-source-meta">AI Act source · {sourceVersionLabel(findingSource(selected))}</small>{selected.payload.source_type === "local_review" ? <><p>From a {selected.payload.review_status || "saved"} code review.</p><a href={`/app/reviews/${encodeURIComponent(selected.payload.source_review_id || "")}`}>Open code review</a></> : selected.id.startsWith("demo-") ? <p>Simulated pull request #{selected.pr} · {selected.payload.branch || "Demo branch"} · {selected.head === "synthetic-head" ? "Sample commit" : selected.head.slice(0, 7)}</p> : <a href={`https://github.com/${selected.name}/pull/${selected.pr}`} target="_blank" rel="noreferrer">Open pull request</a>}{selected.payload.source_type !== "local_review" && <div className="finding-lifecycle">
        <b>Code lifecycle</b>
        <p>Flagged in PR #{selected.pr}
          {["merged", "released"].includes(codeStage(selected)[0]) && " → Merged"}
          {codeStage(selected)[0] === "released" && ` → Released · ${selected.payload.release_tag || "Version unavailable"}`}
        </p>
        <small>{codeStage(selected)[1]} · Finding {selected.state.replaceAll("_", " ")}</small>
      </div>}
      {selected.legal_request && <div className="finding-lifecycle">
        <b>Awaiting legal review</b>
        <p>{selected.legal_request.reason || "The reviewer asked Legal to assess this finding."}</p>
      </div>}
      {githubCodeUrl(selected)
        ? <a className="overview-link" href={githubCodeUrl(selected) || "#"} target="_blank" rel="noreferrer">Open code at reviewed commit</a>
        : <a className="overview-link" href="#finding-code-evidence">Jump to code evidence</a>}
      {selected.payload.code_sample ? <pre id="finding-code-evidence">{selected.payload.code_sample}</pre> : <pre id="finding-code-evidence">{selected.payload.evidence?.path}{selected.payload.evidence?.start_line ? `:${selected.payload.evidence.start_line}` : ""}{selected.payload.evidence?.quote ? `\n${selected.payload.evidence.quote}` : ""}</pre>}
      {selected.payload.citations?.map((c,i)=><p key={i}>{c.section_id&&<b>{c.section_id}: </b>}{c.quote} <a href={c.url} target="_blank" rel="noreferrer">Official source</a></p>)}
      {selected.payload.context_question&&<div className="findings-question"><b>Question to check</b><p>{selected.payload.context_question}</p></div>}<label className="findings-explanation">Explanation<textarea rows={4} placeholder="Optional for false positives" value={reason} onChange={e=>setReason(e.target.value)} maxLength={2000}/></label>
      {selected.fp_mark && <div className="finding-lifecycle">
        <b>{selected.fp_mark.pending ? "Awaiting approval" : "False positive"}</b>
        <p>{selected.fp_mark.actor}{selected.fp_mark.reason && ` · ${selected.fp_mark.reason}`}</p>
      </div>}
      <div className="finding-search-tools"><label>False-positive reason (optional)
        <select value={category} onChange={e=>setCategory(e.target.value)}>
          <option value="">No category</option>
          {Object.entries(fpCategories).filter(([key])=>key !== "unspecified").map(([key,label])=><option key={key} value={key}>{label}</option>)}
        </select>
      </label></div>
      {selected.fp_mark?.pending && <button className="findings-button" disabled={busy} onClick={()=>decide("fp_approve")}>Approve false positive</button>}
      <div className="findings-decisions">{actions.map(action=><button className={action.value==="resolved" ? "findings-button primary" : "findings-button"} key={action.value} title={action.help} disabled={busy||(["resolved","context"].includes(action.value)&&!reason.trim()) || (action.value === "false_positive" && Boolean(selected.fp_mark)) || (action.value === "unsure" && (selected.state !== "open" || Boolean(selected.legal_request)))} onClick={()=>decide(action.value)}>{action.label}</button>)}</div>
      {selected.id.startsWith("demo-") && <section className="findings-simulation"><button className="findings-button" disabled={busy||!reason.trim()} onClick={()=>decide("resolved",true)}>Simulate PR resolve reply</button>{" "}
        <button className="findings-button" disabled={busy || Boolean(selected.fp_mark)} onClick={()=>decide("false_positive",true)}>Simulate PR false-positive mark</button>{" "}
        <button className="findings-button" disabled={busy || selected.state !== "open" || Boolean(selected.legal_request)}
          onClick={()=>decide("unsure",true)}>Simulate PR unsure reply</button></section>}<h3>Decision history</h3>{history.map(d=><p className="findings-history" key={d.id}>{d.actor} · {new Date(d.created_at).toLocaleString()} · {d.action.replaceAll("_"," ")} · {d.reason || "No reason added"} · {d.sync_status === "synced" ? (selected.id.startsWith("demo-") ? "Simulated sync" : "Synced") : d.sync_status === "not_required" ? "Local decision, no GitHub sync needed" : "Waiting for GitHub sync"}</p>)}
    </section>}
  </section>;
}
