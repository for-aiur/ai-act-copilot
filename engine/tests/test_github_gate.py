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
    def run(event='pull_request_target', data=None, scanner=None, mode='automatic'):
        nonlocal counter
        counter += 1
        return run_event(config, event, data or payload(), github, tmp_path/str(counter), scanner or service.scanner, KEY, mode)
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
    assert '/aiact ack' in next(c['body'] for k, c in github.remote if gate.MARKER.search(c['body']))
    event = user(command(snapshot()))
    run('issue_comment', event)
    assert github.checks[-1]['conclusion'] == 'success'
    assert len(contexts) == 1
    assert 'Noted.' in github.replies[-1]
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
    assert 'Context noted' in github.replies[-1]
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
    assert 'older or mismatched' in github.replies[-1]
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
    run('issue_comment', user(command(snapshot(), 'false-positive', reason=' ')))
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


def test_ack_needs_no_reason_and_keeps_concern_open_for_follow_up(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    finding = snapshot()['findings'][0]
    run('pull_request_review_comment', user('/aiact ack', kind='review', parent=finding['thread_id']))
    assert github.checks[-1]['conclusion'] == 'success'
    assert 'remains open for follow-up' in github.replies[-1]
    assert len(contexts) == 1
    run('pull_request_review_comment', user('/aiact reopen', kind='review', parent=finding['thread_id'], comment_id=901))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_short_fp_requires_reason_and_authorized_role(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    root = snapshot()['findings'][0]['thread_id']
    run('pull_request_review_comment', user('/aiact fp', kind='review', parent=root))
    assert github.checks[-1]['conclusion'] == 'failure'
    assert 'needs a brief reason' in github.replies[-1]
    run('pull_request_review_comment', user('/aiact fp Test fixture only.', actor='dev', kind='review', parent=root, comment_id=901))
    assert github.checks[-1]['conclusion'] == 'failure'
    run('pull_request_review_comment', user('/aiact fp Test fixture only.', kind='review', parent=root, comment_id=902))
    assert github.checks[-1]['conclusion'] == 'success'


def test_short_command_needs_current_thread_not_top_level_comment(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    run('issue_comment', user('/aiact ack'))
    assert github.checks[-1]['conclusion'] == 'failure'
    assert 'CURRENT finding thread' in github.replies[-1]


def test_new_revision_gets_new_thread_and_old_short_reply_cannot_approve_it(gated):
    config, github, contexts, run, snapshot, user = gated
    run()
    root = snapshot()['findings'][0]['thread_id']
    original = next(c['body'] for _, c in github.remote if c['id'] == root)
    github.head = 'c'*40
    run()
    current = snapshot()['findings'][0]['thread_id']
    assert current != root
    assert next(c['body'] for _, c in github.remote if c['id'] == root) == original
    run('pull_request_review_comment', user('/aiact ack', kind='review', parent=root))
    assert github.checks[-1]['conclusion'] == 'failure'
    assert 'CURRENT finding thread' in github.replies[-1]
    run('pull_request_review_comment', user('/aiact ack', kind='review', parent=current, comment_id=901))
    assert github.checks[-1]['conclusion'] == 'success'


def test_same_review_reuses_thread_but_changed_finding_gets_new_thread(gated):
    from aiact.pipeline import scan
    from test_github_bot import StubModel
    config, github, contexts, run, snapshot, user = gated
    run()
    root = snapshot()['findings'][0]['thread_id']
    count = len(github.remote)
    run()
    assert snapshot()['findings'][0]['thread_id'] == root
    assert len(github.remote) == count
    def changed(root, context):
        result = scan(root, StubModel(), explicit_context=context)
        result.findings[0].title = 'Changed concern requiring fresh review'
        return result
    run(scanner=changed)
    assert snapshot()['findings'][0]['thread_id'] != root
    run('pull_request_review_comment', user('/aiact ack', kind='review', parent=root))
    assert github.checks[-1]['conclusion'] == 'failure'


def test_file_level_thread_when_evidence_is_outside_diff(gated):
    config, github, contexts, run, snapshot, user = gated
    original_files = github.files
    def files(*args):
        rows = original_files(*args)
        rows[0]['patch'] = '@@ -100,1 +100,1 @@\n+unrelated = True'
        return rows
    github.files = files
    run()
    finding = snapshot()['findings'][0]
    assert finding['thread_kind'] == 'review'
    root = next(c for _, c in github.remote if c['id'] == finding['thread_id'])
    assert root['line'] is None and root['path'] == 'src/ranker.py'
    run('pull_request_review_comment', user('/aiact ack', kind='review', parent=root['id']))
    assert github.checks[-1]['conclusion'] == 'success'


def test_manual_mode_skips_auto_but_dispatch_and_replies_still_work(gated):
    config, github, contexts, run, snapshot, user = gated
    run(mode='manual')
    assert not github.checks and not contexts
    event = {**payload(), 'inputs': {'pull_request': '7'}, 'sender': {'login': 'dev', 'type': 'User'}}
    run('workflow_dispatch', event, mode='manual')
    assert len(contexts) == 1
    root = snapshot()['findings'][0]['thread_id']
    run('pull_request_review_comment', user('/aiact ack', kind='review', parent=root), mode='manual')
    assert github.checks[-1]['conclusion'] == 'success'


def test_manual_mode_preserves_authorized_rescan_command(gated):
    config, github, contexts, run, snapshot, user = gated
    run('issue_comment', user('/aiact rescan', actor='dev'), mode='manual')
    assert len(contexts) == 1 and snapshot()['status'] == 'complete'


@pytest.mark.parametrize('number', ['0', '-1', '7;echo secret', '../7', '', '1.5'])
def test_dispatch_rejects_invalid_pr_number_without_scanning(gated, number):
    config, github, contexts, run, snapshot, user = gated
    event = {**payload(), 'inputs': {'pull_request': number}, 'sender': {'login': 'dev', 'type': 'User'}}
    with pytest.raises(BotError, match='positive_pr_number'):
        run('workflow_dispatch', event, mode='manual')
    assert not contexts and not github.checks


def test_dispatch_rejects_unauthorized_actor_and_invalid_mode(gated):
    config, github, contexts, run, snapshot, user = gated
    event = {**payload(), 'inputs': {'pull_request': '7'}, 'sender': {'login': 'outsider', 'type': 'User'}}
    with pytest.raises(BotError, match='not_authorized'):
        run('workflow_dispatch', event)
    with pytest.raises(BotError, match='invalid_review_mode'):
        run(mode='typo')
    assert not contexts


def test_file_review_api_does_not_require_line(monkeypatch):
    client = GitHub('test-only', 'evros-test[bot]')
    calls = []
    monkeypatch.setattr(client, 'request', lambda method, path, body=None: calls.append((method, path, body)))
    client.create_comment(REPO, 7, 'review', 'a'*40, 'src/ranker.py')
    assert calls[-1][2] == {'body': 'review', 'commit_id': 'a'*40, 'path': 'src/ranker.py', 'subject_type': 'file'}


def test_comments_are_concise_and_keep_analysis_question_sources_and_reply_guide(gated):
    import re
    config, github, contexts, run, snapshot, user = gated
    run()
    # One current status and one finding, no duplicate technical run summary.
    assert len(github.remote) == 2
    root = next(c['body'] for _, c in github.remote if gate.MARKER.search(c['body']))
    visible = re.sub(r'<!--.*?-->', '', root, flags=re.S)
    assert '### 🤖 Recruitment selection context' in visible
    assert 'This model predicts applicant scores' in visible and '**Question:**' in visible
    assert '[Code](' in visible and '[Annex III](' in visible
    assert '/aiact ack' in visible and '/aiact fp <reason>' in visible
    assert len(visible.split()) < 160
    for clutter in ['Engineering review', 'certificate', 'Commit:', 'changed Python', 'unassigned', 'State:', '```']:
        assert clutter not in visible
    status = gate.snapshot_comment(github.remote, github, github.head)['body']
    visible_status = re.sub(r'<!--.*?-->', '', status, flags=re.S).strip()
    assert visible_status == '🤖 Review ready. Questions are attached to the code.'
    assert '#discussion_r' in github.checks[-1]['summary']


def test_citation_failure_is_visible_in_plain_language_and_still_blocks(gated):
    import re
    config, github, contexts, run, snapshot, user = gated
    run(scanner=lambda *_: ScanResult(status='failed', errors=[
        ScanError(code='citation_invalid', message='Question topic does not match its cited legal passage.')]))
    assert len(github.remote) == 1
    body = re.sub(r'<!--.*?-->', '', github.remote[0][1]['body'], flags=re.S)
    assert "couldn't verify the legal references" in body and '/aiact rescan' in body
    assert 'citation_invalid' not in body and 'Engineering review' not in body
    assert github.checks[-1]['conclusion'] == 'failure'
    assert "couldn't verify the legal references" in github.checks[-1]['summary']
