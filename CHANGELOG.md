# Changelog

Published POC snapshots are listed here. Extension and engine versions are
independent; Git tags identify the complete repository snapshot.

## Unreleased

- EVR-34/32: package the customer dashboard and FastAPI worker as one local
  Compose stack, with persistent SQLite and an optional private PostgreSQL
  profile. Add CI startup and retrieval-persistence checks for both profiles,
  and document the local boundary and possible future hosting map.

- EVR-31: separate the public project page from the signed-in local workspace.
  Add sample-guided reviews, tenant-owned review history and detail, measured
  step timings, Langfuse trace links, API key management and actual API usage.
  Save source relevance feedback as version-pinned drafts without changing
  retrieval behavior.

- EVR-30: add local workspace accounts, tenant-scoped API keys and measured API
  usage, plus durable tenant-scoped review jobs with retries, idempotent starts,
  saved context answers and restart recovery. Keep provider failures explicit and
  do not put source, prompts or credentials into trace metadata.

- EVR-29: preserve question, answer, finding revision and reviewer decision history
  for resumable RAG reviews. Keep decisions separate from scan findings, require
  a reason to mark a false positive, and reopen a dismissed finding when new
  context changes it. No reviewer action represents assistant approval.

- EVR-28: persist resumable reviews in local SQLite by default, with optional
  PostgreSQL. Bind each review to the active RAG release and source fingerprint,
  retain its retrieved passages, and resume context questions against that same
  release. Keep API keys out of checkpoints and preserve ScanResult.

- EVR-27: run bounded code collection, purpose extraction, legal retrieval,
  review and evidence validation as named LangGraph steps. Keep the current
  review contract, shared repair/deadline limits and privacy-safe stage traces.

- EVR-55: add one workbench Settings page for model parameters, review limits,
  retrieval/build tuning, Langfuse and local evaluation targets. Keep credentials
  in `.env`, pin search settings to new RAG manifests and retain effective
  settings with evaluation reports. Refresh saved cases after evaluation and
  show the exact case count for each report.

- EVR-54: explain the four review steps, sample timings and Langfuse's role in
  the dashboard. Name it AI Act Test Bench, mark it as an internal tool, and
  keep version removal controls compact when blocker details are shown.
- Expand the local demo set to ten runnable examples. Five synthetic smoke cases
  are explicitly marked as drafts and documented as tuned demo data, not legal
  gold or general quality evidence.

- EVR-53: make code testing the primary studio flow with scenario description,
  UTF-8 source upload/paste, 24 KB bounds, exact source-line evidence and retained
  templates. Save code with test fixtures; hide unrelated case/context fields.
  Explain incompatible historical candidates before activation and allow builds
  after bookkeeping-only changes. Remove run comparison, simplify screen labels,
  compact evaluation details, and align upload/removal controls with their rows.
  Keep five distinct runnable sample cases with accepted labels; clear the extra
  cases from local SQLite.

- EVR-52: reuse identical local candidates across Git-only changes, retain build
  provenance and legacy manifests, and add protected, recoverable removal.
  Restore Create candidate and replace page slogans with task instructions.

- Simplify RAG version selection and collapse developer build controls. Remove
  unrelated setup/provenance warnings from that screen. Help popups use the
  browser top layer and dismiss on outside click or Escape.

- Clarify source and active RAG identifiers with keyboard-accessible help popups.
  Explain publisher references, applicability and publication in plain language;
  remove the language badge.

- Keep source exploration read-only. Required-source selection now opens only
  from a test scenario, with explicit add-to-test and return actions.

- Reuse the existing Copilot logo in the dashboard and favicon. Remove internal
  milestone labels from the user interface.

- Add a minimal English M1 presentation with actual screen images, Langfuse
  usage, versioning rationale and extension points.
- Preserve sibling conditions and exceptions inside their numbered official
  source paragraphs, with exact subdivision addresses and offset tests.

Engine 0.5.0, dashboard 0.2.0 and extension 0.4.0 (M1 tooling):

- Add a full-source, domain-independent hybrid retrieval runtime with immutable
  manifests, local CPU embeddings, versioned storage and explicit promotion.
- Add React source exploration, paragraph-level labels, revisioned scenario
  approval, retrieval traces, run comparisons and evaluation exports.
