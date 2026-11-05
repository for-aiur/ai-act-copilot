# Local stack and future hosting boundary

## What runs locally

`docker compose up --build` starts the React dashboard, FastAPI service and its
single review worker. The dashboard is at `http://localhost:8000`; the API is
available at `http://localhost:8001`. SQLite, review history, embeddings and
embedded Qdrant are stored in the persistent `rag-data` volume. The worker is
the only process that opens the local vector index.

The public project page, local registration and signed-in dashboard are all in
the React app. `/workbench` is the separate internal RAG workbench. Workspaces
share the installation's legal corpus and active RAG release, while reviews,
API keys and usage are scoped to a workspace.

Gemini review is a cloud call. A key can be kept in the untracked `.env` file;
the reviewer must explicitly approve sending the selected code and context for
each review. Langfuse is an optional external service. Its traces contain stage
metadata, not code, prompts or answers. Neither service is required to browse
sources, search or annotate cases. Ollama is optional and is not started by
Compose.

SQLite is the default. To try PostgreSQL, set
`DATABASE_URL=postgresql+psycopg://aiact@postgres:5432/aiact` in `.env` and run
`docker compose --profile postgres up --build`. The profile keeps PostgreSQL
inside the Compose network. It uses a separate volume. Changing the URL does
not copy SQLite data. Stop containers with `docker compose down`; this preserves
volumes. Add `-v` only when you intend to erase local data.

## Future AWS mapping

This table is a later design boundary, not a deployment plan. Nothing here
creates an AWS account, provisions a service or moves local data.

| Local part | Possible hosted part | Why revisit it |
| --- | --- | --- |
| FastAPI and one worker | ECS Fargate service | Keep the API and its retrieval worker together while there is one index owner. |
| In-process review queue | SQS plus a separate worker | Add this only when reviews need independent scaling or durable delivery. |
| SQLite database and local user files | RDS PostgreSQL and private object storage | Move shared records and uploaded material to managed durable storage. |
| Embedded Qdrant | Managed vector service or a dedicated retrieval service | Choose only after measured load or availability needs outgrow one owner. |
| `.env` secrets | AWS Secrets Manager | Keep provider and telemetry keys out of images and deployment files. |
| Langfuse Cloud and Gemini API | Existing external services | They remain external integrations unless a later privacy review changes that choice. |

Before any hosted deployment, replace local password accounts and API keys with
reviewed identity, authorization, secret rotation, backups and tenant-isolation
controls. Define data retention and legal-data update ownership. Measure latency,
throughput and retrieval quality first. Do not infer a production capacity from
local timings or the synthetic demo cases.

For setup and the screens, start at the [main README](../README.md). For tenant
and API behavior, see [local workspaces](LOCAL-WORKSPACES.md).

## Native development

Requirements: Python **3.12**, [uv](https://docs.astral.sh/uv/) and Node **24**.
Intel Mac local embeddings require Python 3.12; the engine lockfile selects a
compatible ONNX Runtime. The ordinary CLI supports Python 3.11+.

First setup, with an explicit embedding download:

```sh
uv sync --project engine --python 3.12 --extra workbench --extra rag
AIACT_DOWNLOAD_MODEL=true uv run --project engine --extra workbench --extra rag python -m aiact.workbench.bootstrap
```

Start the API:

```sh
uv run --project engine --extra workbench --extra rag python -m uvicorn aiact.workbench.api:create_app --factory --host 127.0.0.1 --port 8001
```

In a second terminal:

```sh
npm ci --prefix dashboard
npm run dev --prefix dashboard
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` to the
Python service on port 8001. Set `AIACT_API_TARGET` for a different local API
address. No API URL or secret is compiled into the browser bundle. Restart Python
after backend or `.env` changes. Native data is stored under `.aiact-workbench/`,
gitignored.

## Commands and verification

```sh
# Inspect the active source/RAG identity.
uv run --project engine --extra rag aiact rag status

# Evaluate local cases; results distinguish drafts and approved gold.
uv run --project engine --extra rag aiact rag eval --output .aiact-results/evaluation.json

# Explicit network operations, without changing the active corpus.
uv run --project engine --extra rag aiact corpus check
uv run --project engine --extra rag aiact corpus sync --staging

# Full automated engine tests and frontend builds.
uv run --project engine --extra dev --extra bot --extra workbench --extra workbench-test --extra rag --extra postgres python -m pytest engine/tests
npm run build --prefix dashboard
npm test --prefix extensions/vscode
```

`docker compose run --rm rag-eval` evaluates through the running API, so it never
opens Qdrant concurrently. For final acceptance, `aiact rag eval --require-quality
--include-holdout` fails unless the expert-gold policy passes. It is expected to
fail with the initial draft-only legal data. Reports include misses and sample
size uncertainty, rather than implying certified compliance.

[CI and release gates](CI.md) describe PR checks, PostgreSQL parity,
container restart tests and protected live-model evaluation. Actual observed
checks and remaining acceptance are in [M1 status](M1-STATUS.md).

## Run the built frontend without Docker

After native setup and `npm run build --prefix dashboard`, run from the repository root:

```sh
AIACT_STATIC_DIR="$PWD/dashboard/dist" uv run --project engine --extra workbench --extra rag python -m uvicorn aiact.workbench.api:create_app --factory --host 127.0.0.1 --port 8000
```

Open **[http://localhost:8000](http://localhost:8000)**. This serves the dashboard
and API together, without a separate Vite process.
