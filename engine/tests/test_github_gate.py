"""App gate with real engine and signed state; GitHub/model are test transports."""
import copy
import json

import pytest

from aiact.github_bot.actions import run_event
from aiact.github_bot import gate
from aiact.github_bot.github import AppAuth, BotError, GitHub
from aiact.github_bot.service import Service
from aiact.github_bot.store import digest
from aiact.contracts import ScanResult, ScanError
from test_github_bot import system, payload, REPO

KEY = b'test-only-signing-key-not-a-real-App-key'


@pytest.fixture
def gated(system, tmp_path):
    config, store, github, service, contexts = system
    config.acknowledgement_gate = True
    github.checks, github.replies = [], []
    def create_gate(repo, number, head, name):
        github.checks.append({'head': head, 'name': name, 'conclusion': None})
        return len(github.checks)
    def finish_gate(repo, check_id, conclusion, summary):
        github.checks[check_id-1].update(conclusion=conclusion, summary=summary)
    def reply(repo, number, kind, parent, body):
        comment = github.create_comment(repo, number, body)
        github.remote[-1] = (kind, github.remote[-1][1])
        if kind == 'review':
            github.remote[-1][1]['in_reply_to_id'] = parent
        github.replies.append(body)
        return comment
    github.create_gate, github.finish_gate, github.reply = create_gate, finish_gate, reply
    counter = 0
    def run(event='pull_request_target', data=None, scanner=None):
        nonlocal counter
        counter += 1
        return run_event(config, event, data or payload(), github, tmp_path/str(counter), scanner or service.scanner, KEY)
    def snapshot():
        policy = digest([service.policy, True])
        return gate.load_snapshot(gate.snapshot_comment(github.remote, github, github.head), KEY,
                                  REPO, 7, github.head, github.base, policy)
    def user(body, actor='dpo', kind='issue', parent=None, comment_id=900):
        comment = {'id': comment_id, 'body': body, 'user': {'login': actor, 'type': 'User'},
                   'created_at': '2026-10-29T13:00:00Z', 'updated_at': '2026-10-29T13:00:00Z'}
        if parent:
            comment['in_reply_to_id'] = parent
        github.remote.append((kind, comment))
        return {**payload('created'), 'issue': {'number': 7, 'pull_request': {}},
                'pull_request': {'number': 7}, 'comment': copy.deepcopy(comment),
                'sender': {'login': actor, 'type': 'User'}}
    return config, github, contexts, run, snapshot, user


def command(snapshot, action='acknowledge', reason='Reviewed the selection process.'):
    item = snapshot['findings'][0]
    return f"/aiact {action} {item['id']} {item['token']} {reason}"


