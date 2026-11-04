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
