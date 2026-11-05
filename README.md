# AI Act Copilot

Review AI code against official EU AI Act sources. Developers can inspect the
code and evidence behind a finding. Reviewers can track open issues across
repositories, record decisions and see which findings reached a release.

## Start locally

With Docker and Docker Compose running, run this from the repository root:

```sh
docker compose up --build
```

Open **[the local homepage](http://127.0.0.1:8000/)** when the services are ready.
The first start downloads a CPU embedding model and builds the source index.
Allow a few minutes. The app creates a demo workspace with password-free
entry. No API key is required to explore the dashboard or browse legal sources.

Stop with Ctrl+C. To remove the containers, run `docker compose down`. Projects,
review history and the local index persist in the Compose volume.

## Take the demo tour

1. Open [the sign-in page](http://127.0.0.1:8000/login) and select **Enter the demo**.
2. On a fresh workspace, create a project. Select **Load demo repositories**,
   choose `example/recruitment`, name the project and click **Create project**.
   If the workspace already has a project, open [Projects](http://127.0.0.1:8000/app/projects)
   to create or edit one.
3. In **Overview**, select **High priority in releases**. Open the finding for
   PR #14 to see its priority, release, code evidence and official citations.
4. In **Findings**, filter by repo, priority, status, code stage or policy.
   Add an explanation and select **Resolve** to see the decision in its history.
5. Open [Repository Scans](http://127.0.0.1:8000/app/audits) for a demo repository scan with
   progress, coverage, findings and a PDF report.

The GitHub activity, dependency map and repository scan use demo data.
Live GitHub event ingestion and hosted deployment are planned for M4.

## Run a model review

To run the website example or a saved model review with Gemini, put your key
in the private `.env` file at the repo root. If the stack is already running,
rerun the startup command so Compose picks up the change.

```dotenv
GEMINI_API_KEY=your-key
```

Open [Try a sample review](http://127.0.0.1:8000/onboarding), choose an example,
optionally add a question, approve sending it to Gemini and click **Run example**.
Findings appear on the page. To keep a result or answer a context question later,
start the review from **Code Checks** in the dashboard.

## What you can explore

| Area | What it shows |
| --- | --- |
| **Overview & Projects** | Project score, open High findings in releases, and charts by priority, code stage, policy and week. Filter the charts by repository and priority. |
| **AI Systems** | Project inventory, system relationships and saved release evidence. Open the nutrition and insurance example to try the flow. |
| **Findings** | Searchable evidence, PR and release context, source versions and decision history. |
| **Code Checks** | Saved results for individual code checks. |
| **Repository Scans** | Demo scan of a branch or release, with coverage and a PDF report. |
| **API** | Workspace keys, recorded requests and daily request totals. |
| **[Workbench](http://127.0.0.1:8000/workbench)** | Official sources, retrieval tests, feedback, RAG versions and evaluation. |

## Reference

- [Local development, Docker and PostgreSQL](docs/LOCAL-DEPLOYMENT.md)
- [Workspaces and review API](docs/LOCAL-WORKSPACES.md) and [how the review agent works](docs/agent/README.md)
- [Workbench operations](docs/WORKBENCH.md) and [official source packs](corpus/README.md)
- [VS Code extension](extensions/vscode/README.md) and [GitHub Actions App](docs/PR-ACTIONS.md)
- [Architecture](docs/ARCHITECTURE.md), [CI checks](docs/CI.md) and [M1 status](docs/M1-STATUS.md)
- [Gemini settings](docs/GEMINI.md), [presentation](docs/presentation/README.md) and [release history](CHANGELOG.md)