def test_pending_then_acknowledged_on_exact_head_without_new_inference(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    assert github.checks[-1]['conclusion'] == 'failure'
    assert github.checks[-1]['head'] == github.head
    assert '/aiact acknowledge' in next(c['body'] for k, c in github.remote if gate.MARKER.search(c['body']))
    event = user(command(snapshot()))
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'success'
    assert len(contexts) == 1
    assert 'Recorded **acknowledge**' in github.replies[-1]
    run('issue_comment', event)
    assert len(github.replies) == 1


def test_fp_and_reopen_commands_and_role_enforcement(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    run('issue_comment', user(command(snapshot(), 'fp'), actor='dev'))
    assert github.checks[-1]['conclusion'] == 'failure'
    assert 'not accepted' in github.replies[-1]
    run('issue_comment', user(command(snapshot(), 'fp'), comment_id=901))
    assert github.checks[-1]['conclusion'] == 'success'
    run('issue_comment', user(command(snapshot(), 'reopen'), actor='admin', comment_id=902))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_inline_context_gets_receipt_but_never_acknowledges(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    root = next(c['id'] for k, c in github.remote if k == 'review' and gate.MARKER.search(c['body']))
    event = user('A recruiter reviews every rejection.', kind='review', parent=root)
    run('pull_request_review_comment', event)
    assert 'unverified human statement' in github.replies[-1]
    assert github.checks[-1]['conclusion'] == 'failure'
    assert len(contexts) == 1
    event = user(command(snapshot()), kind='review', parent=root, comment_id=901)
    run('pull_request_review_comment', event)
    assert github.checks[-1]['conclusion'] == 'success'


@pytest.mark.parametrize('action', ['edited', 'deleted'])
def test_editing_or_deleting_acknowledgement_blocks_again(gated, action):
    config, github, contexts, run, snapshot, user = gated
    run()
    event = user(command(snapshot()))
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'success'
    if action == 'deleted':
        github.remote = [(k, c) for k, c in github.remote if c['id'] != 900]
    else:
        next(c for k, c in github.remote if c['id'] == 900)['body'] = 'I need to reconsider.'
        event['comment']['body'] = 'I need to reconsider.'
    event['action'] = action
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'failure'


def test_new_revision_invalidates_old_decisions_and_stale_tokens(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    previous = command(snapshot())
    run('issue_comment', user(previous))
    github.head = 'c'*40
    run()
    assert github.checks[-1]['head'] == 'c'*40
    assert github.checks[-1]['conclusion'] == 'failure'
    run('issue_comment', user(previous, comment_id=901))
    assert 'stale or mismatched' in github.replies[-1]
    assert github.checks[-1]['conclusion'] == 'failure'


def test_tampered_and_user_spoofed_snapshots_cannot_unblock(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    original = gate.snapshot_comment(github.remote, github, github.head)
    forged = copy.deepcopy(original)
    forged['id'] = 900
    forged['user'] = {'login': 'dpo', 'type': 'User'}
    github.remote.append(('issue', forged))
    assert gate.snapshot_comment(github.remote, github, github.head)['id'] == original['id']
    original['body'] = original['body'].replace('aiact-snapshot:', 'aiact-snapshot:bad')
    run('issue_comment', user('Recheck please.', comment_id=901))
    assert github.checks[-1]['conclusion'] == 'failure'
    assert 'No verified complete' in github.checks[-1]['summary']


def test_failed_rescan_replaces_previous_success(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    run('issue_comment', user(command(snapshot())))
    assert github.checks[-1]['conclusion'] == 'success'
    event = user('/aiact rescan', actor='dev', comment_id=901)
    run('issue_comment', event, scanner=lambda *_: ScanResult(status='failed', errors=[ScanError(code='timeout', message='test')]))
    assert snapshot()['status'] == 'failed'
    assert github.checks[-1]['conclusion'] == 'failure'
    run('issue_comment', user('Can we merge?', actor='admin', comment_id=902))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_missing_review_or_changed_policy_cannot_be_approved(gated):
    config, github, contexts, run, snapshot, user = gated
    event = user('/aiact acknowledge '+ 'a'*20+' '+'b'*16+' Reviewed.')
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'failure'
    run()
    config.roles['privacy_officer'] = ['different-reviewer']
    run('issue_comment', event)
    assert 'No verified complete' in github.checks[-1]['summary']


def test_no_python_needs_no_model_and_can_pass(gated):
    config, github, contexts, run, snapshot, user = gated
    github.files = lambda *_: [{'filename': 'README.md', 'status': 'modified'}]
    run()
    assert contexts == []
    assert github.checks[-1]['conclusion'] == 'success'
    assert snapshot()['findings'] == []


def test_fork_rejected_and_gate_fails_closed(gated):
    config, github, contexts, run, snapshot, user = gated
    github.fork = True
    with pytest.raises(BotError, match='fork_review_not_enabled'):
        run()
    assert github.checks[-1]['conclusion'] == 'failure'
    assert not contexts


def test_head_changed_during_scan_never_gets_success(gated):
    config, github, contexts, run, snapshot, user = gated
    def scanner(*_):
        github.head = 'd'*40
        return ScanResult(status='complete')
    with pytest.raises(BotError, match='review_not_current'):
        run(scanner=scanner)
    assert github.checks[-1]['conclusion'] == 'failure'


def test_empty_reason_and_cross_thread_command_cannot_acknowledge(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    run('issue_comment', user(command(snapshot(), reason=' ')))
    assert github.checks[-1]['conclusion'] == 'failure'
    # A bot-owned root for another finding must not be used for this decision.
    github.remote.append(('review', {'id': 901, 'body': '<!-- aiact-finding:'+'e'*20+' -->',
                                    'user': {'login': github.bot_login, 'type': 'Bot'}}))
    run('pull_request_review_comment', user(command(snapshot()), kind='review', parent=901, comment_id=902))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_unsigned_state_and_snapshot_deletion_block(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    run('issue_comment', user(command(snapshot())))
    snapshot_id = gate.snapshot_comment(github.remote, github, github.head)['id']
    deleted = next(c for _, c in github.remote if c['id'] == snapshot_id)
    github.remote = [(k, c) for k, c in github.remote if c['id'] != snapshot_id]
    event = user('placeholder', comment_id=901)
    event.update(action='deleted', comment=deleted)
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'failure'


def test_partial_even_with_no_findings_cannot_pass(gated):
    config, github, contexts, run, snapshot, user = gated
    run(scanner=lambda *_: ScanResult(status='partial'))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_check_transport_reuses_only_own_app_check_and_fails_closed_first(monkeypatch):
    client = GitHub('test-only', 'evros-test[bot]')
    calls = []
    def request(method, path, body=None):
        calls.append((method, path, body))
        if method == 'GET':
            return {'check_runs': [
                {'id': 1, 'external_id': f'aiact:{REPO}:7', 'app': {'slug': 'another-app'}},
                {'id': 2, 'external_id': f'aiact:{REPO}:7', 'app': {}},
                {'id': 3, 'external_id': f'aiact:{REPO}:7', 'app': {'slug': 'evros-test'}}]}
        return {'id': 3}
    monkeypatch.setattr(client, 'request', request)
    assert client.create_gate(REPO, 7, 'a'*40, gate.CHECK_NAME) == 3
    assert calls[-1][0] == 'PATCH' and calls[-1][1].endswith('/3')
    assert calls[-1][2]['conclusion'] == 'failure'
    client.finish_gate(REPO, 3, 'success', 'all acknowledged')
    assert calls[-1][2]['conclusion'] == 'success'


def test_repository_app_auth_discovers_installation_and_scopes_check_permission(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import jwt
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    raw = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    calls = []
    def request(self, method, path, body=None):
        jwt.decode(self.token, key.public_key(), algorithms=['RS256'], issuer='123')
        calls.append((method, path, body))
        if path == '/app':
            return {'id': 123, 'slug': 'evros-test'}
        if path.endswith('/installation'):
            return {'id': 456}
        return {'token': 'test-installation-token'}
    monkeypatch.setattr(GitHub, 'request', request)
    client = AppAuth('123', key_bytes=raw).repository_client(REPO, 42)
    assert client.bot_login == 'evros-test[bot]'
    assert calls[-1][1] == '/app/installations/456/access_tokens'
    assert calls[-1][2] == {'repository_ids': [42], 'permissions': {
        'contents': 'read', 'pull_requests': 'write', 'issues': 'read', 'checks': 'write'}}


def test_edit_actor_cannot_borrow_original_authors_role(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    event = user(command(snapshot()))
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'success'
    actual = next(c for _, c in github.remote if c['id'] == 900)
    actual['body'] = command(snapshot(), 'false-positive', 'Edited by a writer, not the DPO.')
    actual['updated_at'] = '2026-10-29T14:00:00Z'
    event.update(action='edited', comment=copy.deepcopy(actual), sender={'login': 'dev', 'type': 'User'})
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'failure'
    assert any('Decision not accepted' in c['body'] for _, c in github.remote if gate.owned(c, github))
    # Replay later must remember the verified editor, not the original author.
    run('issue_comment', user('Recheck.', actor='admin', comment_id=901))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_body_changed_without_matching_verified_event_invalidates_receipt(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    run('issue_comment', user(command(snapshot())))
    assert github.checks[-1]['conclusion'] == 'success'
    actual = next(c for _, c in github.remote if c['id'] == 900)
    actual['body'] = command(snapshot(), 'false-positive', 'Another explanation.')
    run('issue_comment', user('Recheck.', actor='admin', comment_id=901))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_every_finding_needs_its_own_decision(gated):
    from aiact.pipeline import scan
    from test_github_bot import StubModel
    config, github, contexts, run, snapshot, user = gated
    def two_findings(root, context):
        result = scan(root, StubModel(), explicit_context=context)
        result.findings.append(result.findings[0].model_copy(update={
            'title': 'Another context question', 'context_question': 'Who reviews rejected applicants?'}))
        return result
    run(scanner=two_findings)
    state = snapshot()
    assert len(state['findings']) == 2
    run('issue_comment', user(command(state)))
    assert github.checks[-1]['conclusion'] == 'failure'
    second = state['findings'][1]
    run('issue_comment', user(f"/aiact fp {second['id']} {second['token']} Synthetic fixture only.", comment_id=901))
    assert github.checks[-1]['conclusion'] == 'success'
