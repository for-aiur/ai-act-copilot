# PR review with GitHub Actions

PR event -> changed Python blobs -> existing two-pass engine -> PR questions and
source evidence. Only trusted default-branch engine/configuration runs. PR code
is downloaded through GitHub's API as data, never installed or executed.

## Setup

1. Merge the engine, `bot/actions.toml` and `.github/workflows/pr-review.yml`
   into the repository's default branch.
2. In **Settings > Secrets and variables > Actions**, add the repository secret
   `GEMINI_API_KEY`. The editor's saved key is separate.
3. Edit `bot/actions.toml`: repository allowlist, model and optional GitHub logins
   for privacy officer, model owner and engineering. Role routing uses the App
   adapter's existing citation-prefix rules and can be overridden with `[routing]`.
4. Set the Actions repository variable `AIACT_PR_REVIEW_ENABLED` to `true`.
   Enabling this consents to sending selected changed code and retrieved legal
   passages to Gemini using your API quota. Fork PRs remain disabled.
5. Open or update an internal PR changing a Python file. Inspect the **AI Act PR
   review** workflow and its PR comments. A writer, maintainer, admin or configured
   role holder can post `/aiact rescan` as a PR conversation comment.

No App registration, webhook, external server or AWS account is needed. Comments
are authored by `github-actions[bot]`; a custom App avatar requires the deferred
GitHub App setup. Repository/organization policy must permit this workflow and
the declared token permissions. Actions and Gemini usage remain subject to their
own quotas and billing.

## State and limits

- No database survives the job. Scratch SQLite reuses the tested adapter and is
  deleted on normal exit; the hosted runner is discarded after the job. It is
  never uploaded as an artifact, cached or committed.
- PR comments remain on GitHub. Stable finding markers let subsequent jobs
  update matching comments rather than posting the same finding repeatedly.
  Deleted comments can be recreated; changed finding identities can create new
  threads. Summaries are per commit/configuration, not a dashboard history.
- Replies are for human discussion only. Evidence ingestion, false-positive/
  resolved commands, decision replay and automatic closure are deferred. Old
  comments can remain after a finding disappears; use their pinned commit links.
- Reviews retain existing scan budgets and legal coverage limits. Failed or
  partial reviews post their summary and fail the workflow; findings alone do
  not fail it. Zero findings is not a compliance certificate.
- Jobs serialize per PR. Stale head/base checks suppress results for outdated
  revisions. No model credentials are exposed to PR code.

Disable by setting `AIACT_PR_REVIEW_ENABLED=false`. The existing local scanner
and VS Code extension are independent of this switch.
