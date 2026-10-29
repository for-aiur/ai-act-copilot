# POC verification record

29 October 2026, Europe/Berlin. This records observed checks, not certification.

## Environment

- MacBookPro16,2; Intel i5-1038NG7 at 2.00 GHz; 16 GB; macOS 15.7.7; CPU inference.
- Python 3.12.14 in `.venv`; editable engine install completed.
- Node 24.22.1 used for building; system Node 20.12.2 is too old for current VSIX tool dependencies.
- Ollama 0.40.13 downloaded from the official release; `.tools/ollama` is gitignored.
- Chosen local model: `qwen2.5:3b`. Existing `phi3:mini` timed out in full reviews.
  Downloaded `qwen2.5:1.5b` returned unreliable legal reasoning and was not selected.
- Local service listens on 127.0.0.1:11434. Restarted with `OLLAMA_NO_CLOUD=1`,
  one loaded model and raw request logging disabled. The offline rehearsal also
  restricts the server and engine to loopback via macOS sandbox profiles.

## Observed checks

| Check | Observed result |
| --- | --- |
| `python -m pip install -e './engine[dev]'` | Passed in `.venv` |
| `python -m pytest engine/tests` | 33 passed |
| Extension `npm test` | 9 passed; includes direct activation/lifecycle tests with mocked VS Code APIs |
| Extension `npm run compile` | Passed |
| Extension `npm run package` | Passed; local VSIX produced |
| `code --install-extension …vsix` | Passed; installed `yildirim-labs.ai-act-copilot@0.1.0` confirmed |
| Packaging dependency audit after patch override | 0 known vulnerabilities reported |
| `aiact doctor` | Passed with the default qwen2.5:3b model and corpus; 1.5B also checked during setup |
| Live missing-model scan | Failed with `model_unavailable` and schema-valid JSON, exit 1 |
| Live missing-corpus scan | Failed with `corpus_unavailable` and schema-valid JSON, exit 1 |
| `aiact update --corpus /tmp/aiact-verified-cache.json` | Passed against all three official Commission pages |
| Cache corruption/download-change tests | Passed; existing cache preserved |
| Non-loopback configuration | Rejected with structured result and exit 2 |
| External socket from loopback sandbox | Denied with EPERM (1) |

Tests cover clean JSON stdout and usage errors; source/quote/range/citation
validation; hidden, ignored, symlink and bounded inputs; parse errors; malformed
model output, one repair and timeouts; no scanned-code execution or official
network fetch from scans; untrusted workspace refusal, one active process,
argument arrays with spaced paths, stale versions/content, and escaped reports.

## Live evaluation

The final fixture rehearsal is recorded below. It uses real
local inference, two bounded passes per file and explicit result JSON under
`.aiact-results/` (gitignored, contains source evidence). The evaluator checks
expected domain citation, a context question, completed status and the negative
control; semantic support still requires reading the result.

Earlier runs failed despite valid quotations: unrelated provisions, incorrect
classification, ordinary arithmetic warnings and omitted context questions.
Those failures led to narrower domain retrieval, quotation choices constrained
by schema and independently checked, explicit AI-use extraction, conservative
rejection of misleading legal classifications, and required questions for
unresolved model use. There is no production stub or recorded-result mode.

Final `poc-4` rehearsal: **5/5 passed**, all scans complete with no operational errors under loopback-only networking. Recruitment 33,883 ms; biometrics 30,643 ms; chatbot 37,062 ms; ordinary arithmetic 44,547 ms; ambiguous model call 35,452 ms. Positive domains cited Annex III 4(a), Annex III 1(a), and Article 50(1) respectively. The ambiguous case cited Article 6(3) only to explain why intended-use context is needed, without classifying the system. Source/legal evidence, reviewed explanations and specific questions were read after the run. The negative control had zero findings. The previous `poc-3` run passed all five mechanical fixture checks (26.4, 67.0, 28.8, 29.4 and 44.2 seconds) but semantic reading found a biometric exception misstatement and cut-off chatbot prose. Those results were not accepted as semantic completion. Initial missing-context explanations and titles are now constrained to reviewed domain wording; question choices are reviewed prompts, while fact extraction, evidence selection, priority and next action use the real local model. This POC demonstrates grounded triage/context questions, not unrestricted legal reasoning.

## Actual CLI cold/warm rehearsal

The default command `.venv/bin/aiact scan examples/recruitment/ranker.py --json` was run through subprocesses under the same loopback-only sandbox. After explicitly unloading the model, the cold run completed with exit 0, one finding, and 61,172 ms. The immediate warm run completed with exit 0, one finding, and 26,164 ms. These are observations on this machine, not latency guarantees. Captured complete and failed payloads are checked in under `schemas/`; the adapter consumes the complete payload unchanged in a cross-language contract test.

## Manual acceptance still required

The native UI automation tool timed out; no visual/editor interaction acceptance
is claimed. The installed extension and root workspace are ready for the user:

