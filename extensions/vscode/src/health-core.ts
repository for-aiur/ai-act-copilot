export interface HealthCheck { id: 'engine' | 'ollama' | 'gemini' | 'model' | 'corpus'; status: 'ready' | 'unavailable' | 'unknown'; detail: string }
export interface HealthResult {
  schema_version: '1.0'; status: 'ready' | 'unavailable'; engine_version: string; python_version: string;
  provider?: 'ollama' | 'gemini'; endpoint: string | null; model_id: string | null; checks: HealthCheck[];
  errors: {code: string; message: string; path: string | null}[];
}
export function parseHealth(text: string): HealthResult {
  const data = JSON.parse(text);
  if (!data || data.schema_version !== '1.0' || !['ready','unavailable'].includes(data.status) ||
      typeof data.engine_version !== 'string' || typeof data.python_version !== 'string' ||
      !(data.endpoint === null || typeof data.endpoint === 'string') || !(data.model_id === null || typeof data.model_id === 'string') ||
      !Array.isArray(data.checks) || !Array.isArray(data.errors)) { throw new Error('Unsupported health response. Update the engine or check aiact.executable.'); }
  const provider = data.provider ?? 'ollama';
  if (!['ollama','gemini'].includes(provider)) { throw new Error('Unsupported inference provider.'); }
  const expected = ['engine','corpus','model',provider];
  const ids = new Set<string>();
  for (const check of data.checks) {
    if (!check || !expected.includes(check.id) || ids.has(check.id) ||
        !['ready','unavailable','unknown'].includes(check.status) || typeof check.detail !== 'string') { throw new Error('Malformed health check.'); }
    ids.add(check.id);
  }
  for (const error of data.errors) {
    if (!error || typeof error.code !== 'string' || typeof error.message !== 'string') { throw new Error('Malformed health error.'); }
  }
  if (data.status === 'ready' && (ids.size !== 4 || data.checks.some((c: HealthCheck) => c.status !== 'ready') || data.errors.length)) { throw new Error('Inconsistent ready health response.'); }
  if (data.endpoint !== null) {
    if (provider === 'gemini') { if (data.endpoint !== 'https://generativelanguage.googleapis.com') { throw new Error('Unexpected Gemini API endpoint.'); } }
    else { localHost(data.endpoint); }
  }
  return data;
}
export function localHost(endpoint: string): string {
  if (!/^http:\/\/(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?\/?$/.test(endpoint)) { throw new Error('Only a loopback Ollama endpoint can be started.'); }
  const url = new URL(endpoint);
  return `${url.hostname === 'localhost' ? '127.0.0.1' : url.hostname}:${url.port || '11434'}`;
}
