# Workbench operations

Use the [root setup guide](../README.md) for the supported Docker/native commands.
This page covers data, evaluation and version operations.

## Local data

Native defaults: `.aiact-workbench/aiact.db`, `models/`, `qdrant/`,
`embedding-cache/` and immutable `releases/<sha256>/` under the same directory.
Compose uses `/data` in its named volume. Avoid overriding `DATABASE_URL` with a
native relative path inside Compose; leave the default unless selecting another
backend intentionally. Changing a database URL does not migrate existing data.

Explicitly saving scenarios, retrieval runs or reviews retains entered context
and result evidence locally. Keep the database and backups private. Stop the
owner before copying SQLite/Qdrant files, or use a consistent SQLite backup.
Do not run another process against the same Qdrant Local path.

## Build and activate

```sh
aiact rag build --download-model
aiact rag status
aiact rag activate --release RELEASE_ID --allow-unapproved
aiact rag rollback --allow-unapproved
```

Run commands through `uv run --project engine --extra rag` when not in an activated
environment. `--download-model` is an explicit network setup operation. Omit it
for cache-only builds. `--lexical-only` creates a labelled baseline, not a hybrid
release. UI activation is for local tooling tests and does not establish quality.

A code/model/source mismatch requires a new candidate. Old bundles and runs stay
available. On restart, bootstrap does not replace an existing active release.

## Cases and evaluation

The initial legal set contains 54 **model-authored development drafts** across
18 subject areas. They are candidate questions for review, not expert gold.
No protected holdout is supplied. The small technical domain has two separately
reviewed engineering fixtures.

For a useful case, supply intended use, role, deployment and constraints. Mark
required/relevant/irrelevant/uncertain sources with reasons. Add missing sources
from the pinned library; never invent a reference. Save the draft, then enter the
approving reviewer and explicitly approve a new immutable revision. The older
revision remains in history. Relevance labels are distinct from finding ack/FP.

Export cases as JSON for a reviewed Git change. Approved release gold belongs in
`evaluation/gold/ai-act.json` as `{"cases": [GoldenCase, ...]}`. It must pin the
source snapshot, label revisions, author/reviewer, area and split. A holdout must
be sealed before tuning and kept out of development evaluation. Do not turn
model-authored labels into expert-approved gold without qualified review.

```sh
aiact rag seed-drafts
aiact rag eval --output .aiact-results/evaluation.json
aiact rag eval --dataset evaluation/gold/ai-act.json --include-holdout --require-quality
```

Seeding never overwrites existing case IDs/revisions. Changed source snapshots
require reviewed case revisions. Metrics distinguish expected sources from actual
hits and report required-source recall, labelled precision, MRR/nDCG, misses,
false positives and uncertainty. UI evaluation excludes holdout by default.

## Official updates

```sh
aiact corpus check
aiact corpus sync --staging
aiact corpus diff --before OLD_RELEASE --after NEW_RELEASE
aiact corpus promote --after NEW_RELEASE --approval-note "Reviewed source and evaluation evidence"
```

Check queries the official Publications Office metadata. Sync downloads only the
pinned source pack into a new staging directory and revalidates it. Changed or
incomplete files fail without replacing the active corpus. A new consolidated
edition needs a reviewed source manifest/parser revision; the tool does not
silently import arbitrary future law. Diffs include document/chunk changes and
affected recorded citations. Promotion requires the final expert-gold gate.

## Langfuse

Set `LANGFUSE_ENABLED=true`, the public/secret keys and `LANGFUSE_PROJECT_ID` in
private runtime configuration. The fixed EU endpoint receives OTLP spans with
run/model/source identities, stage durations and available token counts. Raw
code, prompts, answers, keys and reviewer text are excluded. Disabled or failed
export does not change scan results. The review screen links to a trace when a
project ID is configured. No cost estimate is invented when pricing is unknown.

## Troubleshooting

- **Docker cannot connect:** start a compatible Docker engine before Compose.
- **Initial setup is slow:** the CPU is embedding the full source pack. Keep the
  setup running and inspect its terminal; no latency guarantee is claimed.
- **No active build:** build a candidate in RAG versions, then explicitly select it.
- **Runtime implementation changed:** restart the API, build a new candidate and
  select it. Existing artifacts are intentionally not rewritten.
- **Missing model cache:** run the explicit download setup. Retrieval never fetches
  a model implicitly.
- **Gemini key missing:** add it to private `.env` and restart the API. VS Code
  keys live separately in SecretStorage.
- **Quality gate blocked:** review/approve legal gold and run the sealed holdout
  and critical suites. A passing software build cannot replace this work.

For older consumers, `/api/corpus` and `/api/drafts` retain their initial legacy
subset/draft behavior. The current workbench uses `/api/rag/*` endpoints.
