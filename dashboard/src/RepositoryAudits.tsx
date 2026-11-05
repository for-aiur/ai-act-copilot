import { useEffect, useState } from "react";
import { Download, GitBranch, ScanSearch } from "lucide-react";

const snapshots = [
  { ref: "main", commit: "d27d831", total: 120, skipped: 12 },
  { ref: "v1.8.0", commit: "a14c92e", total: 96, skipped: 8 },
];
const findings = [
  { at: 24, priority: "High", title: "Check who can override the candidate ranking",
    path: "src/ranking.py:42", source: "Article 14 · Human oversight",
    detail: "The model score changes candidate order. Confirm who can review and override it." },
  { at: 56, priority: "Medium", title: "Verify retention for bias audit records",
    path: "src/bias_audit.py:18", source: "Article 4a · Bias detection and correction",
    detail: "The function returns sensitive audit records. Confirm when those records are deleted." },
  { at: 84, priority: "Low", title: "Locate the audit log for ranking runs",
    path: "src/runner.py:71", source: "Article 12 · Record-keeping",
    detail: "The entry point starts a ranking run. Check where the run is recorded." },
];

function downloadReport(snapshot: typeof snapshots[number], sourceVersion: string) {
  const lines = [
    "Repository scan report", "Synthetic demo", "", "Repository: example/recruitment",
    `Ref: ${snapshot.ref}   Commit: ${snapshot.commit}`,
    `AI Act source: ${sourceVersion}`,
    `Processed: ${snapshot.total}   Reviewed: ${snapshot.total - snapshot.skipped}   Skipped: ${snapshot.skipped}`,
    `Coverage: ${Math.round((snapshot.total - snapshot.skipped) / snapshot.total * 100)}%`,
    "", "3 findings: 1 high, 1 medium, 1 low", "",
    ...findings.flatMap(finding => [
      `${finding.priority}: ${finding.title}`,
      `${finding.path} | ${finding.source.replace(" · ", " / ")}`,
      finding.detail, "",
    ]),
  ];
  const commands = lines.map((line, index) => {
    const escaped = line.replace(/[\\()]/g, "\\$&");
    return `/F1 ${index === 0 ? 22 : 11} Tf 1 0 0 1 48 ${740 - index * 23} Tm (${escaped}) Tj`;
  }).join("\n");
  const stream = `BT\n${commands}\nET\n`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}endstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = objects.map((object, index) => {
    const offset = pdf.length;
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
    return offset;
  });
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  const url = URL.createObjectURL(new Blob([pdf], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `repository-scan-${snapshot.commit}.pdf`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function RepositoryAudits() {
  const params = new URLSearchParams(location.search);
  const [snapshotIndex, setSnapshotIndex] = useState(() => params.get("ref") === "v1.8.0" ? 1 : 0);
  const sourceVersion = params.get("source") === "demo-updated" ? "Simulated update" : "Synthetic baseline";
  const [processed, setProcessed] = useState<number | null>(null);
  const snapshot = snapshots[snapshotIndex];
  const running = processed !== null && processed < snapshot.total;
  const complete = processed === snapshot.total;
  const visible = findings.filter(finding => processed !== null && finding.at <= processed);
  const reviewed = snapshot.total - snapshot.skipped;
  const coverage = Math.round(reviewed / snapshot.total * 100);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      setProcessed(value => Math.min(snapshot.total, (value ?? 0) + 4));
    }, 240);
    return () => window.clearInterval(timer);
  }, [running, snapshot.total]);

  return <div className="audit-layout">
    <section className="audit-control">
      <div className="audit-scope"><ScanSearch size={24}/><div><h2>example/recruitment</h2><span>Demo scan</span></div></div>
      <label><GitBranch size={16}/> Branch or release
        <select value={snapshotIndex} disabled={running} onChange={event => {
          setSnapshotIndex(Number(event.target.value));
          setProcessed(null);
        }}>
          {snapshots.map((entry, index) => <option key={entry.ref} value={index}>{entry.ref}</option>)}
        </select>
      </label>
      <span className="audit-commit">Commit <code>{snapshot.commit}</code></span>
      <button className="button-dark" disabled={running} onClick={() => setProcessed(0)}>
        {running ? "Scanning…" : complete ? "Run again" : "Start scan"}
      </button>
    </section>
    {processed === null && <section className="panel list-panel audit-empty">
      <h2>Repository scan</h2><p>{snapshot.total} files in this snapshot.</p>
    </section>}
    {processed !== null && <section className="panel list-panel audit-result">
      <div className="audit-heading">
        <div><h2>{complete ? "Scan report" : "Scan in progress"}</h2>
          <p>{snapshot.ref} · {snapshot.commit} · AI Act source: {sourceVersion}</p></div>
        {complete && <button className="button-dark" onClick={() => downloadReport(snapshot, sourceVersion)}><Download size={16}/> Download PDF</button>}
      </div>
      <div className="audit-progress">
        <label htmlFor="audit-progress">{processed} / {snapshot.total} files processed</label>
        <b>{Math.floor(processed / snapshot.total * 100)}%</b>
        <progress id="audit-progress" value={processed} max={snapshot.total}/>
      </div>
      {complete && <div className="audit-metrics">
        <div><b>{coverage}%</b><span>Scan coverage</span></div>
        <div><b>{reviewed}</b><span>Files reviewed</span></div>
        <div><b>{snapshot.skipped}</b><span>Files skipped</span></div>
        <div><b>0</b><span>File errors</span></div>
      </div>}
      <h3>Findings <span aria-live="polite">{visible.length}</span></h3>
      {visible.length === 0 && <p>Waiting for findings…</p>}
      {visible.map(finding => <article className="audit-finding" key={finding.path}>
        <div><h4>{finding.title}</h4><span className={`findings-badge priority-${finding.priority.toLowerCase()}`}>{finding.priority}</span></div>
        <p>{finding.detail}</p><small><code>{finding.path}</code> · {finding.source}</small>
      </article>)}
    </section>}
  </div>;
}
