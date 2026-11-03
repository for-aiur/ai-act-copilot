# Local retrieval workbench

M1 tooling foundation, EVR-50. React + Vite + TypeScript frontend and a separate
FastAPI adapter. No hosted deployment, inference calls or automatic legal fetches.
The packaged 114-passage corpus is explicitly a legacy subset, not the full act.

## Run locally

Use Python 3.11+ and Node 22.12+ (Node 24 recommended). From the repository root:

```sh
uv sync --project engine --extra workbench
uv run --project engine --extra workbench python -m uvicorn aiact.workbench.api:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
npm ci --prefix dashboard
npm run dev --prefix dashboard
```

Open http://127.0.0.1:5173. Stop each process with Ctrl+C. Vite forwards same-origin
`/api` requests to Python. Set `AIACT_API_TARGET` in the frontend process to use a
different local API address. Do not put secrets in Vite environment variables.
No browser API URL is embedded in the frontend bundle.

For an existing pip environment, the equivalent backend setup is
`python -m pip install -e './engine[workbench]'`, followed by the same
`python -m uvicorn ...` command. Development dependencies are not required to run.

## Available workflow

- Search the packaged corpus by reference or text; filter articles/annexes.
- Inspect exact source text, canonical URL, scope limits and snapshot checksum.
- Attach sources to a scenario, enter intended use and deployment context.
- Save a draft, reopen it and export JSON. Saving an opened draft creates a new
  snapshot; editing/replacing existing rows is not implemented.

Drafts persist in `.aiact-workbench/drafts.sqlite3`, gitignored. Override the path
with `AIACT_WORKBENCH_DB` in the Python process. Explicitly saving a scenario
persists the entered text and references on this machine. The workbench does not
read source files or reuse source snippets from scans. List displays the newest
100 drafts. Input lengths and source references are validated; the corpus checksum
is pinned on save. References express investigation intent, not relevance labels.

The API binds to loopback in the documented command. Host validation and
same-origin write checks protect local browser use; it has no public authentication.
Keep Vite and API on loopback. Do not expose this development service publicly.
No CORS wildcard, external fonts, analytics or model SDKs are used.

## Checks

```sh
uv run --project engine --extra dev --extra workbench --extra workbench-test python -m pytest engine/tests/test_workbench.py
npm run build --prefix dashboard
```

CI installs the workbench extras and builds the frontend. Plain engine installs
keep workbench dependencies optional.

Observed on 3 November 2026: Node 24.22.2 production build passed; locked uv
environment sync passed; engine suite passed 177 tests (one upstream TestClient
deprecation warning). The initial restricted-shell suite failed on local socket
and macOS sandbox permissions and missing bot extras; the complete configured
suite passed with those environment constraints resolved. Browser checks passed
for searching Annex III 4(a), adding its source, saving an applicant-ranking draft
and reopening the saved context/reference. API proxy health returned ready.
Responsive DOM check at 390px reported no horizontal overflow. No live model or
Docker acceptance is claimed.

## Next slices

Full official source ingestion (EVR-35), domain contracts (EVR-45), central runtime
configuration (EVR-33), hybrid retrieval, draft annotations/approval and workbench
stage traces (EVR-42). Compose is EVR-46. This foundation does not implement those
features or satisfy M1's final expert-gold quality gate. No retrieval scores,
evaluation results or model performance are fabricated. Model-authored cases may
be imported in a later slice as drafts; expert approval remains distinct.
