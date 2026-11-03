# M1 implementation record

Updated 3 November 2026. Tooling-first delivery is distinct from final M1 quality
acceptance. Do not mark the milestone complete using draft-case metrics.

## Implemented

- EVR-35: pinned Publications Office consolidated 2026 XHTML plus original and
  amendment recitals. 119 articles, 14 annexes, 180 original recitals and
  47 amendment recitals; 360 documents / 1,773 exact-offset chunks.
- EVR-45: generic source, query, candidate, golden-case and evaluation records,
  with AI Act and authored technical documentation adapters.
- EVR-33/36: typed runtime settings, SQLite/PostgreSQL-ready immutable storage,
  source/paragraph provenance and separately qualified date rules.
- EVR-43/37: immutable RAG bundles, FTS/BM25, CPU FastEmbed, single-owner Qdrant,
  explicit reference lookup, fusion, reranking and bounded expansion traces.
- EVR-41/42: React workbench, domain switching, source search, context-aware runs,
  annotations, manual missing-source addition, revisioned approval, JSON export,
  evaluation and before/after run comparison.
- EVR-38: optional full-corpus Python review reusing bounded source collection,
  provider protocol and deterministic code/citation validation.
- EVR-24/26: metadata-only opt-in Langfuse OTLP export; new editor/demo Gemini
  default with explicit consent, existing CLI local default preserved.
- EVR-25: 54 model-authored development drafts across 18 subject areas, plus
  two approved technical fixtures. No expert-approved legal gold or untouched
  holdout is claimed.
- EVR-39: actual official-version discovery, pinned-source staging, version diffs
  and a quality-gated explicit promotion path.
- EVR-46/44: Compose runtime, deterministic CI artifacts, baseline deltas,
  PostgreSQL parity and protected final-release gates.

## Observed checks

- Final complete engine suite: 195 passed, one PostgreSQL test skipped locally.
- Import/source integrity, contract, storage, context isolation, manifest,
  retrieval, feedback and API tests passed during their individual slices.
- Real local BAAI/bge-small-en-v1.5 ONNX embedding downloaded and executed on CPU.
  ONNX Runtime 1.23.2 imports on this Intel Mac; locked resolution records it.
- Real full-corpus hybrid build and retrieval succeeded; Qdrant reopened and
  returned results after closing its owner.
- Official SPARQL discovery returned 2026-07-27 and 2024-07-12 consolidated editions.
- React production build passed. Native browser displayed full source inventory,
  domain switching and real FTS/dense/fusion stage results.
- Existing VS Code suite after default change: 31 passed.
- Latest targeted tracing/provider tests: 38 passed.
- Docker Compose configuration validates. Local Docker daemon remains unavailable;
  UI launch timed out. No local container startup/restart acceptance is claimed.

## Remaining acceptance

Final browser and isolated wheel checks are in progress. Observe CI Compose
and PostgreSQL results when available. Gemini and Langfuse live credentials are absent from this session:
live cloud review/trace acceptance remains unverified. Expert-approved legal gold,
sealed holdout, semantic review and measured final M1 quality targets remain open.
Protected release CI intentionally fails when these prerequisites are absent.