- Add bounded full-corpus review and opt-in metadata-only Langfuse tracing.
  New editor installs use Gemini with explicit cloud consent.
- Add 54 legal development drafts, two technical fixtures, reproducible CI
  reports, PostgreSQL checks and a single-owner Docker Compose runtime.
- Consolidate installation and operations documentation. Retire superseded POC
  plans. Expert-approved gold and live cloud acceptance remain required before
  claiming final M1 quality.

EVR-35: import the full pinned Publications Office source pack (119 articles,
14 annexes, 180 original and 47 amendment recitals), preserving source hashes,
paragraph offsets, origin and binding/explanatory distinctions. Rebuild and
explicit staging download commands reject incomplete or changed source inventories.

M1 tooling foundation (EVR-50):

- Add React + Vite corpus explorer and scenario studio backed by a local FastAPI
  adapter. Inspect exact packaged sources and provenance; save/reopen/export draft
  scenarios persisted in SQLite.
- Label the existing corpus as a legacy subset. No model calls or quality claims.
- Add API integration checks and frontend build to CI. Keep workbench dependencies
  optional; preserve ScanResult and existing adapters.

Engine 0.4.3: concise PR comments and bounded citation repair (YIL-23).

- Show concrete analysis, one question, code/legal links and simple reply commands.
  Keep signed state hidden; remove repetitive summaries and technical boilerplate.
- Explain review failures in plain language and keep acknowledgement receipts brief.
- Retry invalid citation selections once, sharing the existing schema-repair budget
  and deadline. Exact quotations, question sources and code evidence stay validated.
- Prompt version is poc-7. Live Gemini acceptance remains pending.

Engine 0.4.2: simple finding replies and manual demos (YIL-22).

- Reply `/aiact ack` without a reason to record awareness and keep a concern
  open for follow-up. False positives still require a reason; `/aiact reopen`
  returns a concern to pending acknowledgement.
- Resolve finding/revision from signed thread metadata. Changed revisions or
  findings get a new thread; unchanged reviews reuse their thread. Evidence
  outside diff lines uses a file-level review thread. Long commands still work.
- Add independent manual/automatic mode and an Actions Run workflow form with a
  PR-number input. Manual mode preserves explicit rescans and decision handling;
  the existing master switch still disables the entire bot.


Engine 0.4.1: App identity and acknowledgement gate (YIL-18).

- Queue PR reply events sequentially instead of replacing pending replies when
  several decisions arrive together (YIL-20).
- Added a 512 px PNG App avatar below GitHub's 1 MB upload limit.

- Use repository-scoped, short-lived GitHub App tokens in Actions. App credentials
  replace webhook/server setup; no retained database is needed.
- Add a signed current-review snapshot, revision-bound acknowledge/false-positive/
  reopen commands, configurable role authorization and deterministic bot replies.
- Recompute an App-owned acknowledgement check on PR changes and comment
  creation/edit/deletion. Incomplete scans, stale decisions and unverified state
  block it; repository branch rules must require the check to enforce merging.
- Use Linear-provided branch names and issue-linked PR titles for future work.


Engine 0.4.0: stateless GitHub Actions PR review and deferred App adapter.

- Added opt-in Actions review with the built-in GitHub token, Gemini secret,
  trusted-branch configuration, matching-comment updates and authorized rescan.
  No retained database, report artifact, App registration or server is required.
  Human decision tracking and dashboard integration are deferred.

- Added signed-webhook jobs, commit-pinned changed-Python snapshots and PR review
  comments with code evidence, official quotations and configurable role input.
- Added persistent SQLite scan/finding/comment/decision history, scoped
  false-positive and resolved decisions, conservative rescan reconciliation,
  crash recovery and priority-ordered export for a future dashboard.
- Added App registration settings, optional authentication dependencies,
  single-container configuration and local end-to-end tests. No PR code is run.
- Live App installation/HTTPS/model acceptance requires operator credentials.
  Extension 0.3.0 and existing scan result fields are unchanged.



Engine 0.3.2: evidence-oriented question bank.

- Expanded from 32 to 164 authored questions; every stored passage has a scoped
  evidence question and expected artifact. Added detailed training, data-quality,
  oversight, deletion and security challenges, plus a browsable catalogue.
