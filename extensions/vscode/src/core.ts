import {createHash} from 'node:crypto';
import * as path from 'node:path';
import {ScanResult} from './contracts';

const sectionPages: Record<string, string> = {
  'annex-iii-4-a': 'annex-3', 'annex-iii-1-a': 'annex-3', 'article-6-2': 'article-6',
  'article-6-3': 'article-6', 'article-50-1': 'article-50', 'article-50-2': 'article-50',
};
export const fingerprint = (text: string): string => createHash('sha256').update(text).digest('hex');
export const isFresh = (version: number, hash: string, currentVersion: number, text: string): boolean => version === currentVersion && hash === fingerprint(text);
export const escapeText = (text: string): string => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/[\\`*_{}\[\]()#!|~]/g, '\\$&');
const object = (value: unknown): value is Record<string, any> => value !== null && typeof value === 'object' && !Array.isArray(value);
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(x => typeof x === 'string');
const code = (text: string): string => text.split('\n').map(line => `    ${line}`).join('\n');

export function parseResult(text: string, root: string, target: string, sourceText: string): ScanResult {
  const value: unknown = JSON.parse(text);
  if (!object(value) || value.schema_version !== '1.0' || !['complete', 'partial', 'failed'].includes(value.status) ||
      !Array.isArray(value.findings) || value.findings.length > 3 || !Array.isArray(value.errors) ||
      !object(value.coverage) || !object(value.metadata) || !strings(value.coverage.scanned_files) ||
      !Array.isArray(value.coverage.skipped_files) || typeof value.coverage.truncated !== 'boolean' ||
      !strings(value.coverage.limitations) || !strings(value.coverage.corpus_scope) || !strings(value.coverage.supported_languages)) {
    throw new Error('Engine returned an unsupported or malformed result contract.');
  }
  for (const item of value.errors) {
    if (!object(item) || typeof item.code !== 'string' || typeof item.message !== 'string') { throw new Error('Malformed operational error.'); }
  }
  for (const item of value.coverage.skipped_files) {
    if (!object(item) || typeof item.path !== 'string' || typeof item.reason !== 'string') { throw new Error('Malformed skipped coverage.'); }
  }
  for (const key of ['model_id', 'corpus_version', 'corpus_checksum', 'input_fingerprint']) {
    if (value.metadata[key] !== null && typeof value.metadata[key] !== 'string') { throw new Error('Malformed provenance.'); }
  }
  if (typeof value.metadata.prompt_version !== 'string' || !Number.isInteger(value.metadata.elapsed_ms) || value.metadata.elapsed_ms < 0) { throw new Error('Malformed provenance.'); }
  if (value.status === 'complete' && (value.errors.length || value.coverage.truncated || value.coverage.skipped_files.length)) { throw new Error('Inconsistent complete result.'); }
  if (value.status === 'failed' && !value.errors.length) { throw new Error('Failed result omitted its operational error.'); }
  const lines = sourceText.split(/\r?\n/);
  for (const f of value.findings) {
    if (!object(f) || !['potential_issue', 'context_question'].includes(f.kind) || !['high', 'medium', 'low'].includes(f.priority) ||
        !['id', 'title', 'explanation', 'suggested_next_action'].every(key => typeof f[key] === 'string' && f[key].length) ||
        !(f.context_question === null || typeof f.context_question === 'string') || !object(f.evidence) || !Array.isArray(f.citations) || !f.citations.length) {
      throw new Error('Malformed finding.');
    }
    const ev = f.evidence;
    if (typeof ev.path !== 'string' || path.isAbsolute(ev.path) || ev.path.split(/[\\/]/).includes('..') || ev.path.includes('\\') ||
        path.resolve(root, ev.path) !== path.resolve(target) || !Number.isInteger(ev.start_line) || !Number.isInteger(ev.end_line) ||
        ev.start_line < 1 || ev.end_line < ev.start_line || ev.end_line > lines.length ||
        ev.quote !== lines.slice(ev.start_line - 1, ev.end_line).join('\n')) {
      throw new Error('Engine evidence does not match the current file.');
    }
    for (const c of f.citations) {
      if (!object(c) || typeof c.quote !== 'string' || !c.quote || typeof c.section_id !== 'string' ||
          !sectionPages[c.section_id] || c.url !== `https://ai-act-service-desk.ec.europa.eu/en/ai-act/${sectionPages[c.section_id]}`) {
        throw new Error('Engine returned an unrecognized official-source link.');
      }
    }
  }
  return value as unknown as ScanResult;
}

export function report(result: ScanResult, sourceLink: (line: number) => string): string {
  const sections = ['# AI Act Copilot', `**Review ${result.status}** · ${result.findings.length} finding(s) · ${result.coverage.scanned_files.length} Python file(s)`,
    'Engineering review only. Zero findings does not certify compliance.', '## Coverage',
    `Scanned: ${result.coverage.scanned_files.map(escapeText).join(', ') || 'none'}`,
    ...result.coverage.skipped_files.map(s => `- Skipped ${escapeText(s.path)}: ${escapeText(s.reason)}`),
    ...result.errors.map(e => `- **${escapeText(e.code)}:** ${escapeText(e.message)}`)];
  if (result.coverage.truncated) { sections.push('**Input was truncated by the scan budgets.**'); }
  for (const f of result.findings) {
    sections.push(`## ${f.kind === 'context_question' ? 'Needs context' : 'Potential concern'}: ${escapeText(f.title)}`,
      `Review priority: **${f.priority}**`, escapeText(f.explanation), '### Code evidence',
      `[${escapeText(f.evidence.path)}:${f.evidence.start_line}–${f.evidence.end_line}](${sourceLink(f.evidence.start_line)})`, code(f.evidence.quote), '### Official evidence');
    for (const c of f.citations) { sections.push(`[${escapeText(c.section_id)}](${c.url})`, `> ${escapeText(c.quote)}`); }
    sections.push('### Next action', escapeText(f.suggested_next_action));
    if (f.context_question) { sections.push('### One context question', escapeText(f.context_question)); }
  }
  if (!result.findings.length && result.status === 'complete') { sections.push('No supported concern identified in this reviewed scope.'); }
  sections.push('## Scope limits', ...result.coverage.limitations.map(limit => `- ${escapeText(limit)}`),
    '## Provenance', `Model: ${escapeText(result.metadata.model_id || 'unavailable')}`,
    `Corpus: ${escapeText(result.metadata.corpus_version || 'unavailable')}`,
    `Corpus SHA-256: ${escapeText(result.metadata.corpus_checksum || 'unavailable')}`,
    `Prompt: ${escapeText(result.metadata.prompt_version)} · elapsed ${result.metadata.elapsed_ms} ms`,
    `Input fingerprint: ${escapeText(result.metadata.input_fingerprint || 'unavailable')}`,
    'Use **AI Act Copilot: Review current Python file** to rerun. Use **Answer context question and review** to add explicit facts for this session.');
  return sections.join('\n\n') + '\n';
}
