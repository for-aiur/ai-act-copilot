# M1 short user guide

[Download the presentation](AI-Act-Copilot-M1.pptx). Twelve slides with editable text and detailed speaker notes. Actual screen examples use the technical-document domain, which shares the same tools as the AI Act domain.

Langfuse setup and usage are explained. Live Langfuse verification remains pending configured credentials.

## 1. AI Act Copilot

Explore the sources. Describe the intended use.
Improve the review together.

<details><summary>Speaker notes</summary>

M1 user guide for internal teams and product demonstrations. The tool supports engineering review and does not issue a compliance certificate.

</details>

## 2. What the system does

Finds official passages for a specific use case.
Shows why those sources appeared.
Turns human feedback into repeatable tests.

<details><summary>Speaker notes</summary>

The runtime combines a complete pinned official source pack, local retrieval and optional Python review. Complete source coverage does not establish review accuracy.

</details>

## 3. The basic workflow

1  Choose a source collection
2  Describe the use and its context
3  Inspect the selected passages
4  Mark gaps and save a test

<details><summary>Speaker notes</summary>

The main screens are Source explorer, Retrieval studio and Evaluation cases. Code review is optional. Gemini requires separate explicit consent before transferring selected source and context.

</details>

## 4. The source screen

Source explorer

Search the official text.
Open a passage and its source.
Add a source that must appear.

<details><summary>Speaker notes</summary>

Sources have pinned versions and checksums. Conditional application dates remain qualified. The Target passage selector supports paragraph-level expectations. Screen examples use the small technical-document domain, which shares the same interface with AI Act sources.

</details>

## 5. The search and review screen

Retrieval studio

What does the system do?
Who uses it, and where?
Inspect the selected sources.
Optionally review Python code.

<details><summary>Speaker notes</summary>

Retrieval combines FTS/BM25, CPU FastEmbed and Qdrant Local. RRF merges candidates before reranking and bounded related-passage expansion. Two bounded model passes extract purpose and review retrieved evidence. Expand the review details to inspect purpose, search intents, candidates and the exact passages sent to the model.

</details>

## 6. The test and feedback screen

Evaluation cases

Mark required or irrelevant sources.
Explain your labels and save a draft.
Approve a revision and rerun the test.

<details><summary>Speaker notes</summary>

Approval creates an immutable revision and retains the earlier draft. JSON exports support review through Git. Conflicting approved labels for the same exact context are rejected. Run an individual case or the development suite. Reports include Recall@5/10, labelled precision, MRR, nDCG and missed sources. Local approval records attribution, not professional qualifications or legal correctness.

</details>

## 7. The comparison screen

Compare runs

Open two runs side by side.
Compare their context and sources.
See what appeared or disappeared.

<details><summary>Speaker notes</summary>

Each run records its context fingerprint and RAG release. Changing context clears the displayed old result and labels. A source can have different relevance under a different intended use or deployment.

</details>

## 8. Source and search versions

RAG versions

Which sources and settings produced this result?
Build and select a new version.
Return to the previous version if needed.

<details><summary>Speaker notes</summary>

Versioning matters because official text, paragraph boundaries, embedding models and retrieval logic can change. Every build has a content-addressed manifest and verified source/vector files. Application version, source snapshot, RAG release and test revision are separate. Local activation does not pass the final quality gate.

</details>

## 9. Following a review in Langfuse

How long did a review take? Where did it fail?

Follow collection, understanding, search, review and validation.
Inspect usage when the provider supplies it.
Open the trace from the review result.

<details><summary>Speaker notes</summary>

Configure LANGFUSE_ENABLED=true, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_PROJECT_ID in private .env configuration. Restart the API, run an authorized review and choose Open metadata-only Langfuse trace. Export uses the fixed EU endpoint. Raw code, prompts, answers and keys are excluded. An unavailable tracing service does not change the review outcome. Live Langfuse verification remains pending because credentials are not configured. No live Langfuse screenshot is claimed.

</details>

## 10. Using Langfuse

1  Enable the connection in your private .env
2  Run a review with explicit consent
3  Open its Langfuse trace link
4  Inspect the steps, duration and errors

<details><summary>Speaker notes</summary>

Keep credentials out of the browser, reports and Git. The tool exports only permitted metadata and actual available usage. M1 also includes 360 official documents, SQLite persistence, PostgreSQL parity tests, explicit update checks, staging/diffs and guarded promotion. Actual Compose startup, evaluation and restart were verified in CI. A new legal edition requires reviewed source and parser policy.

</details>

## 11. How the platform can grow

A new document domain can use the same screens.
A different model can keep the same review flow.
Larger installations can change the storage layer.

<details><summary>Speaker notes</summary>

A second technical-document domain already uses the same API, labels and evaluation path. Python modules separate sources, contracts, storage, embeddings, retrieval, review and evaluation. React + Vite provides the interface. Gemini and Ollama are explicit providers without automatic fallback. Changing DATABASE_URL does not migrate data. Qdrant Local has one owning process. Multi-user product workflows and cloud deployment belong to later milestones.

</details>

## 12. First use and remaining acceptance

Start: docker compose up --build
Open: 127.0.0.1:8000
Try source browsing and retrieval first.

Live checks and expert test approval remain open.

<details><summary>Speaker notes</summary>

First setup downloads the local embedding model. Browsing, retrieval and annotation need no Gemini key. Gemini review is optional and requires explicit source-transfer consent. Five runnable sample cases have labels accepted for local testing. They are not a representative expert-reviewed gold set. Final M1 acceptance requires 50+ expert-approved cases, a sealed holdout and a separate critical suite, plus live model and tracing verification. See README.md and docs/M1-STATUS.md.

</details>
