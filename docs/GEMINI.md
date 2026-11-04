# Gemini configuration

Gemini is the default review provider for the new workbench and fresh VS Code
setups. Local retrieval does not need Gemini. The older portable CLI keeps its
Ollama default unless a provider is selected explicitly. No path falls back to a
cloud provider automatically.

## Workbench

Copy `.env.example` to `.env`, set `GEMINI_API_KEY`, then restart the API or
Compose service. In Code test, select Python source and approve the
cloud-transfer checkbox before **Review & save result locally**. Selected source,
explicit context and retrieved official passages go to Google's fixed Gemini API.
The key stays on the Python side. Do not paste it into the dashboard.

## VS Code

Run **AI Act Copilot: Configure Gemini**. Enter the key in the masked field and
approve cloud review for that workspace. The extension uses SecretStorage and
passes the key through the child-process environment, never arguments/settings.
**Remove saved Gemini API key** removes that key and workspace consent; it does
not remove separately supplied environment variables.

`aiact.geminiModel` selects the cloud model. `aiact.model`, `aiact.endpoint` and
`aiact.ollamaExecutable` are Ollama settings. Choose `aiact.provider=ollama` for
local inference. On-save is off by default and never asks for consent automatically.

## CLI

Set `GEMINI_API_KEY` through your shell or secret manager, then explicitly select
`--provider gemini`. Full-corpus `--rag-release` review also accepts
`--cloud-consent`. The standalone CLI does not automatically export `.env` into
the legacy provider environment. Workbench settings read `.env` directly.

The configured model is `gemini-3.1-flash-lite`; model access and quota depend on
your account. Check current [Google pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [service terms](https://ai.google.dev/gemini-api/terms). No fixed price or
performance guarantee is asserted here. Generation is bounded to two passes,
with at most one shared schema/citation repair and a 120-second review deadline.

Keys are sent only in headers to the fixed Google endpoint. Redirects, proxy
inheritance and raw response/error-body logging are disabled. Health/model
metadata checks do not send source code, and do not prove generation will succeed.
Live Gemini and Langfuse observations are tracked in [M1 status](M1-STATUS.md).
