# Changelog

Published POC snapshots are listed here. Extension and engine versions are
independent; Git tags identify the complete repository snapshot.

## Unreleased

Engine 0.4.1: App identity and acknowledgement gate (YIL-18).

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
