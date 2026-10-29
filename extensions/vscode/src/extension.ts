import * as vscode from 'vscode';
import {execFile, ChildProcess} from 'node:child_process';
import {ScanResult} from './contracts';
import {escapeText, fingerprint, isFresh, parseResult, report} from './core';
import {HealthPanel} from './health';

export function activate(context: vscode.ExtensionContext): void {
  const health = new HealthPanel(context);
  const diagnostics = vscode.languages.createDiagnosticCollection('ai-act-copilot');
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 50);
  status.command = 'aiact.showHealth';
  const changes = new vscode.EventEmitter<vscode.Uri>();
  const reportUri = vscode.Uri.parse('aiact-report:/AI%20Act%20Review.md');
  let reportText = '# AI Act Copilot\n\nRun **AI Act Copilot: Review current Python file** to begin.\n';
  let last: {result: ScanResult; document: vscode.TextDocument; root: string} | undefined;
  let lastSource: vscode.Uri | undefined;
  let active: ChildProcess | undefined;
  let activeUri: string | undefined;
  let queued: vscode.TextDocument | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;
  const explicitContext = new Map<string, string>();

  function state(label: string, icon = 'shield'): void {
    status.text = `$(${icon}) AI Act: ${label}`;
    status.tooltip = 'Local engineering review, not certification. Click to open local health and review actions.';
    status.show();
  }
  function updateReport(text: string): void { reportText = text; changes.fire(reportUri); }
  async function showReport(): Promise<void> {
    await vscode.workspace.openTextDocument(reportUri);
    await vscode.commands.executeCommand('markdown.showPreviewToSide', reportUri);
  }
  function invalidate(document: vscode.TextDocument): void {
    diagnostics.delete(document.uri);
    if (last?.document.uri.toString() === document.uri.toString()) {
      last = undefined;
      updateReport('# AI Act Copilot\n\n**Source changed.** Rerun the review to inspect findings for the current content.\n');
      state('Needs review', 'edit');
    }
  }
  async function review(document: vscode.TextDocument, automatic = false): Promise<void> {
    if (!vscode.workspace.isTrusted) { state('Unavailable', 'lock'); if (!automatic) { vscode.window.showWarningMessage('Trust this workspace before running the local review executable.'); } return; }
    if (document.languageId !== 'python' || document.uri.scheme !== 'file') { if (!automatic) { vscode.window.showInformationMessage('Open a saved Python file to review.'); } return; }
    if (document.isDirty) { if (!automatic) { vscode.window.showInformationMessage('Save the Python file before reviewing it.'); } return; }
    if (active) { if (automatic) { queued = document; } else { vscode.window.showInformationMessage('A local review is already running.'); } return; }
    const folder = vscode.workspace.getWorkspaceFolder(document.uri);
    if (!folder) { vscode.window.showInformationMessage('Open the project folder in VS Code before reviewing.'); return; }
    if (!await health.ensureReady(document.uri, automatic)) {
      state('Unavailable', 'warning');
      updateReport('# AI Act Copilot\n\n**Local setup unavailable.** Open the AI Act Copilot sidebar or run **AI Act Copilot: Show local health** to check and start the local service.\n');
      return;
    }
    // Another request or an edit can arrive while the health check is pending.
    if (active) { if (automatic) { queued = document; } return; }
    if (document.isClosed || document.isDirty) { state('Needs review', 'edit'); return; }
    const config = vscode.workspace.getConfiguration('aiact', document.uri);
    const executable = config.get<string>('executable', 'aiact').replace('${workspaceFolder}', folder.uri.fsPath);
    const args = ['scan', document.uri.fsPath, '--json', '--model', config.get<string>('model', 'qwen2.5:3b'),
      '--endpoint', config.get<string>('endpoint', 'http://127.0.0.1:11434')];
    const corpus = config.get<string>('corpusPath', '');
    if (corpus) { args.push('--corpus', corpus.replace('${workspaceFolder}', folder.uri.fsPath)); }
    const facts = explicitContext.get(document.uri.toString());
    if (facts) { args.push('--context', facts); }
    const version = document.version;
    const source = document.getText();
    const hash = fingerprint(source);
    lastSource = document.uri;
    diagnostics.delete(document.uri);
    last = undefined;
    activeUri = document.uri.toString();
    state('Reviewing locally…', 'sync~spin');
    updateReport('# AI Act Copilot\n\n**Reviewing locally…** Two bounded model passes; source stays on this device.\n');
    await vscode.window.withProgress({location: vscode.ProgressLocation.Notification, title: 'AI Act Copilot: reviewing locally', cancellable: true}, async (_progress, token) => {
      await new Promise<void>(resolve => {
        let cancelled = false;
        const cancellation = token.onCancellationRequested(() => { cancelled = true; active?.kill(); });
        active = execFile(executable, args, {cwd: folder.uri.fsPath, timeout: 130_000, maxBuffer: 2_000_000, shell: false, windowsHide: true}, (error, stdout) => {
          cancellation.dispose();
          active = undefined;
          activeUri = undefined;
          try {
            if (disposed) { return; }
            if (cancelled) { state('Unavailable', 'circle-slash'); updateReport('# AI Act Copilot\n\n**Review cancelled.** Rerun when ready.\n'); return; }
            if (document.isClosed || !isFresh(version, hash, document.version, document.getText())) {
              diagnostics.delete(document.uri); state('Needs review', 'edit');
              updateReport('# AI Act Copilot\n\n**Source changed during review.** Stale results were discarded. Rerun for current content.\n'); return;
            }
            if (!stdout.trim()) { throw new Error(error ? 'Engine unavailable. Check the aiact.executable setting and run aiact doctor in the terminal.' : 'Engine returned no result.'); }
            const result = parseResult(stdout, folder.uri.fsPath, document.uri.fsPath, source);
            last = {result, document, root: folder.uri.fsPath};
            const items = result.findings.map(f => {
              const range = new vscode.Range(f.evidence.start_line - 1, 0, f.evidence.end_line - 1, document.lineAt(f.evidence.end_line - 1).text.length);
              const item = new vscode.Diagnostic(range, `${f.kind === 'context_question' ? 'Needs context' : 'Potential concern'}: ${f.title}\n${f.explanation}`, f.kind === 'context_question' ? vscode.DiagnosticSeverity.Information : vscode.DiagnosticSeverity.Warning);
              item.source = 'AI Act Copilot';
              item.code = {value: f.citations[0].section_id, target: vscode.Uri.parse(f.citations[0].url)};
              return item;
            });
            diagnostics.set(document.uri, items);
            const unavailable = result.errors.some(e => ['model_unavailable', 'corpus_unavailable'].includes(e.code));
            if (unavailable) { void health.refresh(document.uri); }
            state(unavailable ? 'Unavailable' : `${result.status[0].toUpperCase()}${result.status.slice(1)} · ${items.length}`, result.status === 'complete' ? 'shield' : 'warning');
            updateReport(report(result, line => document.uri.with({fragment: `L${line}`}).toString()));
            if (!automatic) { void showReport(); }
          } catch (failure) {
            state('Failed', 'error');
            const message = failure instanceof Error ? failure.message : 'Review failed.';
            updateReport(`# AI Act Copilot\n\n**Review failed:** ${escapeText(message)}\n`);
            if (!automatic) { vscode.window.showErrorMessage(message); }
          } finally { resolve(); }
        });
      });
    });
    if (queued && !disposed) { const next = queued; queued = undefined; void review(next, true); }
  }

  async function currentDocument(): Promise<vscode.TextDocument | undefined> {
    const current = vscode.window.activeTextEditor?.document;
    if (current?.languageId === 'python') { return current; }
    return lastSource ? vscode.workspace.openTextDocument(lastSource) : undefined;
  }
  context.subscriptions.push(diagnostics, status, changes,
    vscode.workspace.registerTextDocumentContentProvider('aiact-report', {onDidChange: changes.event, provideTextDocumentContent: () => reportText}),
    vscode.commands.registerCommand('aiact.review', async () => { const doc = await currentDocument(); if (doc) { await review(doc); } else { vscode.window.showInformationMessage('Open a saved Python file to review.'); } }),
    vscode.commands.registerCommand('aiact.showReport', showReport),
    vscode.commands.registerCommand('aiact.answerContext', async () => {
      const doc = await currentDocument();
      if (!doc || !vscode.workspace.isTrusted) { return; }
      const answer = await vscode.window.showInputBox({title: 'AI Act Copilot: explicit context for this file', prompt: last?.result.findings.find(f => f.context_question)?.context_question || 'What decisions does this AI influence, where is it deployed, and what is your actor role?', value: explicitContext.get(doc.uri.toString()), validateInput: value => Buffer.byteLength(value) > 4000 ? 'Keep explicit context under 4 KB.' : undefined});
      if (answer !== undefined) { explicitContext.set(doc.uri.toString(), answer); invalidate(doc); await review(doc); }
    }),
    vscode.commands.registerCommand('aiact.revealFinding', async () => {
      if (!last?.result.findings.length) { return; }
      const selected = await vscode.window.showQuickPick(last.result.findings.map(f => ({label: f.title, description: `Line ${f.evidence.start_line}`, finding: f})), {title: 'Reveal code evidence'});
      if (selected && last) { const editor = await vscode.window.showTextDocument(last.document); const range = new vscode.Range(selected.finding.evidence.start_line - 1, 0, selected.finding.evidence.end_line - 1, 0); editor.selection = new vscode.Selection(range.start, range.end); editor.revealRange(range, vscode.TextEditorRevealType.InCenter); }
    }),
    vscode.commands.registerCommand('aiact.openOfficialSource', async () => {
      if (!last) { return; }
      const citations = last.result.findings.flatMap(f => f.citations);
      const selected = await vscode.window.showQuickPick(citations.map(c => ({label: c.section_id, description: c.url, url: c.url})), {title: 'Open official legal source'});
      if (selected) { await vscode.env.openExternal(vscode.Uri.parse(selected.url)); }
    }),
    vscode.languages.registerHoverProvider('python', {provideHover(document, position) {
      if (!last || last.document.uri.toString() !== document.uri.toString()) { return; }
      const finding = last.result.findings.find(f => position.line + 1 >= f.evidence.start_line && position.line + 1 <= f.evidence.end_line);
      if (!finding) { return; }
      const markdown = new vscode.MarkdownString();
      markdown.isTrusted = false;
      markdown.supportHtml = false;
      markdown.appendText(`${finding.kind === 'context_question' ? 'Needs context' : 'Potential concern'}: ${finding.title}\n\n${finding.explanation}\n\nNext: ${finding.suggested_next_action}`);
      for (const citation of finding.citations) { markdown.appendMarkdown(`\n\n[${escapeText(citation.section_id)}](${citation.url})`); markdown.appendText(`\n${citation.quote}`); }
      if (finding.context_question) { markdown.appendText(`\n\nQuestion: ${finding.context_question}`); }
      return new vscode.Hover(markdown);
    }}),
    vscode.workspace.onDidChangeTextDocument(event => { if (event.contentChanges.length) { invalidate(event.document); if (activeUri === event.document.uri.toString()) { state('Reviewing changed source…', 'sync~spin'); } } }),
    vscode.workspace.onDidSaveTextDocument(document => {
      if (!vscode.workspace.getConfiguration('aiact', document.uri).get<boolean>('reviewOnSave', false)) { return; }
      if (timer) { clearTimeout(timer); }
      timer = setTimeout(() => { void review(document, true); }, 800);
    }),
    {dispose: () => { disposed = true; if (timer) { clearTimeout(timer); } active?.kill(); }});
  state(vscode.workspace.isTrusted ? 'Check setup' : 'Unavailable', vscode.workspace.isTrusted ? 'shield' : 'lock');
}
