# CI and release gates

## Software checks

`.github/workflows/ci.yml` runs engine/extension tests, builds the React frontend,
wheel and VSIX, and checks an isolated wheel installation. It runs on PRs/pushes
without model credentials. Actions are pinned to commit IDs.

`.github/workflows/rag.yml` adds:

- Pinned official-source import, exact offsets, schema and index integrity.
- Reproducible RAG builds, immutable manifests and source-version isolation.
- Context-scoped annotations, approval revisions, missing sources and evaluations.
- Versioned JSON/Markdown metrics, explicitly distinguishing legal drafts from gold.
- An intentionally failing critical fixture, proving the gate rejects a miss.
- Real PostgreSQL versus SQLite reference retrieval and restart checks.
- Actual multi-stage Docker image / Compose startup, single-owner API evaluation
  and restart persistence tests. No Qdrant path is opened by two containers.

Fast PR tests use lexical baselines and test-only model responses. They do not
claim live inference or legal accuracy. Compose smoke tests download the local
CPU embedding model and exercise the actual hybrid runtime. No cloud model calls
run on ordinary PRs.

## Final RAG release acceptance

Tags `rag-v*` / `v*`, or explicit dispatch with `release_candidate=true`, run the
protected `rag-release` job after software, PostgreSQL and Compose checks pass.
It requires reviewed `evaluation/gold/ai-act.json` and protected
`GEMINI_API_KEY` credentials. The release script runs approved held-out retrieval
cases and seven synthetic live review cases (six broader areas plus a negative
control). Time/cost is bounded; source/evidence/citation validation remains local.

The final policy requires at least 50 approved cases across 10 subject areas,
a sealed holdout with Recall@10 at least 0.95, and zero misses in a separate
critical suite. These are acceptance targets, not measured current capability.
Draft cases, missing credentials, source mismatches or critical misses block the
release job. Missing prerequisites are recorded in an artifact and never treated
as a skipped green quality check. Semantic expert review remains distinct from
mechanical citation validity.

Application version, RAG manifest, source snapshot, dataset revision and run ID
are separate. Reports and failure examples are retained as seven-day artifacts.
Private source is not used in CI. The workflow does not publish packages, migrate
production databases or deploy AWS.

## Local commands

```sh
uv run --project engine --extra dev --extra workbench --extra workbench-test --extra rag python -m pytest engine/tests/test_official.py engine/tests/test_rag_api.py
uv run --project engine --extra rag python scripts/ci-rag.py --output .aiact-results/ci
uv run --project engine --extra rag python scripts/ci-rag.py --output .aiact-results/negative --force-failure
```

The last command must exit **3** for its deliberately missing known source.
PostgreSQL parity runs when `AIACT_TEST_POSTGRES_URL` points to a dedicated test
database. The test recreates RAG tables, so never use a database containing work.
Docker tests require a running engine. Current observed results and verification
limits are in [M1 status](M1-STATUS.md).
