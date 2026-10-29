import * as vscode from 'vscode';

export const GEMINI_KEY = 'aiact.geminiApiKey';
export const GEMINI_CONSENT = 'aiact.geminiConsent';

export function inferenceSettings(config: vscode.WorkspaceConfiguration) {
  const provider = config.get<string>('provider', 'ollama');
  if (provider !== 'ollama' && provider !== 'gemini') { throw new Error('Choose Ollama or Gemini in AI Act Copilot provider settings.'); }
  return {provider, model: provider === 'gemini' ? config.get<string>('geminiModel', 'gemini-3.1-flash-lite') : config.get<string>('model', 'qwen2.5:3b')};
}

export function localEnvironment(): NodeJS.ProcessEnv {
  const env = {...process.env};
  delete env.GEMINI_API_KEY;
  delete env.GOOGLE_API_KEY;
  return env;
}

export async function geminiEnvironment(context: vscode.ExtensionContext): Promise<NodeJS.ProcessEnv> {
  const env = localEnvironment();
  const key = await context.secrets.get(GEMINI_KEY) || process.env.GEMINI_API_KEY;
  if (key) { env.GEMINI_API_KEY = key; }
  return env;
}
