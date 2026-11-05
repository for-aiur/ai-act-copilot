import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Box, Download, FileCheck2, GitCommitHorizontal, Network, Plus } from "lucide-react";
import { request } from "./api";

type Project = {id: string; name: string};
type Repository = {id: string; name: string};
const roles = {unknown:"Undetermined", provider:"System provider", deployer:"Deployer", model_provider:"Model provider"};
const risks = {unassessed:"Unassessed", needs_review:"Needs review", potential_high:"Potential high risk",
  potential_prohibited:"Potentially prohibited", no_high_signal:"No high-risk signal"};
const relations = {supplies_output:"Supplies output to", calls:"Calls", monitors:"Monitors"};
const itemTitles = {model_card:"Model card", validation:"Performance & bias tests", oversight:"Human oversight",
  event_log:"Production event log", technical_docs:"Technical documentation"};

type SystemInput = {
  name: string; purpose: string; owner: string; role: keyof typeof roles; risk: keyof typeof risks;
  rationale: string; repository_id: string | null;
};
type System = SystemInput & {id: string};
type Relationship = {id: string; source: string; target: string; kind: keyof typeof relations};
type Inventory = {systems: System[]; links: Relationship[]; repositories: Repository[]};
type Items = Record<keyof typeof itemTitles, string>;
type EvidenceInput = {release: string; commit: string; model_version: string; items: Items};
type Evidence = EvidenceInput & {
  id: string; created_at: string; project: string; system: System; repository: string | null; demo: boolean;
  source: {version: string; url: string | null; snapshot_id: string} | null;
};
const itemKeys = Object.keys(itemTitles) as (keyof Items)[];
const blankSystem: SystemInput = {name:"", purpose:"", owner:"", role:"unknown", risk:"unassessed", rationale:"", repository_id:null};
const blankEvidence: EvidenceInput = {release:"", commit:"", model_version:"",
  items:{model_card:"", validation:"", oversight:"", event_log:"", technical_docs:""}};

