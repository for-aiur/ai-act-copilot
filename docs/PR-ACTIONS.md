# PR review with our GitHub App

Actions runs the scanner; our App writes findings, replies and the merge check.
No server, webhook or retained database is needed. [Setup](GITHUB-APP.md).

## Review and reply

1. An internal PR opens or changes. The bot scans changed Python files and posts
   code evidence, official sources, a question and requested reviewer roles.
2. Reply in the finding thread with context. The bot confirms receipt. This
   does not count as a decision and is not sent to the model.
3. Copy a command from each finding, replacing `<reason>`:

   ```text
   /aiact acknowledge FINDING_ID REVIEW_TOKEN Reviewed the human oversight process.
   /aiact false-positive FINDING_ID REVIEW_TOKEN This is a synthetic fixture.
   /aiact reopen FINDING_ID REVIEW_TOKEN The evidence needs another review.
   ```

   `ack` and `fp` are aliases. Commands work in an inline reply or the PR
   conversation. The ID/token must match the current finding and revision.
4. The bot accepts/rejects the command and updates **AI Act Copilot /
   acknowledgements**. It passes only after a complete current review and an
   authorized acknowledge/false-positive decision for every finding. Partial or
   failed scans cannot pass, even with zero findings.

Assigned role holders or repository maintainers/admins may decide. When no users
are assigned to a finding's roles, repository writers may decide. Configure
`[roles]` and optional citation-prefix `[routing]` in `bot/actions.toml`.
Acknowledgement records human review, not verified compliance or AI approval.

Writers, maintainers/admins and configured role holders may post `/aiact rescan`
in the PR conversation. Scanning uses Gemini quota; reply processing does not.

## Enforcement and limits

The check only blocks merging when a branch rule requires it. After App setup
and a live test, follow [branch-rule setup](GITHUB-APP.md#require-the-check).
`acknowledgement_gate=true` enables this policy in `bot/actions.toml`.

- The App signs a compact current-review snapshot in a PR comment. Every event
  replays that snapshot and current human commands. Copied user markers, invalid
  signatures, stale policy/base and absent reviews cannot authorize a merge.
- New head commits, base revisions, policy or changed findings invalidate old
  commands. Identical findings on the same revision can retain matching decisions
  after a rescan. Editing/deleting a command or posting `reopen` recomputes the
  gate. Deleting/tampering with the current signed snapshot blocks it.
- Comments remain on GitHub. There is no immutable audit trail, dashboard or
  persistent database. Old findings may remain after disappearing from a scan;
  the signed current snapshot defines the gate. Deleting history removes it.
- Scratch SQLite is deleted on normal job exit and the hosted runner is
  discarded. Review state is never cached, uploaded or committed.
- Only trusted default-branch engine/configuration runs. PR blobs are data, never
  installed or executed. Fork PRs and merge queues are unsupported. Non-Python-only
  PRs require no inference and can pass with limited Python review coverage.
- Bot replies are deterministic receipts, not AI conversations. Administrators
  can change policies and bypass settings; durable history is a later phase.
- The per-PR Actions group uses `queue: max` with cancellation disabled, so rapid
  replies wait sequentially rather than replacing pending decisions. GitHub's
  queue holds at most 100 pending runs; retry a cancelled run if that limit is
  reached. Missing verified decision events keep the gate blocked.
