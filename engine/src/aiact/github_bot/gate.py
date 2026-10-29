"""Reconstruct merge decisions from signed App comments, not a retained database."""
import base64
import hashlib
import hmac
import json
import re

from .github import BotError
from .service import MARKER, same_revision, safe_text
from .store import digest, encoded

CHECK_NAME = 'AI Act Copilot / acknowledgements'
SNAPSHOT = re.compile(r'<!-- aiact-snapshot:([A-Za-z0-9_-]+)\.([a-f0-9]{64}) -->')
PROOF = re.compile(r'<!-- aiact-decision:([A-Za-z0-9_-]+)\.([a-f0-9]{64}) -->')
COMMAND = re.compile(r'/aiact (acknowledge|ack|false-positive|fp|reopen) ([a-f0-9]{20}) ([a-f0-9]{16}) ([\s\S]{1,2000})')


def owned(comment, client):
    return comment.get('user', {}).get('type') == 'Bot' and comment['user'].get('login') == client.bot_login


def state_marker(head):
    return '<!-- aiact-state:'+head+' -->'


def token_for(snapshot, record):
    return digest([snapshot['head'], snapshot['base'], snapshot['policy'], record['id'], record['payload']])[:16]


def snapshot_body(snapshot, key):
    raw = base64.urlsafe_b64encode(encoded(snapshot).encode()).decode().rstrip('=')
    signature = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()
    return '\n\n'.join([state_marker(snapshot['head']), f'<!-- aiact-snapshot:{raw}.{signature} -->',
        '### AI Act Copilot · acknowledgement gate',
        f"Review: **{snapshot['status']}** · commit `{snapshot['head']}` · {len(snapshot['findings'])} finding(s).",
        'Every current finding needs an authorized acknowledgement or false-positive decision with a reason. '
        'Acknowledgement records human review, not legal compliance. The App-owned required check reports merge readiness.'])


def snapshot_comment(comments, client, head):
    matches = [c for kind, c in comments if kind == 'issue' and owned(c, client)
               and (c.get('body') or '').startswith(state_marker(head))]
    return max(matches, key=lambda c: c['id']) if matches else None


