# AI Act Copilot

A local retrieval workbench and Python review assistant by Evros Labs. Explore
versioned official sources, inspect how retrieval works, and build evaluation
cases with explicit context and reviewer feedback.

The source collection contains **119 articles, 14 annexes, 180 original recitals
and 47 amendment recitals** from the Publications Office of the EU. Five sample
test cases cover different topics. They are drafts, not expert-approved tests.

## Open the application

Dashboard: **[http://localhost:8000](http://localhost:8000)**.
The dashboard and API share this address when using Docker or the built frontend.
Keep the application process running while using it.

## Start with Docker (recommended)

Requirements: a running Docker engine with Docker Compose v2.20 or newer.
From the repository root:

```sh
cp .env.example .env
docker compose up --build
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Keep the command running.
The first setup downloads the local embedding model (about 64 MB) and builds the
source/vector indexes. Allow several minutes on a CPU. No Gemini key is needed
for source browsing, retrieval or annotation.

The React build and Python API are served by one container. SQLite, embeddings,
Qdrant and review history live in the persistent `rag-data` volume. Native
SQLite stays in `.aiact-workbench/`, which Git ignores. There is one
owner of the embedded vector index, with no separate Qdrant server.

Stop with Ctrl+C, or `docker compose down` from another terminal. These retain
data. A normal restart uses cached embeddings without downloading them again.
New RAG candidates preserve an existing active release until explicitly selected.

### Optional Gemini review

Add your key to the private `.env` file:

```dotenv
GEMINI_API_KEY=your-key
```

Restart the service after configuration changes. In Code test, enter
Python source and explicitly approve sending that code, context and retrieved
passages to Google. Then choose **Review & save result locally**. Keys never go
into browser settings, command arguments, reports or traces.

Local retrieval uses CPU embeddings regardless of the review provider. To use
Ollama instead, select `AIACT_PROVIDER=ollama`, configure its model and loopback
endpoint in native mode. Container-to-host Ollama networking is not enabled by
default. There is no automatic provider fallback.

## Run the built frontend without Docker

After native setup and `npm run build --prefix dashboard`, run from the repository root:

```sh
AIACT_STATIC_DIR="$PWD/dashboard/dist" uv run --project engine --extra workbench --extra rag python -m uvicorn aiact.workbench.api:create_app --factory --host 127.0.0.1 --port 8000
```

Open **[http://localhost:8000](http://localhost:8000)**. This serves the dashboard
and API together, without a separate Vite process.

## Short screen guide

The [short presentation and screen guide](docs/presentation/README.md)
introduces the system, Langfuse, RAG versions and extension points.

## Use the workbench

1. **Sources:** search source text or references, inspect exact wording
   and provenance. This screen is for reading sources.
2. **Code test:** describe the scenario, paste code or upload a source
   file, then choose **Run**. Code and description share a 24 KB limit. Inspect
   matching sources and label expected results. Examples remain on the right.
   Model analysis requires a configured provider; Gemini requires explicit consent.
3. **Test cases:** label sources, give reasons, save drafts, explicitly
   approve a new revision and export JSON. Use **Add required source** while
   preparing a scenario to select a source the test must find. Expectations and actual hits remain
   separate. A missing expected source is a false negative.
4. **RAG versions:** build a candidate, inspect its manifest and activate or
   roll back for local tooling tests. This does not pass the final quality gate.

Switch to **Workbench API guide** to exercise the same tools with a second,
authored technical domain. Its two engineering fixtures are separate from legal
expert gold. Feedback never globally excludes documents or trains the retriever.

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
uv run --project engine --extra workbench --extra rag python -m uvicorn aiact.workbench.api:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
npm ci --prefix dashboard
npm run dev --prefix dashboard
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` to the
Python service. Set `AIACT_API_TARGET` for a different local API address. No API
URL or secret is compiled into the browser bundle. Restart Python after backend
or `.env` changes. Native data is stored under `.aiact-workbench/`, gitignored.

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

[CI and release gates](docs/CI.md) describe PR checks, PostgreSQL parity,
container restart tests and protected live-model evaluation. Actual observed
checks and remaining acceptance are in [M1 status](docs/M1-STATUS.md).

## Source updates and RAG versions

The canonical source pack is pinned to CELEX `02024R1689-20260727`, with original
and amendment Official Journal sources stored separately. Raw XHTML, source
hashes and deterministic parser output ship in the engine. Consolidated text is
an informational reference; authentic legal acts are the Official Journal texts.

Application version, source snapshot, RAG release, case revision and evaluation
run are separate identities. RAG bundles pin the source, parser, chunking,
embedding files, lexical/vector indexes, retrieval code and budgets. Published
bundles are immutable. Changed source or model files require a new candidate.
Reviewed promotion requires an explicit decision and a passing quality gate.

See [architecture](docs/ARCHITECTURE.md), [workbench operations](docs/WORKBENCH.md)
and [corpus files](corpus/README.md).

## Existing adapters

The [VS Code extension](extensions/vscode/README.md) and
[GitHub Actions App](docs/PR-ACTIONS.md) remain supported. Their existing scan
path uses the labelled 114-passage legacy subset and reviewed question bank.
The full-corpus workbench and explicit CLI `--rag-release` path use the new RAG
runtime. Adapter migration to the common application is later work.

The portable `aiact scan PATH --json` contract remains unchanged: one JSON result,
0 for completed review, 1 for incomplete/failed review, and 2 for configuration
errors. Findings alone do not fail a scan. Explicit full-corpus example:

```sh
uv run --project engine --extra rag aiact scan examples/recruitment/ranker.py --rag-release RELEASE_ID --provider gemini --cloud-consent --json
```

Use the full ID from `aiact rag status`. No scanned code is executed. Zero findings
is not a compliance certificate. Detailed [Gemini settings](docs/GEMINI.md) and
[published release history](CHANGELOG.md) remain available.
