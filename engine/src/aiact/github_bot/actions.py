"""One Actions job; App identity and GitHub comments replace retained storage."""
import json
import os
from pathlib import Path
import re
import tempfile

from .config import BotConfig
from .github import AppAuth, BotError, GitHub
from .service import Service, allowed_path, render_finding, same_revision
from .store import Store, digest
from . import gate


class ActionsService(Service):
    @property
    def emit_run_summary(self):
        return not self.config.acknowledgement_gate

    def render(self, record):
        mode = 'short' if self.config.acknowledgement_gate else 'stateless'
        body = render_finding(record, self.config, mode)
        if self.config.acknowledgement_gate:
            token = gate.token_for(self.snapshot, {'id': record['id'], 'payload': json.loads(record['payload'])})
            body += f'\n\n<!-- aiact-review:{token} -->'
        return body

    def backfill(self, repo, number, client):
        if not self.config.acknowledgement_gate:
            return super().backfill(repo, number, client)
        comments = client.comments(repo, number)
        for kind, comment in comments:
            marker = gate.MARKER.search(comment.get('body') or '') if gate.owned(comment, client) else None
            record = self.store.finding(marker[1]) if marker else None
            if record and record['repo'] == repo and record['pr'] == number:
                token = gate.token_for(self.snapshot, {'id': record['id'], 'payload': json.loads(record['payload'])})
                if f'<!-- aiact-review:{token} -->' in comment['body']:
                    self.store.published(record['id'], comment['id'], kind, comment['body'])
        return comments

    def publish(self, repo, number, client, expected_head=None, patches=None, expected_base=None):
        # Rows now exist: recover matching GitHub-owned comment IDs before posting.
        self.backfill(repo, number, client)
        return super().publish(repo, number, client, expected_head, patches, expected_base)


def run_event(config, event, payload, client, directory, scanner=None, signing_key=None, review_mode='automatic'):
    repo = payload.get('repository', {}).get('full_name', '').lower()
    if repo not in config.repositories:
        raise BotError('repository_not_allowed')
    if review_mode not in {'manual', 'automatic'}:
        raise BotError('invalid_review_mode_use_manual_or_automatic')
    if event == 'pull_request_target' and review_mode == 'manual':
        return
    if event == 'workflow_dispatch':
        number = str(payload.get('inputs', {}).get('pull_request', ''))
        if not re.fullmatch(r'[1-9][0-9]{0,8}', number):
            raise BotError('manual_review_requires_positive_pr_number')
        actor = payload.get('sender', {}).get('login', '')
        if (not actor or client.permission(repo, actor) not in {'write', 'maintain', 'admin'}) and not config.actor_roles(actor):
            raise BotError('manual_review_not_authorized')
        payload = {**payload, 'number': int(number), 'action': 'opened'}
        event = 'pull_request_target'
    if config.acknowledgement_gate:
        if not signing_key:
            raise BotError('github_app_signing_key_required')
        return run_gated_event(config, event, payload, client, directory, scanner, signing_key)
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