- Separated seven institutional passages into maintenance-only questions and
  bounded per-passage options. Developer selection prefers evidence questions.
- Bank format 1.1 accepts the existing 1.0 format; prompt version is poc-6.
  Extension 0.3.0 and the four-finding result contract remain compatible.



Engine 0.3.1: Gemini request diagnostics and resilience.

- Identify purpose-extraction versus legal-review failures; classify HTTP 400
  diagnostics without echoing provider messages, keys or request content.
- Compact the Gemini review grammar by removing long question/quote enum
  combinations; exact bank questions and citations remain validated locally.
- Retry transient HTTP 500/502/503/504 once within the original request deadline;
  report the HTTP status when the retry fails. No automatic provider fallback.
- Live resolution of the user-reported API rejection remains unverified.


Engine and extension 0.3.0: expanded corpus and multi-topic preview.

- Stored 114 source-verified passages from 15 official pages and 32 questions.
- Added training, parameter documentation and sensitive bias-audit examples.
- Support up to four distinct findings, all questions, matching legal citations
  and multi-finding editor hover. Model output remains subject to manual review.
- Kept lexical retrieval and bounded context; no embeddings or database added.


Engine and extension 0.2.0 (Gemini preview).

- Added opt-in Gemini with a configurable model, shared two-pass pipeline and
  independently validated citations. Ollama remains available without fallback.
- Added masked API-key entry, VS Code secure storage, workspace cloud consent,
  provider health checks and explicit cloud labels. CLI uses GEMINI_API_KEY.
- Added optional provider provenance to results and provider-aware health schema.


- Selected the installed smaller qwen2.5:1.5b model for this repository workspace
  and documented the existing VS Code / CLI model configuration.

- Moved the ten existing question options into a packaged JSON bank with stable
  IDs, topic/missing-fact tags and legal-source references.
- Added bank validation and explicit errors for missing/invalid data, while
  preserving current model selection and the public result contract.

## v0.1.6-poc.4 | 2026-10-29

Presentation-ready POC snapshot. Extension 0.1.6 and engine 0.1.0 are unchanged.

- Included this changelog and version maintenance rules in the tagged source.
- Accepted by the user as a limited end-to-end presentation demo.

Automated CI remains the release gate. Detailed native keyboard/theme/lifecycle
checks were not recorded separately; user acceptance does not create test evidence.

[Release](https://github.com/for-aiur/ai-act-copilot/releases/tag/v0.1.6-poc.4)

## v0.1.6-poc.3 | 2026-10-29

Extension 0.1.6; engine 0.1.0; result schema 1.0; prompt poc-4.

- Explained corpus storage, limited demo scope, two model calls, template
  questions and explicit corpus verification in the main README.
- Simplified setup with uv run and committed the Python dependency lockfile.
- Aligned VS Code workspace and guide with the uv engine environment.
- Added the mascot to the main README and a separate VSIX installation guide.
- Added GitHub Actions tests, wheel/VSIX builds, isolated wheel installation
  checks and downloadable package/checksum artifacts on pushes and PRs.

Validation: 44 engine tests and 20 adapter tests passed on GitHub Actions.
Live local recruitment review passed. Engine behavior is unchanged from the
previous release; native editor acceptance remains a separate manual check.

[Release](https://github.com/for-aiur/ai-act-copilot/releases/tag/v0.1.6-poc.3)
· [Changes](https://github.com/for-aiur/ai-act-copilot/compare/v0.1.5-poc.1...v0.1.6-poc.3)

## v0.1.5-poc.1 | 2026-10-29

Extension 0.1.5; engine 0.1.0; result schema 1.0; prompt poc-4.

- First private POC release with Python CLI, local Ollama inference and a
  six-passage official-source corpus.
- Added bounded source collection, two-pass review, lexical retrieval and exact
  code/citation checks with structured JSON results.
- Added native VS Code diagnostics, hover, reports, context answers, local
  health/service startup, opt-in on-save reviews and Evros Labs branding.
- Packaged the engine wheel and extension VSIX with installation instructions.

Validation: automated engine/adapter checks and five live local fixtures passed.
Full legal coverage and generalization beyond the demo cases are not claimed.

[Release](https://github.com/for-aiur/ai-act-copilot/releases/tag/v0.1.5-poc.1)
