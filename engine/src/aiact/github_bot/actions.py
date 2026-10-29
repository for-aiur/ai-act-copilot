"""One Actions job, no retained database or App/webhook credentials."""
import json
import os
from pathlib import Path
import tempfile

from .config import BotConfig
from .github import BotError, GitHub
from .service import Service, render_finding
from .store import Store


class ActionsService(Service):
    def render(self, record):
        body = render_finding(record, self.config).split('Dismissal/resolution decisions require')[0]
        return body + ('Stateless PR review: reply in this thread with context or evidence. '
                       'Replies are not automatically consumed. Use `/aiact rescan` in a PR '
                       'conversation comment to rerun. Decisions and automatic closure are deferred.')

    def publish(self, repo, number, client, expected_head=None, patches=None, expected_base=None):
        # Rows now exist: recover matching GitHub-owned comment IDs before posting.
        self.backfill(repo, number, client)
        return super().publish(repo, number, client, expected_head, patches, expected_base)


def run_event(config, event, payload, client, directory, scanner=None):
    repo = payload.get('repository', {}).get('full_name', '').lower()
    if repo not in config.repositories:
        raise BotError('repository_not_allowed')
    nonce = ''
    if event == 'pull_request_target':
        if payload.get('action') not in {'opened', 'reopened', 'synchronize', 'ready_for_review', 'edited'}:
            return
        number = payload['number']
    elif event == 'issue_comment':
        issue, comment = payload.get('issue', {}), payload.get('comment', {})
        if (payload.get('action') != 'created' or 'pull_request' not in issue or
                comment.get('user', {}).get('type') == 'Bot' or
                (comment.get('body') or '').strip() != '/aiact rescan'):
            return
        actor = comment.get('user', {}).get('login', '')
        if client.permission(repo, actor) not in {'write', 'maintain', 'admin'} and not config.actor_roles(actor):
            return
        number = issue['number']
        nonce = 'comment:'+str(comment['id'])
    else:
        raise BotError('unsupported_actions_event')
    # Scratch SQLite reuses the tested adapter. Never uploaded, cached or committed.
    store = Store(Path(directory)/'scratch.sqlite3')
    service = ActionsService(config, store, None, scanner)
    service.review(repo, int(number), client, nonce=nonce)
    runs = store.export(repo, int(number))['runs']
    if runs and runs[-1]['status'] != 'complete':
        raise BotError('review_incomplete_see_pr_summary')


def main():
    try:
        config = BotConfig.load(Path('bot/actions.toml'))
        payload = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        client = GitHub(os.environ['GH_TOKEN'], 'github-actions[bot]')
        with tempfile.TemporaryDirectory(prefix='aiact-actions-') as directory:
            run_event(config, os.environ['GITHUB_EVENT_NAME'], payload, client, directory)
        return 0
    except (BotError, ValueError, KeyError, OSError) as exc:
        # Never print payloads, source, tokens or raw transport exceptions.
        print('AI Act PR review failed: '+(str(exc) if isinstance(exc, BotError) else 'configuration_invalid'))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