function send<T>(url: string, method: string, body: unknown) {
  return request<T>(url, {method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
}

export function AiSystems() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState("");
  const [demo, setDemo] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [seeding, setSeeding] = useState(false);
  useEffect(() => {
    Promise.all([request<Project[]>("/api/customer/projects"), request<{enabled:boolean}>("/api/demo/status")])
      .then(([items, status]) => {
        const requested = new URLSearchParams(location.search).get("project");
        setProjects(items); setDemo(status.enabled); setReady(true);
        setProject(items.find(item => item.id === requested)?.id ?? items[0]?.id ?? "");
      }).catch(e => setError(e.message));
  }, []);
  async function loadDemo() {
    setSeeding(true); setError("");
    try {
      const seed = await request<{project_id:string; system_id:string}>("/api/demo/ai-systems", {method:"POST"});
      location.assign(`/app/ai-systems?project=${encodeURIComponent(seed.project_id)}&system=${encodeURIComponent(seed.system_id)}`);
    } catch (e) { setError((e as Error).message); }
    finally { setSeeding(false); }
  }
  return <div className="systems-page">
    <div className="systems-toolbar">
      {projects.length > 0 && <label>Project <select value={project} onChange={e => {
        setProject(e.target.value);
        const params = new URLSearchParams({project:e.target.value});
        history.replaceState(null, "", `/app/ai-systems?${params}`);
      }}>
        {projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>}
      {demo && <button className="findings-button" onClick={loadDemo} disabled={seeding}>
        {seeding ? "Loading example…" : "Open nutrition & insurance example"}
      </button>}
    </div>
    {error && <p role="alert">{error}</p>}
    {!ready && !error && <p role="status">Loading projects…</p>}
    {ready && !project && <section className="panel list-panel"><h2>Create a project first</h2>
      <a href="/app/projects" className="overview-link">Open Projects <ArrowRight size={14}/></a>
    </section>}
    {project && <InventoryView key={project} project={project}/>}
  </div>;
}

function InventoryView({project}: {project:string}) {
  const endpoint = `/api/customer/projects/${encodeURIComponent(project)}/ai-systems`;
  const [data, setData] = useState<Inventory>();
  const [selected, setSelected] = useState(() => new URLSearchParams(location.search).get("system") || "");
  const [tab, setTab] = useState<"map" | "evidence">(() =>
    new URLSearchParams(location.search).get("tab") === "evidence" ? "evidence" : "map");
  const [form, setForm] = useState<SystemInput>();
  const [editing, setEditing] = useState("");
  const [addingLink, setAddingLink] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { request<Inventory>(endpoint).then(setData).catch(e => setError(e.message)); }, [endpoint]);
  const system = data?.systems.find(item => item.id === selected) ?? data?.systems[0];
  function select(next: string, nextTab: typeof tab = tab) {
    setSelected(next); setTab(nextTab); setForm(undefined); setAddingLink(false);
    const params = new URLSearchParams({project, system:next});
    if (nextTab === "evidence") params.set("tab", nextTab);
    history.replaceState(null, "", `/app/ai-systems?${params}`);
  }
  async function saveSystem(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setBusy(true); setError("");
    try {
      const saved = await send<System>(editing ? `${endpoint}/${encodeURIComponent(editing)}` : endpoint,
        editing ? "PUT" : "POST", form);
      setData(await request<Inventory>(endpoint));
      select(saved.id, "map");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function changeLink(method: "POST" | "DELETE", value: FormData | string) {
    setBusy(true); setError("");
    try {
      if (typeof value === "string") {
        await request(`${endpoint}/relationships/${encodeURIComponent(value)}`, {method});
      } else {
        await send(`${endpoint}/relationships`, method, Object.fromEntries(value));
      }
      setData(await request<Inventory>(endpoint));
      setAddingLink(false);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  if (!data) return error ? <p role="alert">{error}</p> : <p role="status">Loading AI systems…</p>;
  return <>
    {error && <p className="findings-error" role="alert">{error}</p>}
    <div className="systems-layout">
      <aside className="panel list-panel systems-list">
        <header><h2>Systems <small>{data.systems.length}</small></h2>
          <button className="findings-button" disabled={busy} onClick={() => {
            setTab("map"); setEditing(""); setForm(blankSystem); setAddingLink(false);
          }}><Plus size={15}/> Add system</button>
        </header>
        {data.systems.length === 0 && <p>No AI systems in this project.</p>}
        {data.systems.map(item => <button key={item.id} className="systems-list-item" disabled={busy}
          aria-pressed={system?.id === item.id} onClick={() => select(item.id)}>
          <Box size={16}/><span><b>{item.name}</b><small>{roles[item.role]}</small></span>
        </button>)}
      </aside>
      <div className="systems-main">
        {system && <div className="systems-tabs" role="group" aria-label="AI system views">
          <button aria-pressed={tab === "map"} onClick={() => select(system.id, "map")}><Network size={16}/> System map</button>
          <button aria-pressed={tab === "evidence"} onClick={() => select(system.id, "evidence")}><FileCheck2 size={16}/> Release evidence</button>
        </div>}
        {form ? <section className="panel list-panel"><h2>{editing ? "Edit AI system" : "Add AI system"}</h2>
          <form className="systems-form" onSubmit={saveSystem}>
            <label>System name<input required maxLength={100} value={form.name} onChange={e => setForm({...form,name:e.target.value})}/></label>
            <label>Intended use<textarea required rows={3} maxLength={1000} value={form.purpose} onChange={e => setForm({...form,purpose:e.target.value})}/></label>
            <div className="systems-field-grid">
              <label>Owner<input maxLength={100} value={form.owner} onChange={e => setForm({...form,owner:e.target.value})}/></label>
              <label>Repository<select value={form.repository_id ?? ""} onChange={e => setForm({...form,repository_id:e.target.value || null})}>
                <option value="">No repository linked</option>
                {data.repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
              </select></label>
              <label>Organisation role<select value={form.role} onChange={e => setForm({...form,role:e.target.value as SystemInput["role"]})}>
                {Object.entries(roles).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select></label>
              <label>Risk assessment<select value={form.risk} onChange={e => setForm({...form,risk:e.target.value as SystemInput["risk"]})}>
                {Object.entries(risks).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select></label>
            </div>
            <label>Assessment rationale<textarea rows={2} maxLength={1000} value={form.rationale} onChange={e => setForm({...form,rationale:e.target.value})}/></label>
            <div className="systems-actions"><button className="button-dark" disabled={busy}>Save system</button>
              <button type="button" className="findings-button" disabled={busy} onClick={() => setForm(undefined)}>Cancel</button></div>
          </form>
        </section> : system && (tab === "evidence"
          ? <EvidencePanel key={system.id} endpoint={`${endpoint}/${encodeURIComponent(system.id)}/evidence`} system={system}/>
          : <>
            <section className="panel list-panel systems-map">
              <header><h2>System relationships</h2>{data.systems.length > 1 && <button className="findings-button"
                disabled={busy} onClick={() => setAddingLink(!addingLink)}><Plus size={15}/> Add relationship</button>}</header>
              {addingLink && <form className="systems-form systems-link-form" onSubmit={e => {
                e.preventDefault(); void changeLink("POST", new FormData(e.currentTarget));
              }}>
                <label>From system<select name="source" defaultValue={system.id}>
                  {data.systems.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select></label>
                <label>Relationship<select name="kind">
                  {Object.entries(relations).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                </select></label>
                <label>To system<select name="target" defaultValue={data.systems.find(item => item.id !== system.id)?.id}>
                  {data.systems.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select></label>
                <button className="button-dark" disabled={busy}>Save relationship</button>
              </form>}
              <RelationshipMap data={data} selected={system.id} onSelect={select}
                onRemove={id => changeLink("DELETE", id)} busy={busy}/>
            </section>
            <section className="panel list-panel systems-detail">
              <header><div><span className="systems-kicker">Selected system</span><h2>{system.name}</h2></div>
                <button className="findings-button" disabled={busy} onClick={() => {
                  const {id, ...fields} = system; setEditing(id); setForm(fields);
                }}>Edit system</button></header>
              <p>{system.purpose}</p>
              <dl className="systems-facts">
                <div><dt>Organisation role</dt><dd>{roles[system.role]}</dd></div>
                <div><dt>Owner</dt><dd>{system.owner || "Unassigned"}</dd></div>
                <div><dt>Repository</dt><dd>{data.repositories.find(repo => repo.id === system.repository_id)?.name ?? "Not linked"}</dd></div>
              </dl>
              <div className="systems-assessment"><RiskBadge system={system}/>{system.rationale && <p>{system.rationale}</p>}</div>
              <button className="systems-text-button" onClick={() => select(system.id, "evidence")}>
                Open release evidence <ArrowRight size={15}/>
              </button>
            </section>
          </>)}
      </div>
    </div>
  </>;
}

function RiskBadge({system}: {system:System}) {
  return <span className="systems-risk" data-risk={system.risk}>{risks[system.risk]}</span>;
}

function RelationshipMap({data, selected, onSelect, onRemove, busy}: {
  data:Inventory; selected:string; onSelect:(id:string)=>void; onRemove:(id:string)=>void; busy:boolean;
}) {
  const sources = data.systems.filter(item => data.links.some(edge => edge.source === item.id));
  if (sources.length === 0) return <p className="systems-empty">No relationships yet.</p>;
  const node = (item: System) => <button className="systems-node" aria-pressed={selected === item.id}
    onClick={() => onSelect(item.id)} disabled={busy}>
    <b><Box size={15}/>{item.name}</b><RiskBadge system={item}/>
  </button>;
  return <div className="systems-graph">
    {sources.map(source => <div className="systems-graph-group" key={source.id}>
      {node(source)}
      <div className="systems-graph-targets">
        {data.links.filter(edge => edge.source === source.id).map(edge => {
          const target = data.systems.find(item => item.id === edge.target);
          return target && <div className="systems-edge" key={edge.id}>
            <div className="systems-edge-line"><span>{relations[edge.kind]}</span><ArrowRight size={17} aria-hidden="true"/></div>
            {node(target)}
            <button className="systems-remove" type="button" disabled={busy} title="Remove relationship"
              aria-label={`Remove relationship from ${source.name} to ${target.name}`}
              onClick={() => onRemove(edge.id)}>×</button>
          </div>;
        })}
      </div>
    </div>)}
  </div>;
}

function downloadEvidence(pack: Evidence) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(pack, null, 2) + "\n"], {type:"application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = `release-evidence-${pack.release.replace(/[^a-z0-9._-]/gi, "-")}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function EvidencePanel({endpoint, system}: {endpoint:string; system:System}) {
  const [packages, setPackages] = useState<Evidence[]>();
  const [selected, setSelected] = useState("");
  const [form, setForm] = useState<EvidenceInput>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { request<Evidence[]>(endpoint).then(setPackages).catch(e => setError(e.message)); }, [endpoint]);
  const pack = packages?.find(item => item.id === selected) ?? packages?.[0];
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setBusy(true); setError("");
    try {
      const result = await send<Evidence>(endpoint, "POST", form);
      setPackages(items => [result, ...(items ?? [])]);
      setSelected(result.id); setForm(undefined);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const attached = pack ? itemKeys.filter(key => pack.items[key]).length : 0;
  return <section className="panel list-panel systems-evidence">
    <header><div><span className="systems-kicker">{system.name}</span><h2>Release evidence</h2></div>
      {!form && <button className="findings-button" onClick={() => setForm(blankEvidence)}><Plus size={15}/> New package</button>}
    </header>
    {error && <p role="alert">{error}</p>}
    {form ? <form className="systems-form" onSubmit={save}>
      <div className="systems-field-grid">
        <label>Release<input required maxLength={100} placeholder="v2.1.0" value={form.release} onChange={e=>setForm({...form,release:e.target.value})}/></label>
        <label>Commit<input required pattern="[0-9a-fA-F]{7,64}" placeholder="Git commit SHA" value={form.commit} onChange={e=>setForm({...form,commit:e.target.value})}/></label>
        <label>Model version<input maxLength={100} value={form.model_version} onChange={e=>setForm({...form,model_version:e.target.value})}/></label>
      </div>
      <p>Add evidence references or a short note. Leave gaps blank.</p>
      {itemKeys.map(key => <label key={key}>{itemTitles[key]}<textarea rows={2} maxLength={2000} value={form.items[key]}
        onChange={e=>setForm({...form,items:{...form.items,[key]:e.target.value}})}/></label>)}
      <div className="systems-actions"><button className="button-dark" disabled={busy}>Save package</button>
        <button type="button" className="findings-button" disabled={busy} onClick={()=>setForm(undefined)}>Cancel</button></div>
    </form> : pack ? <>
      <div className="systems-release">
        <div><GitCommitHorizontal size={21}/><div><b>{pack.release}</b><code title={pack.commit}>{pack.commit.slice(0,12)}</code></div></div>
        {pack.demo && <span className="systems-risk">Demo package</span>}
        <button className="findings-button" onClick={() => downloadEvidence(pack)}><Download size={15}/> Export JSON</button>
      </div>
      {packages && packages.length > 1 && <label className="systems-package-picker">Saved packages
        <select value={pack.id} onChange={e=>setSelected(e.target.value)}>
          {packages.map(item => <option key={item.id} value={item.id}>{item.release} · {new Date(item.created_at).toLocaleString()}</option>)}
        </select>
      </label>}
      <dl className="systems-facts">
        <div><dt>Repository</dt><dd>{pack.repository || "Not linked"}</dd></div>
        <div><dt>Model version</dt><dd>{pack.model_version || "Unspecified"}</dd></div>
        <div><dt>AI Act source</dt><dd>{pack.source?.url ? <a href={pack.source.url} target="_blank" rel="noreferrer">{pack.source.version}</a> : pack.source?.version || "Unspecified"}</dd></div>
        <div><dt>Evidence references</dt><dd>{attached} / {itemKeys.length} recorded</dd></div>
      </dl>
      <div className="systems-evidence-items">{itemKeys.map(key => <article key={key}>
        <div><h3>{itemTitles[key]}</h3><span className="systems-risk" data-risk={pack.items[key] ? "recorded" : "potential_high"}>
          {pack.items[key] ? "Recorded" : "Missing"}
        </span></div>
        {pack.items[key] && <p>{pack.items[key]}</p>}
      </article>)}</div>
    </> : <p className="systems-empty">{packages ? "No release evidence yet." : "Loading release evidence…"}</p>}
  </section>;
}
