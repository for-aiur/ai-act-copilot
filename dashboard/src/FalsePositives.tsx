import { useEffect, useState } from "react";
import { request } from "./api";
import { scopedPath } from "./CustomerProjects";
import { FindingsPanel, policyLabel } from "./FindingsPanel";

import { fpCategories } from "./fpCategories";

type Metrics = {
  findings: number; marked: number; pending: number; submissions: number;
  breakdowns: Record<string,Record<string,number>>;
};
type Policy = {mode: "immediate" | "approval"; approver: string | null};

function Bars({title, values, format = (key: string) => key}: {
  title:string; values:Record<string,number>; format?:(key:string)=>string;
}) {
  const entries = Object.entries(values).sort((a,b)=>b[1]-a[1] || a[0].localeCompare(b[0])).slice(0,8);
  const max = Math.max(1, ...entries.map(([,count])=>count));
  return <section className="panel list-panel fp-chart">
    <h3>{title}</h3>
    {entries.length === 0 && <p>No marks yet.</p>}
    {entries.map(([label,count])=><div className="fp-bar" key={label}>
      <span>{format(label)}</span><span className="policy-track"><i style={{width:`${count/max*100}%`}}/></span><b>{count}</b>
    </div>)}
  </section>;
}

export function FalsePositiveMetrics({internal = false, revision = 0}: {internal?:boolean; revision?:number}) {
  const [data, setData] = useState<Metrics>();
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    request<Metrics>(scopedPath(`/api/customer/false-positive-metrics${internal ? "?history=true" : ""}`))
      .then(value=>{if (live) {setData(value);setError("");}})
      .catch(e=>{if (live) setError(e.message);});
    return ()=>{live = false;};
  }, [internal, revision]);
  if (error) return <p role="alert">{internal ? "Sign in to the workspace to view feedback metrics." : error}</p>;
  if (!data) return <p role="status">Loading feedback metrics…</p>;
  const approved = data.marked - data.pending;
  const ring = data.marked ? approved/data.marked*100 : 0;
  const days = Object.entries(data.breakdowns.day).sort(([a],[b])=>a.localeCompare(b)).slice(-14);
  const maximum = Math.max(1,...days.map(([,count])=>count));
  return <div className="fp-metrics">
    <section className="panel list-panel fp-summary">
      <h2>{internal ? "Customer false-positive signals" : "False-positive activity"}</h2>
      <div className="fp-summary-body">
        <div className="priority-ring" aria-hidden="true" style={{background:
          data.marked ? `conic-gradient(#397968 0 ${ring}%, #b18335 ${ring}% 100%)` : "#dae6de"}}><b>{data.marked}</b></div>
        <dl><div><dt>Marked findings</dt><dd>{data.marked} / {data.findings}</dd></div>
          <div><dt>Excluded from review metrics</dt><dd>{approved}</dd></div>
          <div><dt>Awaiting approval</dt><dd>{data.pending}</dd></div>
          {internal && <div><dt>Mark submissions</dt><dd>{data.submissions}</dd></div>}</dl>
      </div>
    </section>
    <section className="panel list-panel fp-chart">
      <h3>Marks by day</h3>
      {days.length === 0 ? <p>No marks yet.</p> : <div className="fp-histogram">
        {days.map(([day,count])=><div key={day}><b>{count}</b>
          <span style={{height:`${count/maximum*58}px`}} aria-hidden="true"/><small>{day.slice(5)}</small></div>)}
      </div>}
    </section>
    <Bars title="Reason category" values={data.breakdowns.category} format={key=>fpCategories[key as keyof typeof fpCategories] || key}/>
    <Bars title="Repository" values={data.breakdowns.repository}/>
    <Bars title="Priority" values={data.breakdowns.priority}/>
    <Bars title="Policy" values={data.breakdowns.policy} format={policyLabel}/>
    {internal && <>
      <Bars title="Model" values={data.breakdowns.model}/>
      <Bars title="RAG release" values={data.breakdowns.rag_release} format={key=>key === "Unknown" ? key : key.slice(0,12)}/>
    </>}
  </div>;
}

export function FalsePositives() {
  const [policy, setPolicy] = useState<Policy>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const endpoint = "/api/customer/false-positive-policy";
  useEffect(() => {request<Policy>(endpoint).then(setPolicy).catch(e=>setError(e.message));}, []);
  async function update(mode: Policy["mode"]) {
    setBusy(true); setError("");
    try {
      setPolicy(await request<Policy>(endpoint,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode})}));
    } catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  return <div className="customer-overview">
    <section className="panel list-panel fp-settings">
      <label>Workspace decision policy <select disabled={!policy || busy} value={policy?.mode || "immediate"}
        onChange={e=>update(e.target.value === "approval" ? "approval" : "immediate")}>
        <option value="immediate">Apply the first mark</option>
        <option value="approval">Require a separate approval</option>
      </select></label>
      {policy?.mode === "approval" && <p>Approver: {policy.approver}. A different actor must submit the mark.</p>}
      {error && <p role="alert">{error}</p>}
    </section>
    <FalsePositiveMetrics revision={revision}/>
    <FindingsPanel falsePositives onDecision={()=>setRevision(n=>n+1)}/>
  </div>;
}
