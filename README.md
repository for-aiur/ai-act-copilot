# AI Act Copilot

*by Evros Labs*

Understand where the AI in your Python code needs a closer look. Run a local
review to inspect source lines, a relevant official legal quotation, a next step
and a specific context question. **This is an engineering review assistant, not
a compliance certificate.**

New to the tool or the AI Act? Read the
[plain-language introduction](extensions/vscode/README.md).

## POC release

**Tag: `v0.1.5-poc.1` · extension: `0.1.5` · Python engine: `0.1.0`.**

This is a private GitHub pre-release for local POC testing, not a Marketplace or
PyPI release. Download the VSIX, Python wheel and `SHA256SUMS.txt` from the
[GitHub releases page](https://github.com/for-aiur/ai-act-copilot/releases).
Repository access is required. Source archives are available with the tag.
The [release notes](docs/releases/v0.1.5-poc.1.md) record scope and known limits.

## First setup

You need Python **3.11+**, VS Code **1.85+**, and
[Ollama](https://ollama.com/download) installed locally. Node **22+** is only
needed if you build the extension from source. Model/package downloads are
explicit setup operations; scans never download anything.

Clone the source and install the engine from the repository root:

```sh
git clone https://github.com/for-aiur/ai-act-copilot.git
cd ai-act-copilot
git checkout v0.1.5-poc.1
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./engine
```

Use a Python 3.11+ executable for the venv command. If `python3` is older, replace
it with your installed newer interpreter, such as `python3.12`. On Windows,
activate with `.venv\Scripts\Activate.ps1` in PowerShell. You can install the
release wheel instead of `-e ./engine` using `python -m pip install` followed by
the downloaded wheel's path.

Start Ollama (the desktop app or `ollama serve` in a separate terminal), then
explicitly download the tested model:

```sh
ollama pull qwen2.5:3b
aiact doctor
aiact scan examples/recruitment/ranker.py --json
```

Install the downloaded `ai-act-copilot-0.1.5.vsix` through VS Code's
**Extensions → … → Install from VSIX**, or:

```sh
code --install-extension /path/to/ai-act-copilot-0.1.5.vsix
```

Replace `/path/to` with the real downloaded-file location. If VS Code is already
open, run **Developer: Reload Window**. The extension ID is
`evros-labs.ai-act-copilot`. No Marketplace account is needed for local VSIX use.

## Review in VS Code

1. Open this repository **root folder**, trust the workspace and save a Python file.
2. Click the **robot icon** in the Activity Bar. Local setup shows the CLI,
   Ollama, selected model and legal corpus separately.
3. If Ollama is stopped, click **Start local service**. Keep its integrated
   terminal open. The helper uses a local bundle when available, otherwise the
   system Ollama; an explicit binary path is respected.
4. Open `examples/recruitment/ranker.py` and click **Review current Python file**.
5. Inspect Problems, hover and the report. Click source evidence to reveal code
   and the official link to read the source. Answer the context question and
   rerun if you have more deployment facts.

The first manual review can offer service startup and continues once setup is
ready. Startup health checks are read-only. The start action does not install
anything, does not create an OS login service and does not start a second server
when a healthy one is reachable. **Refresh health** checks setup again.

## Configure it

Press **Cmd+,** (macOS) or **Ctrl+,** (Windows/Linux), search
`@ext:evros-labs.ai-act-copilot`, and choose **Workspace** for this project or
**User** for global preferences. You can also run **Preferences: Open Workspace
Settings (JSON)** from the Command Palette and edit `.vscode/settings.json`:

```json
{
  "aiact.executable": "${workspaceFolder}/.venv/bin/aiact",
  "aiact.model": "qwen2.5:3b",
  "aiact.endpoint": "http://127.0.0.1:11434",
  "aiact.reviewOnSave": false
}
```

The CLI path above is for macOS/Linux; on Windows use
`${workspaceFolder}/.venv/Scripts/aiact.exe`. The checked-in settings already
configure this project's `.venv` and keep on-save off.

- **`aiact.ollamaExecutable`:** usually leave unset. If needed, choose the actual
  Ollama binary path, not a folder. For a standard macOS app installation, an
  example is `/Applications/Ollama.app/Contents/Resources/ollama`; use it only if
  the file exists. This is different from `aiact.executable`, the Python review CLI.
- **`aiact.endpoint`:** the Ollama server address. It must be on this computer
  (loopback), for example `http://127.0.0.1:11434`.
- **`aiact.reviewOnSave`:** set to `true` to opt in. It waits 800 ms after the last
  save, permits one active scan and discards results for changed content. It
  never prompts or starts a service automatically. Cancel via the progress notice.
- **`aiact.corpusPath`:** optional explicit cache file; normally leave unset.
  `${workspaceFolder}` works in CLI, Ollama and corpus paths.

After changing settings, click **Refresh health**. Service-start settings apply
on the next start; changing them does not stop another running service.
The extension's [full settings guide](extensions/vscode/README.md#configure-in-vs-code)
includes examples and explanations for every setting.

## Terminal commands and result contract

```sh
aiact doctor --json
aiact scan examples/recruitment --json
aiact scan examples/biometrics/identify.py --json
aiact scan examples/chatbot/assistant.py --json
aiact scan examples/negative_control/totals.py --json
aiact scan examples/ambiguous/score.py --context 'Purpose and deployment are undecided.' --json
aiact update --corpus /tmp/aiact-verified-cache.json
```

`scan --json` emits one JSON document on stdout; human errors use stderr.
ScanResult includes version, complete/partial/failed status, findings, operational
errors, coverage and model/prompt/corpus/input/timing metadata. Schema and example
payloads are checked in under `schemas/`. `doctor --json` has a separate health
contract so it can report an available corpus even when Ollama is stopped.

- **0:** completed review, including findings. Zero findings is not certification.
- **1:** incomplete or failed review, including skipped coverage.
- **2:** usage/configuration error.

CLI options `--model`, `--endpoint`, `--corpus` override `AIACT_MODEL`,
`AIACT_OLLAMA_URL`, `AIACT_CORPUS`. Inference accepts loopback only, with redirects,
proxies, remote model aliases and automatic fallback rejected.

## Scope, evidence and privacy

The POC uses one Python engine process and a thin TypeScript adapter; there is no
HTTP backend, database, telemetry or scanned-code execution. Two local model
passes extract purpose/facts and review retrieved passages. Initial
missing-context explanations and question choices use reviewed domain wording;
this is grounded triage, not unrestricted legal reasoning.

Default bounds are 10 Python files, 100 KB/file before reading, 24 KB total source
and explicit context, up to 6 passages/12 KB legal text, at most 3 findings
(current prompt focuses on one), 60 seconds/request and 120 seconds/scan. One
schema repair is allowed within the shared deadline. Coverage reports exclusions,
parse errors and truncation. Hidden paths, dependencies/builds, gitignored files,
symlinks and binary input are excluded. The allowlist cannot guarantee source is
secret-free; inspect input before reviewing or sharing JSON evidence.

The six-passage [reviewed corpus](corpus/README.md) covers selected recruitment,
remote-biometric, classification and transparency provisions. It is not complete
legal coverage. Actor roles, deployment facts and applicability dates are not
inferred from an API name. `aiact update` explicitly verifies reviewed official
passages and atomically replaces the cache, preserving the last good version on
failure. Changed/new law requires manual review. Scans use only local resources;
official links open on user action. Raw snippets are not persisted except when
you explicitly save a result containing evidence.

## Build and verify

From the root with a Python 3.11+ venv activated and Node 22+ on PATH:

```sh
python -m pip install -e './engine[dev]'
python -m pytest engine/tests
cd extensions/vscode
npm ci
npm test
npm run package
```

The lockfile is included. The generated VSIX contains the compiled adapter,
introduction and icons, not Node build dependencies. No open-source distribution
license has been selected; local/private packaging skips a license file.

The explicit live evaluator uses the real installed model sequentially:

```sh
python scripts/evaluate_live.py --output-dir .aiact-results
```

Run that command from the repository root. Result JSON contains code evidence
and is gitignored. Mechanical checks do not prove semantic support.

See [verification](docs/VERIFICATION.md) for actual checks and remaining manual
editor acceptance. The tested device is an Intel i5 Mac with 16 GB RAM, Python
3.12 and Node 24. Earlier Qwen 3B CLI measurements were 61.2 s cold / 26.2 s warm;
these are not guarantees on other devices. Phi3 timed out and Qwen 1.5B produced
unreliable reasoning in earlier tests. The full Linear milestone is not closed
merely by publishing this POC pre-release.

On the existing demo Mac, `.venv` and `.tools/ollama` already exist. Reuse them;
the system's default Python 3.9 and Node 20 are older than the build requirements.
`sh scripts/start-local-model.sh` is an explicit source-checkout helper that keeps
Ollama in the foreground, disables cloud mode and uses loopback-only networking
on macOS. Keep its terminal open.
