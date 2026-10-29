# GitHub App setup

The App supplies identity and permissions. Actions does the work. Leave webhooks
inactive; no hosting, callback server or database is needed.

## Register and install

1. Open [New GitHub App](https://github.com/settings/apps/new). Name it
   **Evros AI Act Copilot** (or an available variant). Homepage:
   `https://github.com/for-aiur/ai-act-copilot`. Leave callback URLs blank and
   uncheck **Active** under Webhook.
2. Repository permissions: **Contents: Read**, **Pull requests: Read and write**,
   **Issues: Read**, **Checks: Read and write**. No account/administration
   permissions. Select **Only on this account**.
3. Create it, upload `extensions/vscode/media/copilot-wig.png` as the avatar and
   record the numeric **App ID**, not the Client ID.
4. Generate a private key in the App's key settings. Keep the downloaded PEM
   private. Do not paste it into a PR, chat, issue or repository file.
5. Choose **Install App**, your account, **Only select repositories**, and
   select `ai-act-copilot`.

`bot/github-app-manifest.json` records the webhook-free permission set.

## Repository configuration

In **Repository > Settings > Secrets and variables > Actions**:

| Type | Name | Value |
| --- | --- | --- |
| Variable | `AIACT_APP_ID` | Numeric App ID |
| Secret | `AIACT_APP_PRIVATE_KEY` | Entire PEM including BEGIN/END lines |
| Secret | `GEMINI_API_KEY` | Existing Gemini key |
| Variable | `AIACT_PR_REVIEW_ENABLED` | `true` |

Merge the reviewed YIL-18 implementation into the default branch. Its workflow
and role configuration run from that trusted branch. Tokens are scoped to this
repository and revoked at job end when possible; otherwise they expire. Key
rotation requires a rescan to replace old snapshot signatures.

New comments use the App name/avatar. Earlier `github-actions[bot]` comments are
left untouched and do not satisfy this App's gate.

## Test before enforcing

Use an internal PR changing a Python example:

1. Confirm App-authored findings and an initially failing acknowledgement check.
2. Post an inline context reply. Expect a receipt, with the gate still blocked.
3. Copy each finding's acknowledge/false-positive command with a reason. Only all
   decided findings should pass. Edit/delete a decision or post `reopen` to block
   it again. Push a new commit and verify old tokens no longer work.

This uses real Gemini quota. Local tests use labeled test-only transports and do
not prove live App registration works.

## Require the check

After a live test, use **Settings > Rules > Rulesets** (or classic **Branches**).
Target `main`, require PRs and status checks, then select
**AI Act Copilot / acknowledgements** with **this App as its expected source**.
Do not select only the Actions `review` job. Preserve other existing protections.
Keep the bypass list empty, or apply classic protection to administrators too,
if nobody should bypass it.

Private-repository protection requires a supported paid GitHub plan. Without
that, the bot reports failure but cannot enforce merging. See
[GitHub plan availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
and [App-bound required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

Require the check only after the App is installed, the workflow is on the default
branch and a live check has appeared. Otherwise PRs wait for a check that cannot
run. This adapter does not support GitHub merge queues.
