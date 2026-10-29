# AI Act Copilot — POC plan assessment

Date: 29 October 2026, Europe/Berlin.

Implementation follow-up: the user authorized ticket revision and implementation
after this assessment. YIL-5–13 and the POC milestone have now been revised to
reflect the sequence and safeguards below. The original assessment remains here
as rationale; current observed implementation, live results and remaining gates
are recorded in [VERIFICATION.md](VERIFICATION.md).

## Conclusion

The product direction is sound: keep an IDE-independent engine, local analysis, evidence-grounded findings, and a thin VS Code adapter. The main problem today is the horizontal work sequence, which delays the first working demo—not the technology choices. Instead of finishing the entire corpus, provider, retrieval, and context infrastructure first, we should get one recruitment example working end to end.

Sources reviewed: the [Linear project](https://linear.app/yildirim-labs/project/ai-act-copilot-c72174fb02fd/overview), its POC milestone, and the descriptions for YIL-5–YIL-13. All nine issues were in Backlog; the local repository was empty, with no commits. This review does not verify implementation code or performance. The Linear shared agent-context tool was called, but the service returned “Tool not found”; this review is based directly on the project and issue contents.

This file proposes an implementation sequence. The Linear issues and milestone were not changed during this review. In particular, the smaller demo checkpoint proposed here does not count as completion of the full POC acceptance criteria in Linear.

## What to keep and what to simplify

| Area | Decision | Reason |
| --- | --- | --- |
| Python engine + CLI | Keep | Other IDE and CI integrations can consume the same JSON output. |
| Local Ollama | Keep; verify it in the first half hour | Model setup and device latency are critical unknowns and should not be discovered after the UI is built. |
| Two-stage analysis | Keep, with bounds | Separating code evidence extraction from legal review makes both stages easier to inspect; an unbounded agent loop is unnecessary. |
| Model independence | Use one small Protocol | There is only one real adapter today; do not build enterprise provider infrastructure in advance. |
| Legal corpus | Start with a verified subset for the demo | YIL-6 already allows this. A complete legislation parser should not be on today's critical path. |
| Retrieval | Use simple keyword weights + synonyms | Consider BM25 or embeddings only if fixtures reveal a real need. |
| Code scope | Python, prioritizing the selected file | A generic-language fallback increases the burden of reliable line mapping and test coverage. |
| VS Code | Start with a manual command + native report | On-save analysis adds cancellation, stale-result, and performance problems that can wait. |
| Visual design | Use native editor surfaces and clear information hierarchy | A consistent UI does not require a separate dashboard, React app, or design system. |
| Tests/demo | Build them into each slice | Leaving them until the end, as the current sequence suggests, exposes integration risks too late. |

## Important gaps in the current plan

1. **Result semantics:** An empty `findings` array does not distinguish a failed analysis from a successfully completed one. Establish `complete/partial/failed`, coverage, and a separate errors field first.
2. **Citation accuracy:** Producing a real article ID is not enough. Is the quote actually in the corpus? Is the code line correct? Does the quote support the claim? The first two can be checked deterministically; semantic support needs a separate review against demo expectations.
3. **Small-model quality:** The model, tag, installation, and machine performance have not been verified. Schema-constrained output, narrow context, one repair attempt, timeouts, and explicit failures are required.
4. **Missing context:** Source code alone cannot establish purpose, user group, actor role, or the actual deployment setting. “Unknown” and a useful context question should be core behavior.
5. **Demo reliability:** Three positive examples are not enough; include ordinary non-AI code and an ambiguous use case. The goal should not be to produce an alert for every file.
6. **Editor lifecycle:** Debouncing on-save runs, allowing only one active job, discarding stale results, and respecting workspace trust are not covered.
7. **Privacy boundary:** Choosing Ollama alone does not guarantee local operation. Remote endpoints, logs, symlinks, reads outside the scan root, and silent network fallback also need limits.
8. **Visual story:** The Problems panel alone may not explain the value. A short report should make the sequence from evidence to source to next action to question visible.

## Recommended delivery sequence for today

Timeboxes are relative estimates because the remaining work hours are unknown; they are not delivery guarantees. The target is an approximately six-hour window. If less time is available, use the scope cuts below.

| Slice | Timebox | Related issues | Acceptance / exit condition |
| --- | --- | --- | --- |
| 0. Critical preflight | 20 min | YIL-7, YIL-6 | Verify the model endpoint and exact model name; obtain one structured response; confirm an official corpus source is accessible. If the model is unavailable, report the setup blocker immediately. |
| 1. Contract + first fixture | 40 min | YIL-5, YIL-11, start of YIL-13 | Package is installable; schema and example payload are fixed; CLI JSON boundary works. Stubs are used only in tests. |
| 2. One real vertical slice | 100 min | Minimum parts of YIL-6–YIL-11 | Recruitment example → local model → verified corpus subset → cited finding/question → real CLI JSON. Negative control and rejection of a fake citation work. |
| 3. Visible product | 60 min | Minimum part of YIL-12 | A manual VS Code command shows the same result in Problems, hover, and a readable report; source-line and official-source links work. |
| 4. Reliability + coverage | 60 min | YIL-8, YIL-10, YIL-13 | Other two domains, ambiguous example, missing model/cache, malformed JSON, timeout, and coverage are checked. |
| 5. Full-milestone finishing work | 60 min | YIL-6, YIL-12, YIL-13 | Safe manual update, opt-in on-save, VSIX, offline rehearsal, and README; demo can be reproduced from setup. |
| 6. Presentation rehearsal | 20 min | YIL-13 | Run the three-minute story twice; note actual latencies; make remaining limitations visible. |

**Dependency logic:** contract → one real scan → editor → broader coverage and hardening. Begin YIL-13 fixtures and checks in the first slice. Add YIL-12 on-save work after the real scan and manual command. Completing the minimum part of an issue does not mean the whole issue is complete.

### If time gets tight

- First cut generic-language fallback, automatic README context, broad repository scans, and rich visuals.
- Then defer on-save and VSIX packaging until after the demo; demo with a manual command. In that case, the full Linear POC milestone is not complete.
- If needed, present one excellent end-to-end scenario instead of three domains, and state the scope clearly.
- Use a verified subset from an official source instead of a full parser. Do not present an incomplete or fabricated corpus as full legal coverage; do not close the full milestone if the update flow is unfinished.
- If the local model does not work, do not present a mock result as live AI analysis. A recorded example is only a clearly labeled presentation fallback; the live-analysis goal remains open.
- Do not cut evidence validation, the distinction between errors and successful results, the privacy boundary, or accurate source-line references.

## High-impact improvements with little effort

| Opportunity | Demo impact | When |
| --- | --- | --- |
| Review an example file with one command and jump to the source line | Shows product value in the first minute | Today |
| One-sentence summary at the top of the report, with fewer than three strong findings | Helps stakeholders know what to inspect | Today |
| Code evidence and official quotation on the same screen | Makes the difference from a generic chatbot visible | Today |
| Three ready examples + a negative control | Makes the demo repeatable and selective | Today |
| “Analysis coverage / local model / corpus version” | Shows the basis for trust | Today |
| A doctor command that explains how to fix a missing model/cache | Reduces first-run friction | Today |
| Answer the user's context question and rerun the scan | Strengthens the copilot experience | After the core path passes; carry the answer as explicit input |
| Show a cached result again for identical input | Improves perceived speed | Later; include code, context, model, prompt, and corpus versions in the cache key |
| Save the Markdown report externally | Makes it shareable after a meeting | Small addition if a preview already exists |

## Three-minute stakeholder demo

1. Open the recruitment example: “How does this code use AI, and what review question does it raise?”
2. Start a manual review; show the progress and local-analysis status.
3. Open one strong finding; explain the correct code line, official quotation, and qualified reasoning together.
4. Show the one open context question and the suggested engineering next step. Do not imply that answering it and rerunning has been implemented unless it has.
5. Show an ordinary code example; preserve the distinction between “no finding in this scope” and “compliant.”

In a live network-off test, scanning should work locally; opening the official source in a browser may require a network connection and should be evaluated separately. Warm up the model before the demo and measure both cold and warm durations. The initial target is a warm scan under 30 seconds on a small example; this has not yet been measured. If it exceeds the target, first narrow the context/output and check the number of calls, then consider a different model.

## Modularity and the later roadmap

Directories and function boundaries are enough for modularity. A general plugin system, service split, or abstract repository layer is unnecessary. The shared result schema, provider Protocol, and corpus manifest are the extension points. A new idea should first explain which of these boundaries it uses.

- **First step after the POC:** fixture evaluation set, real-device latency, user feedback, and setup reliability. Do not add multiple integrations before validating product value.
- **Public Release:** reproducible packaging, version policy, privacy explanation, PyPI/Marketplace, and a short demo. A website belongs at this stage, not on today's critical path.
- **Enterprise:** add one provider in response to a real customer need, with credential handling, data-transfer permission, and capability fit. Do not implement every provider at once.
- **Regulatory intelligence:** establish corpus version/provenance now; add automatic change tracking and impact analysis for past reviews later. Do not put changes to binding law, guidance, and proposals in the same category.

## Technical references and limits of this review

- [Ollama structured outputs](https://ollama.com/blog/structured-outputs): JSON Schema constrained output is available; independent application validation is still required.
- [VS Code webview UX guidance](https://code.visualstudio.com/api/ux-guidelines/webviews): webviews are appropriate when native surfaces are insufficient; this supports starting with native UI.
- This assessment is not legal advice and is not a legal corpus. An implementation task adding legal content must verify the current official text separately.

This change adds only a plan and agent instructions. No implementation tests, live-model benchmark, offline-operation test, or VSIX build has been run.
