import { scopedPath } from "./CustomerProjects";
import { useEffect, useState } from "react";
import { request } from "./api";

export type LegalSource = {
  version: string;
  snapshot_id: string;
  url: string | null;
  retrieved_at: string | null;
  consolidated_date: string | null;
  publication_date: string | null;
};

export function sourceVersionLabel(version: string) {
  if (version === "unknown") return "Source unknown";
  return version;
}

export function SourceVersionFilter({value, versions, onChange}: {
  value: string; versions: string[]; onChange: (version:string) => void;
}) {
  const options = [...new Set([...versions, value].filter(Boolean))].sort();
  return <label>AI Act source <select value={value} onChange={event=>onChange(event.target.value)}>
    <option value="">All versions</option>
    {options.map(version=><option key={version} value={version}>{sourceVersionLabel(version)}</option>)}
  </select></label>;
}

type Change = {id: string; title: string; change: string};
type Impact = {id: string; repository: string; title: string; review_id: string | null; provisions: string[]};
type Updates = {
  active: LegalSource | null;
  comparisons: {previous: LegalSource; changes: Change[]; affected: Impact[]; candidates: string[]}[];
  demo_finding: {id: string; repository: string; title: string} | null;
};

export function LegalSourceLine({source}: {source: LegalSource}) {
  return <div className="legal-source-line">
    <b>EU AI Act</b> {source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.version}</a> : source.version}
    {source.consolidated_date && <span>Consolidated {source.consolidated_date}</span>}
    {source.publication_date && <span>Published {source.publication_date}</span>}
    <span>{source.retrieved_at ? `Retrieved ${source.retrieved_at}` : "Retrieval date unavailable"}</span>
  </div>;
}

export function LegalSourceUpdates() {
  const [data, setData] = useState<Updates>();
  const [error, setError] = useState("");
  useEffect(() => {
    request<Updates>(scopedPath("/api/customer/source-updates")).then(setData).catch(e=>setError(e.message));
  }, []);
  if (!data && !error) return null;
  return <section className="panel list-panel source-updates">
    <h2>AI Act source & review updates</h2>
    {error && <p role="alert">{error}</p>}
    {data?.active ? <LegalSourceLine source={data.active}/> : data && <p>No active source.</p>}
    {data?.comparisons.map(({previous,changes,affected,candidates}) => <details key={previous.snapshot_id}>
      <summary>{previous.version} · {changes.length} changed provisions · {affected.length} affected findings</summary>
      {affected.map(item=><div className="source-impact-row" key={item.id}>
        <a href={scopedPath(`/app/findings?finding=${encodeURIComponent(item.id)}`)}>{item.title}</a>
        <span>{item.repository} · {item.provisions.join(", ")}</span>
        {item.review_id && <a href={`/app/reviews/${encodeURIComponent(item.review_id)}`}>Open review to rescan</a>}
      </div>)}
      {candidates.length > 0 && <p>Rescan candidates from the older source: {candidates.join(", ")}.</p>}
    </details>)}
    {data?.comparisons.length === 0 && <p>No source changes matched against pinned findings.</p>}
    {data?.demo_finding && <details>
      <summary>Simulated update · 1 affected finding</summary>
      <div className="source-impact-row">
        <a href={scopedPath(`/app/findings?finding=${encodeURIComponent(data.demo_finding.id)}`)}>{data.demo_finding.title}</a>
        <span>{data.demo_finding.repository} · PR #14 · v1.8.0 · Article 14</span>
        <a href="/app/audits?ref=v1.8.0&source=demo-updated">Open simulated rescan</a>
      </div>
    </details>}
  </section>;
}

type Comparison = {active: LegalSource; previous: LegalSource[]; changes: Change[]};

export function SourceComparison() {
  const [previous, setPrevious] = useState("");
  const [data, setData] = useState<Comparison>();
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    const query = previous ? `?previous=${encodeURIComponent(previous)}` : "";
    request<Comparison>(`/api/rag/source-changes${query}`)
      .then(result=>{ if (live) { setData(result); setError(""); } })
      .catch(e=>{ if (live) setError(e.message); });
    return ()=>{ live = false; };
  }, [previous]);
  if (!data && !error) return null;
  return <section className="panel list-panel source-updates">
    <h2>AI Act source comparison</h2>
    {error && <p role="alert">{error}</p>}
    {data && <>
      <LegalSourceLine source={data.active}/>
      <label>Compare with <select value={previous} onChange={event=>{setPrevious(event.target.value);setData(undefined);}}>
        <option value="">Choose a previous snapshot</option>
        {data.previous.map(item=><option value={item.snapshot_id} key={item.snapshot_id}>
          {item.version} · {item.snapshot_id.slice(0, 8)}
        </option>)}
      </select></label>
      {data.previous.length === 0 && <p>No previous AI Act snapshot is available for comparison.</p>}
      {previous && <ul>{data.changes.map(change=><li key={change.id}>{change.title} · {change.change}</li>)}</ul>}
      {previous && !data.changes.length && <p>No provision changes.</p>}
    </>}
  </section>;
}
