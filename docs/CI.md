# POC CI

GitHub Actions runs `.github/workflows/ci.yml` on pushes, pull requests and
manual dispatch. It uses Ubuntu 24.04, Python 3.12, uv 0.13.6 and Node 24.

The workflow checks:

- Engine JSON contracts, code/citation evidence, bounded input, privacy rules,
  malformed output, missing dependencies and local launcher behavior.
- Adapter result parsing, trust, stale results, concurrent process handling,
  argument paths and health/start behavior using mocked VS Code APIs.
- Wheel and VSIX builds, then an isolated wheel installation with its bundled
  legal corpus. Successful runs upload both packages and SHA256SUMS.txt as a
  seven-day Actions artifact.

Model responses in automated tests are fixtures, not live inference. CI does
not install Ollama or download a model. It does not prove legal interpretation
quality or native editor rendering. The recorded live POC evaluation and manual
VS Code checks remain separate.

Release publication is explicit: choose a passing commit and publish its
packages as a GitHub pre-release. This workflow creates release candidates; it
does not publish to Marketplace or PyPI. No API keys or repository write token
are needed. Action dependencies are pinned to commit IDs.

A future live-model job should run on demand with pinned Ollama/model versions
and a separate time budget. It is deferred until runner performance is measured.