1. Reload VS Code, open the repository root and trust it.
2. Review recruitment; inspect Problems, hover and the report.
3. Reveal the source and open the official URL; check the exact code/legal quote.
4. Add explicit context and rerun; edit during a scan and confirm stale results
   disappear; cancel; then enable opt-in on-save and check debouncing.
5. Check native light/dark themes and keyboard navigation.

A successful build and mocked lifecycle test do not prove these interactions.
The full POC milestone remains open until acceptance gates are satisfied.

## Limits

- Small local models can miss or misinterpret legal relevance. Mechanical
  quotation validity and fixture success are not general semantic guarantees.
- Six reviewed Commission-reproduced passages, not complete AI Act coverage.
  EUR-Lex was inaccessible; no independent applicability dates are asserted.
- Refresh verifies existing reviewed passages; changed/new law needs manual review.
- Python only, bounded files. Open the repository root in VS Code for matching paths.
- No public release, deployment, Marketplace publishing or distribution license.
- Warm scans have exceeded the proposed 30-second target; no sub-30-second claim.

## Manual test follow-up: service unavailable

The user observed `model_unavailable` from the installed VS Code adapter. A fresh `aiact doctor` confirmed that the Ollama endpoint was not running, while the bundled corpus was readable. Started the existing loopback-only helper in a dedicated macOS Terminal window using Terminal AppleScript; `aiact doctor` then passed with qwen2.5:3b. The service is not an installed login/background service: keep that Terminal open. README and connection-error recovery now explicitly name `sh scripts/start-local-model.sh` rather than assuming `ollama` is on PATH. Provider tests: 9 passed.

Same-file live recovery scan: exit 0, status complete, one finding, 41325 ms, no operational errors.

## Extension health/start feature (0.1.1)

Added the native Activity Bar Local setup view with independent CLI, Ollama, model and corpus checks. `aiact doctor --json` is a separate additive health contract (`schemas/health.schema.json`); ScanResult remains unchanged. The first manual review offers service start when Ollama is stopped, and continues after setup is ready. Activation only checks health; on-save never starts a service or prompts. Starting uses a visible VS Code integrated terminal with executable/argument arrays, loopback host and cloud disabled. An already healthy service is reused. No installations/downloads or OS login service are added.

Engine suite: 38 passed. Extension suite: 17 passed. Extension checks cover stopped service with available corpus, missing model, first-review start, concurrent start deduplication, untrusted workspaces, automatic on-save refusal to start, configuration staleness, malformed health, invalid launch configuration, plus prior scan/lifecycle checks. Real `doctor --json` reports all four checks ready. A live CLI-to-view-data rehearsal under loopback-only networking also passed (VS Code UI APIs mocked, CLI/backend real). Native rendering and integrated-terminal interaction still require the user's manual VS Code check after Reload Window.

## Icon and plain-language introduction (0.1.2)

Added an original robot-with-legal-wig PNG extension icon and a separately authored monochrome SVG Activity Bar companion. The built-in imagegen tool produced the PNG; its original transparent alpha was preserved and the final file is in the project. Validated square 1254×1254 RGBA, alpha range 0–255, and SVG XML. The prompt is recorded in docs/ICON-PROMPT.md. No image generation is added to product scans.

The extension README now explains the tool and the AI Act for a beginner, gives a recruitment example, shows first steps and result meanings, states current limits, then puts clearly labelled future goals last. The short legal introduction links to the current official European Commission overview; no corpus/legal applicability metadata was changed. New native sidebar introduction/roadmap actions open the packaged local README through the built-in Markdown preview. Packaging keeps local image links intact and handles the VSIX's lowercase readme filename.

Extension tests: 18 passed, including introduction/roadmap routing without a scan or service start. Compile and VSIX packaging passed. PNG, SVG, manifest icon references, packaged intro and compiled bytes verified. Native image rendering and Markdown scrolling after Reload Window remain manual visual checks. Engine source was unchanged; no broad inference or engine reruns were needed for this slice.

## Evros Labs publisher identity (0.1.3)

Renamed the local VSIX publisher to evros-labs and added the visible Evros Labs credit to the extension introduction, health-panel introduction and root README. Product name, command IDs, configuration keys and engine contract remain AI Act Copilot/aiact. Version/lockfile updated to 0.1.3. TypeScript compile and VSIX packaging passed; both package.json and VSIX Identity Publisher were checked. Installed evros-labs.ai-act-copilot@0.1.3, removed the old yildirim-labs.ai-act-copilot installation to prevent duplicate commands/views, then verified the extension list contains only the new identity. Existing historical records/Linear workspace URLs are retained. Native branding appearance is checked after Developer: Reload Window. This is a local publisher ID; no Marketplace publication or publisher-account registration was performed.

## Broken README image follow-up (0.1.4)