def run_gated_event(config, event, payload, client, directory, scanner, signing_key):
    repo = payload['repository']['full_name'].lower()
    if event == 'pull_request_target':
        if payload.get('action') not in {'opened', 'reopened', 'synchronize', 'ready_for_review', 'edited'}:
            return
        number = int(payload['number'])
    elif event in {'issue_comment', 'pull_request_review_comment'}:
        if payload.get('sender', {}).get('type') == 'Bot':
            return
        if event == 'issue_comment' and 'pull_request' not in payload.get('issue', {}):
            return
        number = int((payload.get('issue') or payload.get('pull_request', {}))['number'])
    else:
        raise BotError('unsupported_actions_event')
    pr = client.pull(repo, number)
    if pr.get('state') != 'open':
        return
    head, base = pr['head']['sha'], pr['base']['sha']
    if not re.fullmatch('[a-f0-9]{40}', head) or not re.fullmatch('[a-f0-9]{40}', base):
        raise BotError('commit_invalid')
    check_id = client.create_gate(repo, number, head, gate.CHECK_NAME)
    try:
        if pr['head']['repo']['full_name'].lower() != repo and not config.allow_forks:
            raise BotError('fork_review_not_enabled')
        store = Store(Path(directory)/'scratch.sqlite3')
        service = ActionsService(config, store, None, scanner)
        policy = digest([service.policy, config.acknowledgement_gate])
        comments = client.comments(repo, number)
        existing = gate.snapshot_comment(comments, client, head)
        snapshot = gate.load_snapshot(existing, signing_key, repo, number, head, base, policy)
        comment = payload.get('comment', {})
        rescan = (payload.get('action') == 'created' and comment.get('user', {}).get('type') == 'User'
                  and (comment.get('body') or '').strip() == '/aiact rescan')
        if rescan:
            actor = comment['user'].get('login', '')
            rescan = client.permission(repo, actor) in {'write', 'maintain', 'admin'} or bool(config.actor_roles(actor))
        if event == 'pull_request_target' or rescan:
            snapshot = {'version': 1, 'repo': repo, 'pr': number, 'head': head, 'base': base,
                        'policy': policy, 'status': 'running', 'findings': []}
            existing = gate.save_snapshot(client, repo, number, snapshot, signing_key, existing)
            service.snapshot = snapshot
            changed = client.files(repo, number)
            # Non-Python-only PRs need no inference, but still receive a scoped check.
            if any(f.get('status') != 'removed' and allowed_path(f['filename']) for f in changed):
                service.review(repo, number, client, nonce='gate:'+str(payload.get('comment', {}).get('id', '')))
                runs = store.export(repo, number)['runs']
                if not runs:
                    raise BotError('review_not_current')
                saved = json.loads(runs[-1]['result'])
                snapshot['status'] = saved['scan_result']['status']
                snapshot['error_codes'] = [e['code'] for e in saved['scan_result']['errors']]
                snapshot['findings'] = []
                for record in saved['records']:
                    published = store.finding(record['id'])
                    snapshot['findings'].append(dict(id=record['id'], roles=record['roles'],
                        token=gate.token_for(snapshot, record), thread_id=published['github_id'],
                        thread_kind=published['github_kind'], title=record['payload']['title']))
            else:
                snapshot['status'] = 'complete'
            if not same_revision(client.pull(repo, number), head, base):
                raise BotError('review_not_current')
            gate.save_snapshot(client, repo, number, snapshot, signing_key, existing)
            comments = client.comments(repo, number)
        gate.finish(client, config, repo, number, pr, check_id, snapshot, comments, event, payload, signing_key)
    except Exception:
        # A failed rescan cannot reuse an earlier successful gate or snapshot.
        client.finish_gate(repo, check_id, 'failure', 'Review processing failed. Fix the workflow error and request a new scan.')
        raise


def main():
    client = None
    app_client = False
    try:
        config = BotConfig.load(Path('bot/actions.toml'))
        payload = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        review_mode = os.environ.get('AIACT_PR_REVIEW_MODE', 'automatic') or 'automatic'
        if review_mode not in {'manual', 'automatic'}:
            raise BotError('invalid_review_mode_use_manual_or_automatic')
        signing_key = os.environ.get('AIACT_APP_PRIVATE_KEY', '').encode()
        app_id = os.environ.get('AIACT_APP_ID', '')
        if config.acknowledgement_gate or app_id:
            if not app_id.isdigit() or not signing_key:
                raise BotError('configure_AIACT_APP_ID_and_AIACT_APP_PRIVATE_KEY')
            repo = payload['repository']['full_name'].lower()
            if repo not in config.repositories:
                raise BotError('repository_not_allowed')
            client = AppAuth(app_id, key_bytes=signing_key).repository_client(repo, payload['repository']['id'])
            app_client = True
        else:
            client = GitHub(os.environ['GH_TOKEN'], 'github-actions[bot]')
        with tempfile.TemporaryDirectory(prefix='aiact-actions-') as directory:
            run_event(config, os.environ['GITHUB_EVENT_NAME'], payload, client, directory,
                      signing_key=signing_key, review_mode=review_mode)
        return 0
    except (BotError, ValueError, KeyError, OSError) as exc:
        # Never print payloads, source, tokens or raw transport exceptions.
        print('AI Act PR review failed: '+(str(exc) if isinstance(exc, BotError) else 'configuration_invalid'))
        return 1
    finally:
        if app_client:
            try:
                client.request('DELETE', '/installation/token')
            except BotError:
                pass  # Token is short-lived even if revocation is temporarily unavailable.


if __name__ == '__main__':
    raise SystemExit(main())
