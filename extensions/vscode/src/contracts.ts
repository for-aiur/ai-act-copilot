export interface Evidence { path: string; start_line: number; end_line: number; quote: string }
export interface Citation { section_id: string; quote: string; url: string }
export interface Finding {
  id: string; title: string; explanation: string;
  kind: 'potential_issue' | 'context_question'; priority: 'high' | 'medium' | 'low';
  evidence: Evidence; citations: Citation[]; suggested_next_action: string; context_question: string | null;
}
export interface ScanResult {
  schema_version: '1.0'; status: 'complete' | 'partial' | 'failed'; findings: Finding[];
  errors: {code: string; message: string; path: string | null}[];
  coverage: {scanned_files: string[]; skipped_files: {path: string; reason: string}[]; truncated: boolean; supported_languages: string[]; corpus_scope: string[]; limitations: string[]};
  metadata: {model_id: string | null; prompt_version: string; corpus_version: string | null; corpus_checksum: string | null; input_fingerprint: string | null; elapsed_ms: number};
}