The user observed image alt text in the introduction instead of the mascot. The PNG was present in both the 0.1.3 VSIX and installed extension; package presence had not verified rendering. Removed the redundant inline relative image from the shared README, keeping the standard manifest PNG extension icon and monochrome Activity Bar icon. This avoids a broken relative image in the extension description without remote image hosting or changes to preview security. Official VS Code publishing guidance requires README image URLs to resolve to HTTPS: https://code.visualstudio.com/api/working-with-extensions/publishing-extension .

Compile/package passed. Verified the 0.1.4 packaged README has no inline image/alt-text placeholder, while the manifest icon's PNG bytes remain intact and Evros Labs/intro/roadmap content is preserved. Native rendering is checked after Reload Window and reopening the introduction. No engine or inference changes; no broad engine reruns.

## POC pre-release v0.1.5-poc.1

Extension 0.1.5; engine 0.1.0; private GitHub distribution. Rewrote the root setup
guide for a fresh clone or release download and added all six VS Code settings,
GUI/JSON examples, explicit model setup, CLI vs Ollama executable distinction,
custom local endpoints and opt-in on-save behavior. Corrected explicit Ollama
binary forwarding, helper fallback to system Ollama, custom loopback bind ports
and workspace substitution in scan corpus paths. No ScanResult contract change.

Observed release checks:

- `.venv/bin/python -m pytest engine/tests`: **44 passed**. Launcher checks use
  temporary fake binaries, including a spaced path, bundle/system fallback,
  missing binary and remote-bind rejection. macOS sandbox launcher tests require
  running outside the agent's outer sandbox; that restriction was observed and
  the successful rerun used the normal loopback profile without weakening it.
- Extension `npm test` with Node 24: **20 passed**, including explicit Ollama
  path/custom port forwarding and workspace corpus substitution.
- Extension compile/package passed; VSIX manifest/version, packaged settings
  guide and icon presence checked. Installed version verified as
  `evros-labs.ai-act-copilot@0.1.5`.
- `pip wheel --no-deps ./engine --wheel-dir dist/release` passed; verified bundled
  corpus and doctor module in the wheel. Release assets include VSIX, wheel and
  SHA256SUMS.txt; build outputs, local models and saved results are gitignored.
- Real `aiact doctor --json`: engine, corpus, Ollama and model ready.
- Real recruitment scan under `scripts/loopback-only.sb`: exit 0, complete, one
  finding, no operational errors; **68,080 ms**. This is an observed run, not a
  speed guarantee. Earlier five-case rehearsal remains recorded above.
- Staged source whitespace check passed; credential-pattern scan found no
  matching key/token/private-key material. This is a bounded check, not a
  guarantee that all possible sensitive content can be detected.

Native editor keyboard/theme/lifecycle acceptance remains the user's next task.
This pre-release does not mark the full Linear POC milestone complete.

## Final POC snapshot v0.1.6-poc.3

Documentation, setup and packaging update; engine/provider/corpus and extension
runtime source are unchanged. Main README now explains corpus size/storage,
the two model calls, curated question limits and explicit update behavior.
Added a separate VSIX installation section. uv setup uses engine/.venv; the
workspace setting and packaged extension guide point to that executable.
engine/uv.lock records the resolved project dependencies from public PyPI.

Observed checks:

- uv 0.13.6 prepared a fresh engine/.venv and installed the editable engine.
  doctor --json reported all four checks ready with qwen2.5:3b.
- Real scan from the repository root using uv run --offline --project engine
  --python 3.12, under loopback-only networking: exit 0, complete, one finding,
  no operational errors, 48,407 ms. This also verified relative input paths.
- Extension compile and package passed. Verified version/publisher, updated
  guide and identical compiled runtime bytes compared with 0.1.5.
- Installed evros-labs.ai-act-copilot@0.1.6 and confirmed the version through
  the VS Code CLI. Assets include that VSIX and the unchanged 0.1.0 wheel.
- Source whitespace check and release asset SHA-256 checks passed.

No broad engine/adapter suite rerun for documentation/configuration changes.
Earlier 44/20 passing results remain recorded above. Native editor acceptance
is still separate; this release is the final limited POC snapshot, not a claim
that every full-milestone manual gate passed.

## CI addition for final snapshot

Added a read-only, pinned-action GitHub workflow for pushes, pull requests and
manual runs. It installs locked Python development dependencies, runs the engine
and adapter suites, builds wheel/VSIX, smoke-checks a wheel installation outside
the checkout, and uploads packages/checksums as seven-day artifacts. No Ollama
installation or live model download is part of CI. Release publishing remains
explicit. Local command rehearsal: 44 engine tests and 20 adapter tests passed.

## User presentation acceptance

29 October 2026: the user accepted the limited end-to-end POC as ready for
presentation and requested closure for now. v0.1.6-poc.4 includes the changelog
and versioning rules in the tagged source. Runtime versions are unchanged.
This supersedes the earlier hold on POC handoff on the basis of user acceptance;
it does not assert unobserved native keyboard/theme/lifecycle test results.
Broader product validation remains future work.
