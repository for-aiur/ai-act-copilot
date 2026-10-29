"""One Actions job; App identity and GitHub comments replace retained storage."""
import json
import os
from pathlib import Path
import tempfile

from .config import BotConfig
from .github import AppAuth, BotError, GitHub
from .service import Service, allowed_path, render_finding, same_revision
from .store import Store, digest
from . import gate


class ActionsService(Service):
    def render(self, record):
        body = render_finding(record, self.config).split('Dismissal/resolution decisions require')[0]
        if self.config.acknowledgement_gate:
            token = gate.token_for(self.snapshot, {'id': record['id'], 'payload': json.loads(record['payload'])})
            command = record['id']+' '+token+' <reason>'
            return body + ('**Decision required for this revision:**\n\n'
                f'- `/aiact acknowledge {command}`\n'
                f'- `/aiact false-positive {command}`\n'
                f'- `/aiact reopen {command}`\n\n'
                'Reply here or in the PR conversation. An assigned role holder or maintainer/admin must decide; '
                'when no users are assigned for these roles, repository writers may decide. '
                'Plain replies receive a receipt but do not unblock merging or go to the model. '
                'Acknowledgement is a human review decision, not a compliance certificate.')
        return body + ('Stateless PR review: reply in this thread with context or evidence. '
                       'Replies are not automatically consumed. Use `/aiact rescan` in a PR '
                       'conversation comment to rerun. Decisions and automatic closure are deferred.')

    def publish(self, repo, number, client, expected_head=None, patches=None, expected_base=None):
        # Rows now exist: recover matching GitHub-owned comment IDs before posting.
        self.backfill(repo, number, client)
        return super().publish(repo, number, client, expected_head, patches, expected_base)


def run_event(config, event, payload, client, directory, scanner=None, signing_key=None):
    repo = payload.get('repository', {}).get('full_name', '').lower()
    if repo not in config.repositories:
        raise BotError('repository_not_allowed')
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
    import re
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
                snapshot['findings'] = [dict(id=r['id'], roles=r['roles'], token=gate.token_for(snapshot, r))
                                        for r in saved['records']]
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
            run_event(config, os.environ['GITHUB_EVENT_NAME'], payload, client, directory, signing_key=signing_key)
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
