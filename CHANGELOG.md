# Changelog

Published POC snapshots are listed here. Extension and engine versions are
independent; Git tags identify the complete repository snapshot.

## Unreleased

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
