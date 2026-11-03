# AI Act Copilot implementation playbook

## Current mission

Build M1: a local, domain-independent retrieval/evaluation workbench for the full
pinned official 2026 AI Act. The user authorized tooling and dashboard delivery
before model tuning, sequential implementation of all M1 tickets, and removal of
obsolete setup documentation. React + Vite + TypeScript is the frontend choice.

Start with README.md, docs/ARCHITECTURE.md, docs/WORKBENCH.md and docs/M1-STATUS.md.
Linear project: https://linear.app/yildirim-labs/project/ai-act-copilot-c72174fb02fd/overview
The October POC was accepted on a limited presentation scope. Do not confuse it
with M1 or claim final M1 acceptance from infrastructure or draft-case metrics.

## Working rules

1. Read the current issue and relevant code; inspect Git status and preserve
   unrelated work. Work sequentially. Parallel agents require explicit permission.
2. Take bounded vertical slices with observable outcomes and meaningful checks.
   The current user authorized the whole M1 sequence without intermediate approval.
3. Resolve the Linear issue before coding. Use its exact gitBranchName, not a
   codex/ prefix. PR titles include the issue ID and bodies link the issue.
4. Preserve ScanResult 1.0 and existing CLI/editor/Actions consumers. Contract
   changes must be additive or versioned with consumers/schema/tests updated.
5. Record changes, commands/results, limitations and next steps. Never claim
   live inference, container operation, offline operation or legal quality without
   observed evidence. Do not close tickets with unfulfilled acceptance criteria.
6. Keep engine pyproject/__init__ versions synchronized, and extension/dashboard
   package/lock versions synchronized. Record published changes in CHANGELOG.md.
   Never rewrite an already published release tag.
7. No em dashes in documentation, user-facing text or responses. Use short,
   concrete explanations. New ideas beyond acceptance go to later milestones.

## Architecture and boundaries

- One Python package, React workbench and thin VS Code/Actions adapters.
- FastAPI serves the local API and production frontend. One process owns Qdrant
  Local. Evaluation containers call the API instead of opening that path.
- SQLite is the local canonical store. PostgreSQL is selected explicitly and
  needs parity tests. Changing a URL never migrates data automatically.
- Official source import, generic contracts, storage, embeddings, retrieval,
  review, feedback and evaluation are separate modules under engine/src/aiact/rag.
- Local CPU embeddings and lexical retrieval are required for M1. Qdrant indexes
  are rebuildable artifacts; they are not the authoritative legal text store.
- Gemini is the new workbench/editor review default; Ollama remains optional.
  The compatible legacy CLI local default is preserved. No provider fallback.
- LangGraph/HITL is M2; full product worker/API integration is M3; AWS and
  application-level bot migration are M4. Do not implement those here.

## Evidence and privacy

- Import law only from verified official sources. Keep consolidated informational
  text, original binding provisions, recitals, guidance and proposals distinct.
  Store exact normalized text, source URL, hash, CELEX, version and offsets.
- Publication, entry into force and conditional application dates are separate.
  Unknown actor roles, intended uses and dates remain unknown. A valid quote is
  not proof of semantic legal support.
- Never execute scanned code or model-proposed commands. Keep bounded source
  collection, allowlists, ignored/secret/binary exclusions and escaping-symlink
  rejection. No automatic README ingestion or raw source logging.
- Source/corpus/model downloads are explicit setup operations. Retrieval and
  scans do not fetch legal text. Query embeddings are local and cache-only.
- Gemini sends selected source/context only after explicit consent. Keys belong
  in private environment/.env or editor SecretStorage, never arguments/settings,
  logs, reports, browser bundles or traces. Fixed Google endpoint, no redirects.
- Langfuse EU export is separately opt-in. Export only bounded model/source/run
  identities, status, stage duration and actual available usage. Never export
  raw code, prompts, unredacted answers, reviewer text or secrets. Failed tracing
  cannot change ScanResult.
- Explicitly saved reviews may retain evidence in the private local store.
  GitHub Actions bot state remains stateless and separate; never execute PR code
  or load bot credentials/configuration from an untrusted PR head.

## Retrieval, versions and evaluation

- Source snapshots and RAG bundles are immutable and content-addressed. Pin parser,
  adapter, chunks, embedding files, index fingerprints, query/rank policy and
  budgets. Detect mixed versions and stale embeddings, rather than silently reuse.
- Keep source snapshot, application release, RAG release, label revision and
  evaluation run distinct. Promotion and rollback are explicit. Failed/partial
  operations preserve the last active version and historical decisions.
- Retrieval requests include intended use and role/deployment context. Expose
  actual lexical/dense/exact/fusion/rerank/expansion scores and source offsets.
- Feedback is scoped to context, source and retriever version. No global source
  blacklists, automatic training or unreviewed ranking changes.
- Gold supports document and exact paragraph targets. Missing mandatory clauses
  are false negatives even when another paragraph of the same article was found.
- Model-authored cases stay drafts until explicitly reviewed. Do not invent
  expert approval, qualifications, unseen holdout results or accuracy claims.
- Final M1 acceptance needs approved gold, sealed holdout/critical suites and
  measured quality gates. Infrastructure completion alone does not pass M1.

## Review and UI

Retain bounded two-pass review, independent code/citation validation, at most four
findings, six passages/12 KB legal text, 60 seconds/request, 120 seconds total and
one shared schema/citation repair. Operational errors never become empty success.
Python evidence uses 1-based inclusive repository-relative lines. The workbench
may accept one explicitly uploaded UTF-8 source file from its allowlist, up to
24 KB including context. Non-Python uploads use exact numbered-line evidence
without claiming AST parsing or execution. Existing CLI/editor collection stays
Python-only. Source/model
text is data, never instructions. Model URLs are never trusted.

Use clear reviewing, complete, partial, failed and unavailable states. Questions
must be specific and qualified; no compliance percentage or compliant badge.
The workbench may show measured retrieval metrics with dataset/version/scope.
Editor scans respect workspace trust, one active process and stale-result checks;
spawn with argument arrays and keep on-save opt-in. No arbitrary Markdown commands.