def load_snapshot(comment, key, repo, number, head, base, policy):
    if not comment:
        return None
    match = SNAPSHOT.search(comment.get('body', '')[:32000])
    if not match or not hmac.compare_digest(match[2], hmac.new(key, match[1].encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(match[1]+'='*(-len(match[1]) % 4)))
        if (data['version'] != 1 or [data['repo'], data['pr'], data['head'], data['base'], data['policy']] !=
                [repo, number, head, base, policy] or data['status'] not in {'running', 'complete', 'partial', 'failed'} or
                not isinstance(data['findings'], list) or len(data['findings']) > 4):
            return None
        ids = set()
        for finding in data['findings']:
            if (not re.fullmatch(r'[a-f0-9]{20}', finding['id']) or finding['id'] in ids or
                    not re.fullmatch(r'[a-f0-9]{16}', finding['token']) or
                    not isinstance(finding['roles'], list)):
                return None
            ids.add(finding['id'])
        return data
    except (ValueError, TypeError, KeyError):
        return None


def save_snapshot(client, repo, number, snapshot, key, existing=None):
    body = snapshot_body(snapshot, key)
    if existing:
        return client.update_comment(repo, 'issue', existing['id'], body)
    return client.create_comment(repo, number, body)


def can_decide(config, finding, actor, permission):
    if permission in {'maintain', 'admin'}:
        return True
    assigned = {login.lower() for role in finding['roles'] for login in config.roles.get(role, [])}
    return actor.lower() in assigned if assigned else permission == 'write'


def command_hash(comment):
    return digest([comment.get('body') or '', comment.get('updated_at')])


def provenance(comments, client, key, event, payload):
    proofs = {}
    for _, comment in comments:
        match = PROOF.search(comment.get('body') or '') if owned(comment, client) else None
        if not match or not hmac.compare_digest(match[2], hmac.new(key, match[1].encode(), hashlib.sha256).hexdigest()):
            continue
        try:
            proof = json.loads(base64.urlsafe_b64decode(match[1]+'='*(-len(match[1]) % 4)))
            if proof['purpose'] == 'decision' and proof['kind'] in {'issue', 'review'}:
                proofs[(proof['kind'], proof['id'])] = proof
        except (ValueError, KeyError, TypeError):
            continue
    current = None
    if payload.get('action') != 'deleted' and payload.get('sender', {}).get('type') == 'User':
        kind = 'review' if event == 'pull_request_review_comment' else 'issue'
        incoming = payload.get('comment', {})
        actual = next((c for k, c in comments if k == kind and c['id'] == incoming.get('id') and
                       c.get('user', {}).get('type') == 'User'), None)
        if actual and command_hash(actual) == command_hash(incoming):
            current = {'purpose': 'decision', 'kind': kind, 'id': actual['id'],
                       'hash': command_hash(actual), 'actor': payload['sender']['login']}
            proofs[(kind, actual['id'])] = current
    return proofs, current


def replay(config, snapshot, comments, client, repo, number, proofs):
    findings = {f['id']: f for f in snapshot['findings']}
    states, outcomes, permissions = {}, {}, {}
    roots = {c['id']: MARKER.search(c.get('body') or '') for kind, c in comments
             if kind in {'issue', 'review'} and owned(c, client)}
    ordered = sorted(comments, key=lambda item: (item[1].get('updated_at') or item[1].get('created_at') or '', item[1]['id']))
    for kind, comment in ordered:
        if kind not in {'issue', 'review'} or comment.get('user', {}).get('type') != 'User':
            continue
        body = (comment.get('body') or '').strip()
        if body == '/aiact rescan':
            continue  # This is a scan request, not a finding decision.
        match = COMMAND.fullmatch(body)
        parent = roots.get(comment.get('in_reply_to_id')) if kind == 'review' else None
        if not match:
            if body.startswith('/aiact '):
                outcomes[(kind, comment['id'])] = 'Command not accepted. Copy a current command from the finding and include its ID, review token and a reason.'
            elif parent and parent[1] in findings:
                outcomes[(kind, comment['id'])] = 'Context received as an unverified human statement. It was not sent to the model and does not acknowledge the finding. Use the command shown in the finding to record a decision.'
            continue
        action, finding_id, token, reason = match.groups()
        finding = findings.get(finding_id)
        if not reason.strip() or not finding or token != finding['token'] or (parent and parent[1] != finding_id):
            outcomes[(kind, comment['id'])] = 'Decision not accepted: stale or mismatched finding/token. Copy the command from the current finding.'
            continue
        proof = proofs.get((kind, comment['id']))
        if not proof or proof['hash'] != command_hash(comment):
            outcomes[(kind, comment['id'])] = 'No verified command event matches this comment. Post a new decision command.'
            continue
        # An editor may differ from the original author. Trust the signed event
        # actor, never attribute an edited command to the original commenter.
        actor = proof['actor']
        if actor not in permissions:
            try:
                permissions[actor] = client.permission(repo, actor)
            except BotError as exc:
                if str(exc) != 'github_http_404':
                    raise
                permissions[actor] = 'none'
        if not can_decide(config, finding, actor, permissions[actor]):
            outcomes[(kind, comment['id'])] = 'Decision not accepted: an assigned role holder or repository maintainer/admin is required. When this finding has no assigned users, repository writers may decide.'
            continue
        action = {'ack': 'acknowledge', 'fp': 'false-positive'}.get(action, action)
        states[finding_id] = action
        outcomes[(kind, comment['id'])] = f'Recorded **{action}** for `{finding_id}` from {safe_text(actor)}. This records a human decision, not a compliance determination.'
    pending = [fid for fid in findings if states.get(fid) not in {'acknowledge', 'false-positive'}]
    return pending, outcomes


def receipt(client, repo, number, event, payload, comments, outcomes, proof, key):
    if payload.get('action') == 'deleted':
        return
    comment = payload.get('comment', {})
    kind = 'review' if event == 'pull_request_review_comment' else 'issue'
    outcome = outcomes.get((kind, comment.get('id')))
    if not outcome:
        return
    marker = '<!-- aiact-receipt:'+digest([kind, comment['id']])+ ' -->'
    # One receipt per user comment, updated on edits/retries; no reply loop.
    existing = next((c for _, c in comments if owned(c, client) and (c.get('body') or '').startswith(marker)), None)
    body = marker+'\n\n'+outcome
    if proof:
        raw = base64.urlsafe_b64encode(encoded(proof).encode()).decode().rstrip('=')
        signature = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()
        body += f'\n\n<!-- aiact-decision:{raw}.{signature} -->'
    if existing:
        if existing.get('body') != body:
            client.update_comment(repo, kind, existing['id'], body)
    else:
        client.reply(repo, number, kind, comment['id'], body)


def finish(client, config, repo, number, pr, check_id, snapshot, comments, event, payload, key):
    if not same_revision(client.pull(repo, number), pr['head']['sha'], pr['base']['sha']):
        client.finish_gate(repo, check_id, 'failure', 'PR changed while processing. A new review is required.')
        return
    if not snapshot or snapshot['status'] != 'complete':
        client.finish_gate(repo, check_id, 'failure', 'No verified complete review for the current head, base and policy. An authorized reviewer must post `/aiact rescan`.')
        return
    proofs, current = provenance(comments, client, key, event, payload)
    pending, outcomes = replay(config, snapshot, comments, client, repo, number, proofs)
    if event != 'pull_request_target':
        receipt(client, repo, number, event, payload, comments, outcomes, current, key)
    if not same_revision(client.pull(repo, number), pr['head']['sha'], pr['base']['sha']):
        client.finish_gate(repo, check_id, 'failure', 'PR changed while processing. A new review is required.')
        return
    summary = ('Awaiting acknowledgement or false-positive decision: '+', '.join('`'+fid+'`' for fid in pending)
               if pending else 'All current findings have an authorized acknowledgement or false-positive decision. Engineering review only, not a compliance certificate.')
    client.finish_gate(repo, check_id, 'failure' if pending else 'success', summary)
