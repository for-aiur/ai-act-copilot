# PR review with our GitHub App

Actions runs the scanner; our App writes findings, replies and the review check.
No server or retained database is needed. [App setup](GITHUB-APP.md).

## Choose manual or automatic

Set repository variable `AIACT_PR_REVIEW_MODE` in **Settings > Secrets and
variables > Actions > Variables**:

- `manual`: PR creation/push does not start a scan. Use **Actions > AI Act PR
  review > Run workflow**, choose `main`, enter the PR number, and run. Or post
  `/aiact rescan` in the PR conversation.
- `automatic`: PR creation/push starts a scan; manual rescans also work. This is
  the default when the variable is absent.

Manual mode means the workflow form or rescan command. The installed App has not
appeared in the native Reviewers picker in our live test. Use automatic mode for
PR creation and push triggers.

Keep `AIACT_PR_REVIEW_ENABLED=true`. Setting it false disables scans and reply
processing in both modes. Writers can use Run workflow; repository writers,
maintainers/admins and configured role holders can request a comment rescan.

## Respond to a finding

Each comment shows the analysis, one question, code and official-source links,
then short reply instructions. A failed review gives a plain explanation and a
retry command; it cannot pass the acknowledgement check. Invalid citations get
one repair attempt within the existing scan deadline, then fail if still invalid.

Reply directly under the current finding, with no IDs or tokens:

```text
/aiact ack
/aiact fp This is a synthetic fixture, not an applicant selection system.
/aiact reopen
```

- **Ack** means seen and kept open for follow-up. No reason is required; it does
  not mean resolved or compliant. The receipt records who acknowledged it and
  GitHub records the date. A future dashboard can import this state.
- **FP** needs a brief reason explaining why the concern does not apply.
- **Reopen** makes the review check pending again. An optional note is allowed.
- Plain context/evidence replies get a receipt but do not count as decisions or
  go to the model. Reply handling makes no model calls.

Assigned role holders or maintainers/admins may decide. When no users are
assigned to a finding's roles, repository writers may decide. Configure roles
and citation-prefix routing in `bot/actions.toml`.

## State and enforcement

The App-owned **AI Act Copilot / acknowledgements** check passes after a complete
review and an authorized ack/FP for every current finding. It confirms awareness,
not that every concern is fixed. Failed/partial scans cannot pass.

Signed snapshots bind short replies to the current thread and revision. Changed
findings/commits get new threads; replies to older threads cannot acknowledge the
new review. Identical reviews reuse a thread. Editing/deleting a command or
posting reopen recomputes the check. Explicit long commands remain compatible.

A branch rule must require this App's check to enforce merging. The current
private-repository plan reports that its saved ruleset is not enforced. The bot
still reports checks; it cannot technically prevent merging on that plan.

Comments remain on GitHub; there is no immutable audit trail or dashboard yet.
Scratch SQLite is discarded and never cached/uploaded. Actions serializes reply
jobs with `queue: max` (up to 100 pending runs). Keep existing PR branches updated
with workflow changes before using inline commands. Fork PRs and merge queues are
unsupported. Reviews cover changed Python files within the documented budgets.
