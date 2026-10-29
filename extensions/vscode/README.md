# AI Act Copilot

*by Evros Labs*

**Understand where the AI in your code needs a closer look.**

AI Act Copilot helps developers connect what their code does with questions
about how an AI system will be used. Open a Python file and run a review. You get
code evidence, a relevant official source and a concrete question to investigate.
You do not need to know the AI Act before you start.

## What is the AI Act?

The AI Act is an EU law that sets rules for developing and using artificial
intelligence. Which rules matter depends on the system's intended use and your
role in developing or using it. The
[European Commission's overview](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
is a starting point if you want to learn more.

Code alone cannot explain the whole situation. A prediction might be used in a
classroom experiment, an internal prototype, or a decision that affects real
people. This tool helps you identify what to check and what context is missing.

## A simple example

Imagine a model that scores job applicants' CVs and returns a shortlist.

The tool can point to the function that ranks candidates, show an official
passage about recruitment, and ask:

> Will these scores affect real hiring decisions in the EU, and who reviews the shortlist?

That gives the developer a concrete question to discuss with the product team
or a qualified reviewer, together with the code and official text behind it.

## What you get from a review

- **A place to look:** the source file and exact lines to inspect.
- **A reason to look:** a potential concern or a specific missing-context question.
- **An official source:** a short quotation and a link you can open yourself.
- **A next step:** something to investigate or document before rerunning.

This is an engineering review assistant, not legal advice or a compliance
certificate. A result with no findings does not establish that a system complies
with the law.

## Start here

1. **Open your project.** Open the repository root in VS Code, trust the workspace
   and save the Python file you want to review.
2. **Check local setup.** Click the AI Act Copilot robot icon in the left sidebar.
   The Local setup panel shows the review engine, local AI service, model and
   legal-source cache. If Ollama is stopped, click **Start local service** and
   keep its terminal open. Models and packages must already be installed.
3. **Review and inspect.** Click **Review current Python file**. Read the report,
   inspect the marked code in Problems or hover, and open the official source.
   Use **Answer context question and review** to add facts for this session.

You can also find these actions in the Command Palette under **AI Act Copilot**.
The status-bar item opens the Local setup panel. **What is this tool?** reopens
this introduction; **Future plans** jumps to the last section below.

## How to read the result

- **Needs context:** the code leaves an important fact unanswered.
- **Potential concern:** something may warrant a closer engineering review.
- **Complete:** the review finished within the reported scope.
- **Partial:** some input or coverage was skipped or limited; read the coverage.
- **Unavailable / failed:** the review could not finish. Check local setup.

Review priority tells you what to inspect first. It is not a legal risk class.

## What works today

This local prototype reviews bounded Python input with an installed Ollama model
and a small reviewed subset of official legal text. Its examples cover
recruitment, biometric identification, a chatbot, ordinary non-AI code and a model
whose purpose is unknown.

The model extracts purpose and facts, then reviews retrieved passages. Source
ranges and legal quotations are checked independently. For the initial
missing-context review, explanations use reviewed domain wording and questions
come from reviewed options; the model also selects evidence, priority and a next
action. It is not unrestricted legal reasoning.

Reviews keep source analysis on this machine. Opening official links requires a
user action; refreshing legal sources and downloading models are separate,
explicit setup operations. Explicit answers are held in extension memory for
the session. The prototype cannot infer a full deployment, determine every actor
role, or cover every provision from one file.

## Local setup and optional settings

Install the Python engine and a local Ollama model before reviewing. Configure
`aiact.executable` with the CLI path, for example
`${workspaceFolder}/engine/.venv/bin/aiact`, and select an installed `aiact.model` tag.
Ollama is the local program that runs that model.

The native health panel checks the CLI, Ollama, selected model and corpus
separately. **Refresh health** checks again. Startup checks are read-only in
trusted workspaces; nothing is installed or downloaded. On the first manual
review, stopped Ollama offers a start action and the review continues once
setup is ready. An already reachable service is reused. The start action uses a
visible VS Code terminal, not an OS login service.

If needed, configure `aiact.ollamaExecutable` for a system binary outside PATH.
The start action otherwise uses the project helper or local bundled binary when
present. `aiact.endpoint` must be a loopback address.

`aiact.reviewOnSave` is optional and defaults to false. When enabled, it debounces
saves by 800 ms, allows one active scan and discards results for changed content.
On-save never prompts or starts a service automatically. You can cancel a review
from its progress notification.

## Configure in VS Code

There are two ways to change these settings. You do not need to edit the engine.

**Settings screen:** press **Cmd+,** on macOS or **Ctrl+,** on Windows/Linux,
then search for `@ext:evros-labs.ai-act-copilot`. Choose **Workspace** to change
only this project, or **User** to use a setting across projects. Find **Review On
Save** to enable automatic review, or **Ollama Executable** to choose a binary.

**JSON:** run **Preferences: Open Workspace Settings (JSON)** from the Command
Palette. This edits `.vscode/settings.json` in the project. Start with:

```json
{
  "aiact.executable": "${workspaceFolder}/engine/.venv/bin/aiact",
  "aiact.model": "qwen2.5:3b",
  "aiact.endpoint": "http://127.0.0.1:11434",
  "aiact.reviewOnSave": false
}
```

This example uses the engine environment created by `uv run --project engine`.
Paths containing spaces need no extra quotes inside the JSON string.

| Setting | What it controls | When to change it |
| --- | --- | --- |
| `aiact.executable` | The Python review CLI, which reads code and produces the report | When the engine is installed elsewhere |
| `aiact.ollamaExecutable` | The program that runs the local model; used by **Start local service** | Only when Ollama is outside PATH or you want a specific installation |
| `aiact.model` | The exact installed model tag | When you explicitly install and test another local model |
| `aiact.endpoint` | The local Ollama address | If your local server uses another port; remote hosts are rejected |
| `aiact.reviewOnSave` | Automatic review after saving Python files | Set to `true` when you want it; default is `false` |
| `aiact.corpusPath` | An optional explicit legal-cache JSON file | Usually leave unset to use the verified local/default subset |

The review CLI and Ollama are different programs. Changing `ollamaExecutable`
does not select the Python interpreter, and changing `model` does not download a
model.

You can normally leave `ollamaExecutable` unset. The start action uses the local
project bundle when present, otherwise a system `ollama` on PATH. To select a
particular installed binary, add its real path, for example on macOS:

```json
"aiact.ollamaExecutable": "/Applications/Ollama.app/Contents/Resources/ollama"
```

Only use that example if the file actually exists on your machine. You can also
set an absolute path to another installation. The project helper respects this
explicit choice. `${workspaceFolder}` substitution works in executable and corpus
paths. For a custom cache, an example is
`"aiact.corpusPath": "${workspaceFolder}/legal-cache/corpus.json"`.

To enable on-save, change the value to `"aiact.reviewOnSave": true`. It waits
800 ms after the last save, keeps one scan active and discards results if the
reviewed content changes. It never starts Ollama or prompts automatically. If
setup is unavailable, open Local setup and start/check the service manually.

After changing settings, click **Refresh health**. Startup settings affect the
next service start; a healthy existing service is reused. If you need to restart
a service you launched, close its Ollama terminal and use **Start local service**
again. Keep that terminal open during reviews. Cancel a scan from its progress
notification.

See the [VS Code settings guide](https://code.visualstudio.com/docs/configure/settings)
for the difference between User and Workspace settings.

## For contributors

Build with Node 22+ and npm: `npm ci`, `npm test`, `npm run package`. The VSIX is
for local installation; nothing is published to the Marketplace. The extension
calls the engine with argument arrays and contains no legal reasoning or cloud
inference. It uses native editor surfaces, escapes generated text and does not
enable arbitrary Markdown command links.

## Planned next steps

These are future goals, not features available in this prototype:

1. **More reliable reviews:** broader evaluation examples, better question
   quality and measured performance on different machines.
2. **An easier first run:** reproducible public CLI/Marketplace packages and
   clearer setup for people who have never installed a local model.
3. **Broader reviewed coverage:** more official passages and use cases, with
   clear source provenance and limits.
4. **More ways to work:** reuse the independent engine in other editors and CI;
   explore enterprise model integrations with explicit data-sharing choices.
5. **Keep past reviews current:** track official legal changes, distinguish
   binding text from guidance and proposals, and show which earlier reviews may
   need another look.
