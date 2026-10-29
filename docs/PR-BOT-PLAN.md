# GitHub PR review slice

Current delivery: stateless GitHub Actions, documented in PR-ACTIONS.md.
The App/SQLite implementation below is deferred, not the required deployment.
No decision replay, auto-resolution or dashboard is promised by Actions.

User-authorized next phase after the local POC: GitHub App + persistent SQLite.

Outcome: signed PR webhooks queue bounded scans of changed Python files, publish
source-linked review questions, retain chronological comments and decisions, and
reconcile findings on subsequent complete scans.

Implementation: engine/src/aiact/github_bot/{config,github,store,service,server}.py,
optional App-auth dependency, a deployment example and integration tests. The
existing scan contract/pipeline stays independent of the adapter.

Acceptance checks:

1. Signed webhook -> durable job -> changed-file snapshot -> engine -> PR comment
   and database; reject untrusted paths, signatures and stale PR heads.
2. Role-controlled feedback, comment edits/deletions and duplicate deliveries
   retain history; complete rescans reconcile without closing on failures.
3. Restart preserves history/jobs; dashboard export orders by review priority.

Out of scope: dashboard UI, production hosting provisioning, general-purpose
workflow engine and legal risk classification. SQLite is a single-instance
persistent database, not a workflow artifact. Actual GitHub installation needs
operator-created App credentials and an HTTPS webhook address. The current
VS Code SecretStorage key is not extracted for this service.
