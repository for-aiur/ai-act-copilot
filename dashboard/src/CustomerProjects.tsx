import { useEffect, useState, type FormEvent } from "react";
import { request } from "./api";

type Project = {id: string; name: string; repository_ids: string[]};
type Repository = {id: string; name: string};
const projectsEndpoint = "/api/customer/projects";

export function scopedPath(path: string) {
  const project = new URLSearchParams(location.search).get("project");
  if (!project) return path;
  const url = new URL(path, location.origin);
  url.searchParams.set("project", project);
  return url.pathname + url.search;
}

export function ProjectScope() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");
  const project = new URLSearchParams(location.search).get("project") || "";
  useEffect(() => {
    request<Project[]>(projectsEndpoint).then(setProjects).catch(e=>setError(e.message));
  }, []);
  function changeScope(id: string) {
    const url = new URL(location.href);
    url.searchParams.delete("finding");
    url.searchParams.delete("repo");
    if (id) url.searchParams.set("project", id);
    else url.searchParams.delete("project");
    location.assign(url);
  }
  return <div className="project-scope">
    <label>Project <select value={project} onChange={e=>changeScope(e.target.value)}>
      <option value="">All projects</option>
      {project && !projects.some(item=>item.id === project) && <option value={project}>Selected project</option>}
      {projects.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}
    </select></label>
    <a href={scopedPath("/app/projects")}>Manage projects</a>
    {error && <span role="alert">{error}</span>}
  </div>;
}

export function CustomerProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [ready, setReady] = useState(false);
  const [demo, setDemo] = useState(false);
  const [name, setName] = useState("");
  const [editing, setEditing] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    Promise.all([
      request<Project[]>(projectsEndpoint),
      request<Repository[]>("/api/repositories"),
      request<{enabled:boolean}>("/api/demo/status"),
    ])
      .then(([items, repos, status])=>{
        setProjects(items); setRepositories(repos); setDemo(status.enabled); setReady(true);
      })
      .catch(e=>setError(e.message));
  }, []);
  function loadForm(project?: Project) {
    setEditing(project?.id || "");
    setName(project?.name || "");
    setSelected(project?.repository_ids || []);
    setError("");
    setNotice("");
  }
  async function loadDemoRepositories() {
    setBusy(true); setError("");
    try {
      await request("/api/demo/seed", {method:"POST"});
      setRepositories(await request<Repository[]>("/api/repositories"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const firstProject = ready && projects.length === 0;
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const endpoint = editing ? `${projectsEndpoint}/${encodeURIComponent(editing)}` : projectsEndpoint;
      const saved = await request<Project>(endpoint, {
        method: editing ? "PUT" : "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({name: name.trim(), repository_ids: selected}),
      });
      if (firstProject) {
        location.replace(`/app?project=${encodeURIComponent(saved.id)}`);
        return;
      }
      setProjects(current=>[...current.filter(item=>item.id !== saved.id), saved]
        .sort((a,b)=>a.name.localeCompare(b.name)));
      loadForm(saved);
      setNotice("Project saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return <div className={firstProject ? "project-layout project-first" : "project-layout"}>
    {!firstProject && <section className="panel list-panel">
      <h2>Workspace projects</h2>
      {!ready && !error && <p>Loading projects…</p>}
      {projects.map(item=><div className="project-list-row" key={item.id}>
        <a href={`/app?project=${encodeURIComponent(item.id)}`}><b>{item.name}</b><small>{item.repository_ids.length} repositories</small></a>
        <div className="project-list-actions">
          <a href={`/app/ai-systems?project=${encodeURIComponent(item.id)}`}>AI systems</a>
          <button className="findings-button" disabled={busy} onClick={()=>loadForm(item)}>Edit</button>
        </div>
      </div>)}
    </section>}
    <section className="panel list-panel">
      <h2>{firstProject ? "Create your first project" : editing ? "Edit project" : "New project"}</h2>
      {firstProject && <p>Group repositories to see their findings and metrics together.</p>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <form className="project-form" onSubmit={save}>
        <label>Project name<input value={name} required maxLength={100} onChange={e=>setName(e.target.value)}/></label>
        <fieldset disabled={busy || !ready}>
          <legend>Repositories</legend>
          {ready && repositories.length === 0 && <p>No repositories in this workspace yet. You can add them to the project later.</p>}
          {ready && demo && repositories.length === 0 && <div>
            <button type="button" className="findings-button" onClick={loadDemoRepositories}>Load demo repositories</button>
          </div>}
          {repositories.map(repo=><label key={repo.id}>
            <input type="checkbox" checked={selected.includes(repo.id)} onChange={e=>{
              const checked = e.target.checked;
              setSelected(items=>checked ? [...items, repo.id] : items.filter(id=>id !== repo.id));
            }}/>{repo.name}
          </label>)}
        </fieldset>
        <div>
          <button className="button-dark" disabled={!ready || busy || !name.trim()}>{busy ? "Please wait…" : firstProject ? "Create project" : "Save project"}</button>
          {editing && <button className="findings-button" type="button" disabled={busy} onClick={()=>loadForm()}>New project</button>}
        </div>
      </form>
    </section>
  </div>;
}
