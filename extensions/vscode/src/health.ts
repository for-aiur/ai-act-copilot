import * as vscode from 'vscode';
import {execFile, ChildProcess} from 'node:child_process';
import {existsSync} from 'node:fs';
import * as path from 'node:path';
import {HealthResult, localHost, parseHealth} from './health-core';

export class HealthPanel implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly changes = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changes.event;
  private readonly view: vscode.TreeView<vscode.TreeItem>;
  private health?: HealthResult;
  private resource?: vscode.Uri;
  private message = 'Open a trusted project folder to check local setup.';
  private pending?: {key: string; promise: Promise<HealthResult | undefined>};
  private currentKey = '';
  private starting?: Promise<boolean>;
  private terminal?: vscode.Terminal;
  private disposed = false;
  private processes = new Set<ChildProcess>();

  constructor(context: vscode.ExtensionContext) {
    this.view = vscode.window.createTreeView('aiact.health', {treeDataProvider: this});
    const introduction = (fragment = '') => {
      // VSIX packaging normalizes README.md to readme.md on case-sensitive hosts.
      const filename = existsSync(path.join(context.extensionUri.fsPath, 'README.md')) ? 'README.md' : 'readme.md';
      return vscode.commands.executeCommand('markdown.showPreviewToSide', vscode.Uri.joinPath(context.extensionUri, filename).with({fragment}));
    };
    context.subscriptions.push(this.changes, this.view,
      vscode.commands.registerCommand('aiact.showIntroduction', () => introduction()),
      vscode.commands.registerCommand('aiact.showRoadmap', () => introduction('planned-next-steps')),
      vscode.commands.registerCommand('aiact.showHealth', () => this.show()),
      vscode.commands.registerCommand('aiact.refreshHealth', () => this.refresh()),
      vscode.commands.registerCommand('aiact.startLocalService', () => this.start()),
      this.view.onDidChangeVisibility(event => { if (event.visible) { void this.refresh(); } }),
      vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration('aiact')) { this.health = undefined; void this.refresh(); } }),
      vscode.window.onDidCloseTerminal(terminal => { if (terminal === this.terminal) { this.terminal = undefined; void this.refresh(); } }),
      {dispose: () => { this.disposed = true; for (const process of this.processes) { process.kill(); } }});
    if (vscode.workspace.isTrusted && vscode.workspace.workspaceFolders?.length) { void this.refresh(); }
  }

  getTreeItem(item: vscode.TreeItem): vscode.TreeItem { return item; }
  getChildren(): vscode.TreeItem[] {
    const items: vscode.TreeItem[] = [];
    const introduction = new vscode.TreeItem('Start here: what is this tool?');
    introduction.iconPath = new vscode.ThemeIcon('book');
    introduction.command = {command: 'aiact.showIntroduction', title: 'What is AI Act Copilot?'};
    items.push(introduction);
    for (const check of this.health?.checks || []) {
      const item = new vscode.TreeItem(({engine: 'CLI', ollama: 'Ollama', model: 'Model', corpus: 'Legal corpus'})[check.id]);
      item.description = `${check.status === 'ready' ? 'Available' : check.status === 'unknown' ? 'Not checked' : 'Unavailable'} · ${check.detail}`;
      item.tooltip = check.detail;
      item.iconPath = new vscode.ThemeIcon(check.status === 'ready' ? 'pass' : check.status === 'unknown' ? 'question' : 'warning');
      items.push(item);
    }
    const action = (label: string, command: string, icon: string) => {
      const item = new vscode.TreeItem(label); item.iconPath = new vscode.ThemeIcon(icon);
      item.command = {command, title: label}; return item;
    };
    items.push(action(this.starting ? 'Starting local service…' : 'Start local service', 'aiact.startLocalService', 'play'));
    items.push(action('Refresh health', 'aiact.refreshHealth', 'refresh'));
    items.push(action('Review current Python file', 'aiact.review', 'search'));
    items.push(action('Show last review report', 'aiact.showReport', 'preview'));
    items.push(action('Future plans', 'aiact.showRoadmap', 'telescope'));
    this.view.message = 'Evros Labs · Understand where AI in your Python code needs a closer look. Open the introduction for an example and first steps.\n\n' + (this.starting ? 'Starting local Ollama in the VS Code terminal…' : this.message);
    return items;
  }
  async show(): Promise<void> {
    await vscode.commands.executeCommand('workbench.view.extension.aiact');
    await this.refresh();
  }
  private options(resource?: vscode.Uri) {
    const selected = resource || this.resource || vscode.window.activeTextEditor?.document.uri;
    const folder = (selected && vscode.workspace.getWorkspaceFolder(selected)) || vscode.workspace.workspaceFolders?.[0];
    if (!folder) { throw new Error('Open a project folder first.'); }
    const config = vscode.workspace.getConfiguration('aiact', selected || folder.uri);
    const resolve = (value: string) => value.replace('${workspaceFolder}', folder.uri.fsPath);
    const model = config.get<string>('model', 'qwen2.5:3b');
    const endpoint = config.get<string>('endpoint', 'http://127.0.0.1:11434');
    const args = ['doctor', '--json', '--model', model, '--endpoint', endpoint];
    const corpus = config.get<string>('corpusPath', '');
    if (corpus) { args.push('--corpus', resolve(corpus)); }
    return {folder, executable: resolve(config.get<string>('executable', 'aiact')), args, endpoint, config, resolve};
  }
  async refresh(resource?: vscode.Uri): Promise<HealthResult | undefined> {
    if (resource) { this.resource = resource; }
    if (!vscode.workspace.isTrusted || this.disposed) {
      this.health = undefined; this.message = 'Trust the workspace to check or start local tools.'; this.changes.fire(); return;
    }
    let options: ReturnType<HealthPanel['options']>;
    try { options = this.options(resource); }
    catch (error) { this.message = (error as Error).message; this.changes.fire(); return; }
    const key = JSON.stringify([options.folder.uri.fsPath, options.executable, options.args]);
    this.currentKey = key;
    if (this.pending?.key === key) { return this.pending.promise; }
    this.message = 'Checking CLI, local Ollama, model and corpus…'; this.changes.fire();
    const promise = new Promise<HealthResult | undefined>(resolve => {
      const child = execFile(options.executable, options.args, {cwd: options.folder.uri.fsPath, shell: false, timeout: 12_000, maxBuffer: 256_000, windowsHide: true}, (_error, stdout) => {
        this.processes.delete(child);
        if (this.disposed || key !== this.currentKey) { resolve(undefined); return; }
        try {
          if (!stdout.trim()) { throw new Error('CLI unavailable. Check aiact.executable and the engine installation.'); }
          this.health = parseHealth(stdout);
          this.message = `${this.health.status === 'ready' ? 'Ready to review' : 'Local setup needs attention'} · Checked ${new Date().toLocaleTimeString()}`;
          this.view.description = options.folder.name;
          resolve(this.health);
        } catch (error) {
          this.health = undefined; this.message = (error as Error).message; resolve(undefined);
        } finally { this.changes.fire(); }
      });
      this.processes.add(child);
    });
    this.pending = {key, promise};
    try { return await promise; }
    catch {
      if (key === this.currentKey && !this.disposed) {
        this.health = undefined;
        this.message = 'Could not launch the CLI health check. Check aiact.executable and its configuration.';
        this.changes.fire();
      }
      return undefined;
    }
    finally { if (this.pending?.promise === promise) { this.pending = undefined; } }
  }

  async ensureReady(resource: vscode.Uri, automatic: boolean): Promise<boolean> {
    const health = await this.refresh(resource);
    if (health?.status === 'ready') { return true; }
    if (automatic) { return false; }
    const stopped = health?.checks.find(c => c.id === 'ollama')?.status === 'unavailable' && !!health.endpoint;
    const choice = await vscode.window.showWarningMessage('Local setup is unavailable. Check CLI, Ollama, model and corpus in AI Act Copilot.', ...(stopped ? ['Start local service', 'Open health'] : ['Open health']));
    if (choice === 'Start local service') { return this.start(resource); }
    if (choice === 'Open health') { await this.show(); }
    return false;
  }
  async start(resource?: vscode.Uri): Promise<boolean> {
    if (this.starting) { return this.starting; }
    this.starting = this.startService(resource);
    this.changes.fire();
    try { return await this.starting; }
    catch (error) { this.message = (error as Error).message; vscode.window.showErrorMessage(this.message); return false; }
    finally { this.starting = undefined; this.changes.fire(); }
  }
  private async startService(resource?: vscode.Uri): Promise<boolean> {
    if (!vscode.workspace.isTrusted || this.disposed) { throw new Error('Trust the workspace before starting a local tool.'); }
    const options = this.options(resource);
    const host = localHost(options.endpoint);
    const before = await this.refresh(resource);
    if (!before) { throw new Error('Fix the CLI configuration before starting Ollama.'); }
    if (!before.endpoint) { throw new Error('Fix the local endpoint or model configuration before starting Ollama.'); }
    if (before.checks.find(c => c.id === 'ollama')?.status === 'ready') {
      this.message = before.status === 'ready' ? 'Local service is already running.' : 'Ollama is running; resolve the model or corpus check.';
      return before.status === 'ready';
    }
    const helper = path.join(options.folder.uri.fsPath, 'scripts', 'start-local-model.sh');
    const bundled = path.join(options.folder.uri.fsPath, '.tools', 'ollama', process.platform === 'win32' ? 'ollama.exe' : 'ollama');
    const configured = options.resolve(options.config.get<string>('ollamaExecutable', 'ollama'));
    const executable = configured === 'ollama' && existsSync(bundled) ? bundled : configured;
    const useHelper = process.platform !== 'win32' && existsSync(helper);
    const terminalName = `AI Act Copilot · Ollama (${host})`;
    this.terminal = vscode.window.terminals.find(t => t.name === terminalName && t.exitStatus === undefined);
    if (!this.terminal) {
      this.terminal = vscode.window.createTerminal({name: terminalName, cwd: options.folder.uri.fsPath,
        shellPath: useHelper ? '/bin/sh' : executable, shellArgs: useHelper ? [helper, executable] : ['serve'],
        env: {OLLAMA_HOST: host, OLLAMA_NO_CLOUD: '1', OLLAMA_DEBUG_LOG_REQUESTS: 'false', OLLAMA_MAX_LOADED_MODELS: '1'}});
    }
    const terminal = this.terminal;
    terminal.show(true);
    const deadline = Date.now() + 30_000;
    while (!this.disposed && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      if (terminal.exitStatus !== undefined || this.terminal !== terminal) { this.message = 'Local service stopped. Inspect its VS Code terminal output.'; return false; }
      const health = await this.refresh(resource);
      if (health?.checks.find(c => c.id === 'ollama')?.status === 'ready') { return health.status === 'ready'; }
    }
    this.message = 'Service is not ready yet. Inspect the Ollama terminal, then refresh health.';
    return false;
  }
}
