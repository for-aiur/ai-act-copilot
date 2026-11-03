# AI Act Copilot for VS Code

*by Evros Labs*

Review a saved Python file, inspect code evidence in Problems/hover, and open a
Markdown report with an official quotation, next action and context question.
This is an engineering review assistant. Zero findings does not certify compliance.

## Install from this checkout

Use Python 3.12, uv and Node 24. From the repository root:

```sh
uv sync --project engine
npm ci --prefix extensions/vscode
npm run package --prefix extensions/vscode
```

In VS Code, choose **Extensions > Install from VSIX**, select the generated
`extensions/vscode/ai-act-copilot-0.4.0.vsix`, then reload the window. Open the
repository root and trust the workspace. Set the engine path if necessary:

```json
{
  "aiact.executable": "${workspaceFolder}/engine/.venv/bin/aiact",
  "aiact.provider": "gemini",
  "aiact.geminiModel": "gemini-3.1-flash-lite",
  "aiact.reviewOnSave": false
}
```

Existing workspace provider choices are retained. Paths with spaces do not need
extra shell quoting inside settings values.

## Configure and review

1. Run **AI Act Copilot: Configure Gemini**. Enter the API key in the masked field
   and approve cloud review for this workspace. The key is saved in SecretStorage,
   never settings JSON or command arguments.
2. Open the robot's **Provider setup** view. Refresh health to check the engine,
   provider/model and legal subset. Gemini does not need an Ollama service.
3. Save a Python file and run **AI Act Copilot: Review current Python file**.
4. Inspect source evidence, open the official link, and use **Answer context
   question and review** to add facts for the current session.

**Remove saved Gemini API key** removes that stored key and clears workspace
consent. It does not remove separately supplied environment variables. For
account, quota and data-sharing details see the [Gemini guide](https://github.com/for-aiur/ai-act-copilot/blob/main/docs/GEMINI.md).

## Optional local Ollama

Set `aiact.provider` to `ollama`, select an installed model in `aiact.model`, and
use a loopback `aiact.endpoint`. The health view offers **Start local service**
when stopped. It uses a visible terminal; keep that terminal running. Set
`aiact.ollamaExecutable` only when the binary is outside PATH. Selecting a model
never downloads it. There is no automatic cloud fallback.

## Result and lifecycle

- **Needs context / potential concern:** inspect the evidence and answer the
  specific question. Priority is review priority, not a legal risk class.
- **Complete:** the review finished within the displayed coverage.
- **Partial:** files or coverage were skipped/truncated; inspect the reasons.
- **Unavailable / failed:** no completed review was produced. Refresh setup.

`aiact.reviewOnSave` is opt-in. It debounces saves by 800 ms, runs at most one
scan and discards stale document results. It never starts a service or requests
cloud consent automatically. Reviews can be cancelled from their progress UI.
Untrusted workspaces never execute the CLI. Generated text is escaped; arbitrary
Markdown command links are disabled.

## Coverage

The extension's compatible scan path currently uses the **legacy 114-passage
subset and authored question bank**. The full-corpus React workbench and explicit
CLI `--rag-release` path are documented in the
[root guide](https://github.com/for-aiur/ai-act-copilot#readme).
Do not infer full-act editor coverage from the M1 dashboard's source inventory.

## Planned next steps

Later milestones add resumable human review and common application adapters.
M1's full-corpus retrieval evaluation tools are available in the local React
workbench. Broad review quality and editor integration still require measured
acceptance. No Marketplace publication is implied by a local VSIX build.
