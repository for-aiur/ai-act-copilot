# Gemini preview

The engine and VS Code extension support two explicit providers: local Ollama
(default) and Gemini. They share the same two-pass pipeline, local corpus,
question bank, budgets and independent evidence validation. There is no fallback.

## VS Code

1. Install the 0.2.0 VSIX and reload the window. Install/update the matching
   engine with `uv run --project engine aiact --version` from the repository root.
2. Run **AI Act Copilot: Configure Gemini**. Enter your API key in the masked
   field and approve sending selected code/context to Google for this workspace.
3. Check **Provider setup**, then run **Review current Python file**.

The command saves the key in VS Code SecretStorage and sets `aiact.provider` to
`gemini` for the workspace. It does not put the key in settings JSON. The engine
receives it in the child-process environment, never command arguments.
**Remove saved Gemini API key** deletes the stored key and clears workspace
cloud consent. A separately supplied `GEMINI_API_KEY` environment variable is
not deleted by this command.

```json
{
  "aiact.provider": "gemini",
  "aiact.geminiModel": "gemini-3.1-flash-lite"
}
```

`aiact.model`, `aiact.endpoint` and `aiact.ollamaExecutable` remain Ollama settings.
To return to local inference, set `aiact.provider` to `ollama`.
On-save is off by default; cloud on-save also requires prior workspace consent.

## CLI

Create an [API key in Google AI Studio](https://aistudio.google.com/apikey).
For zsh, enter it without displaying it or adding it to shell history:

```sh
read -rs 'GEMINI_API_KEY?Gemini API key: '; echo
export GEMINI_API_KEY
uv run --project engine aiact doctor --provider gemini
uv run --project engine aiact scan examples/recruitment/ranker.py --provider gemini --json
```

`--provider gemini` explicitly opts into sending code to Google.
`AIACT_PROVIDER=gemini` can make that choice for your shell; `--model` or
`AIACT_MODEL` overrides the provider's default model. Do not commit keys or put
them in result files. Health checks query model metadata only, not your code;
quota/billing and actual generation may still fail after a successful check.

## Model, cost and data flow

The default is `gemini-3.1-flash-lite` with minimal thinking and at most 2,048
output tokens per call. On 2026-10-29, its standard text price was **$0.25 input /
$1.50 output per million tokens**. Gemini 2.5 Flash-Lite is cheaper but access is
restricted to previous users, so it is not the fresh-project default.
[Pricing](https://ai.google.dev/gemini-api/docs/pricing),
[availability and retirement dates](https://ai.google.dev/gemini-api/docs/deprecations).

Each scan normally makes two generation requests. A shared repair budget allows
at most one additional request; failures do not trigger automatic provider
switching. Actual cost depends on input/output tokens and your account quota.
The model name is configurable so it can be replaced when availability changes.

Selected Python source, source evidence, your explicit context, question options
and retrieved legal passages are sent to Google's fixed API endpoint. Corpus
retrieval and citation/line validation remain local. No legal website is fetched
during a scan. Google's handling of submitted data depends on the applicable
account, region and service terms; review the
[Gemini API terms](https://ai.google.dev/gemini-api/terms) for your account.

## Implementation boundary

`gemini.py` implements the existing `generate_json(prompt, schema, timeout)`
contract using stdlib HTTPS and schema-constrained JSON output. No new SDK or
provider registry is needed. Redirects and proxy inheritance are disabled, the
API key is carried in a header, and errors omit raw response bodies and keys.
JSON results add optional `metadata.provider`; reports identify cloud inference.

Automated tests mock Google's HTTP responses and verify request shape, errors,
key handling, consent, shared pipeline validation and stale editor results.
They do not establish live API availability, latency or review quality. A live
scan requires your API key and should be checked before a presentation.
