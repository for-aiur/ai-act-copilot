"""Local E2E: real scanner/storage/webhook, test-only model and GitHub transport."""
import copy
import hashlib
import hmac
import json
from pathlib import Path
import threading
from urllib.request import Request, urlopen

import pytest

from aiact.contracts import Coverage, ScanError, ScanResult
from aiact.corpus import load_corpus
from aiact.pipeline import scan
from aiact.github_bot.config import BotConfig
from aiact.github_bot.github import BotError, GitHub
from aiact.github_bot.server import accept, make_server, worker_once
from aiact.github_bot.service import Service, allowed_path, right_lines
from aiact.github_bot.store import Store

REPO='example/ai-review'
SOURCE='def shortlist_candidates(applications, suitability_model):\n    return suitability_model.predict(applications)\n'
SECRET='test-only-webhook-secret-never-use-in-production'
ROOT=Path(__file__).resolve().parents[2]


class StubModel:
    model='test-only';name='ollama'
    def __init__(self):self.calls=0;self.ai=False
    def generate_json(self,prompt,schema,timeout):
        self.calls+=1
        data=json.JSONDecoder().raw_decode(prompt.split('UNTRUSTED_DATA_JSON:\n')[1])[0]
        if 'source' in data:
            self.ai=any(s['potential_model_calls'] for s in data['source'])
            return {'ai_use':'evidenced' if self.ai else 'none','purpose':'Recruitment candidate shortlisting' if self.ai else 'Ordinary count',
                    'facts':[],'unknowns':['Selection use and reviewer unknown'] if self.ai else []}
        if not self.ai:return {'findings':[]}
        passage=next(p for p in data['official_passages'] if p['section_id']=='annex-iii-4-a')
        question=next(q for q in data['review_questions'] if q['id']=='recruitment_human_review')
        return {'findings':[{'title':'Recruitment selection context','explanation':'This model predicts applicant scores; intended deployment and the human decision process remain unknown.',
                            'kind':'context_question','priority':'high','evidence_id':'E1',
                            'citations':[{'section_id':passage['section_id'],'quote':passage['quote_options'][0]}],
                            'suggested_next_action':'Document how scores influence candidate selection.','context_question':question['question']}]}


class FakeGitHub:
    bot_login='evros-test[bot]'
    def __init__(self):
        self.head='a'*40;self.base='b'*40;self.source=SOURCE;self.remote=[];self.next_id=100
        self.updated=[];self.downloads=[];self.fork=False;self.other_files=[];self.ignore=None;self.reject_inline=False
    def pull(self,repo,number):return {'state':'open','head':{'sha':self.head,'repo':{'full_name':'fork/repo' if self.fork else REPO}},'base':{'sha':self.base}}
    def files(self,repo,number):
        patch='@@ -0,0 +1,'+str(len(self.source.splitlines()))+' @@\n'+'\n'.join('+'+line for line in self.source.splitlines())
        return [{'filename':'src/ranker.py','status':'modified','patch':patch}]+self.other_files
    def file_bytes(self,repo,commit,path,max_bytes=100000):
        self.downloads.append((commit,path))
        if path.endswith('.gitignore'):
            if self.ignore is not None and path=='.gitignore':return self.ignore.encode()
            raise BotError('source_missing')
        if path=='src/ranker.py':return self.source.encode()
        raise BotError('source_missing')
    def comments(self,*_):return copy.deepcopy(self.remote)
    def permission(self,repo,login):return {'dev':'write','admin':'admin','dpo':'read'}.get(login,'read')
    def create_comment(self,repo,number,body,head=None,path=None,line=None):
        if self.reject_inline and head:raise BotError('github_http_422')
        self.next_id+=1
        comment={'id':self.next_id,'body':body,'user':{'login':self.bot_login,'type':'Bot'},'updated_at':'2026-10-29T12:00:00Z',
                 'path':path,'line':line,'commit_id':head}
        self.remote.append(('review' if head else 'issue',comment));return copy.deepcopy(comment)
    def update_comment(self,repo,kind,github_id,body):
        self.updated.append(github_id)
        for _,comment in self.remote:
            if comment['id']==github_id:comment['body']=body;return copy.deepcopy(comment)
        raise BotError('github_http_404')


@pytest.fixture
def system(tmp_path):
    config=BotConfig([REPO],database=str(tmp_path/'review.sqlite3'),provider='ollama',model='test-only',
                     roles={'privacy_officer':['dpo'],'model_owner':[],'engineering':[]},routing={'annex-iii-4-a':['privacy_officer']})
    store=Store(config.database);github=FakeGitHub();contexts=[]
    def scanner(root,context):
        contexts.append(context)
        return scan(root,StubModel(),explicit_context=context)
    service=Service(config,store,lambda *_:github,scanner)
    return config,store,github,service,contexts


def payload(action='opened'):
    return {'action':action,'number':7,'repository':{'full_name':REPO,'id':42},'installation':{'id':123}}


def feedback(finding_id,command,actor='dpo',action='created',comment_id=500):
    return {**payload(action),'issue':{'number':7,'pull_request':{}},'sender':{'login':actor},
            'comment':{'id':comment_id,'body':f'/aiact {command} {finding_id} Reviewed dataset evidence.',
                       'user':{'login':actor,'type':'User'},'updated_at':'2026-10-29T13:00:00Z'}}


def signed(raw):return 'sha256='+hmac.new(SECRET.encode(),raw,hashlib.sha256).hexdigest()


def first(system):
    _,store,_,service,_=system
    service.process('first','pull_request',payload())
    return store.findings(REPO,7)[0]['id']


def test_signed_delivery_to_real_scan_pr_comments_and_durable_database(system):
    config,store,github,service,contexts=system;raw=json.dumps(payload()).encode()
    with pytest.raises(BotError,match='invalid_signature'):accept(store,config,SECRET,'one','pull_request','bad',raw)
    assert accept(store,config,SECRET,'one','pull_request',signed(raw),raw)
    assert not accept(store,config,SECRET,'one','pull_request',signed(raw),raw)
    assert worker_once(store,service);assert not worker_once(store,service)
    rows=store.findings(REPO,7);assert len(rows)==1 and rows[0]['status']=='needs_context'
    assert len(github.remote)==2 and github.remote[0][0]=='review'
    body=github.remote[0][1]['body'];assert '@dpo' in body and '#L1-L2' in body and 'annex' in body
    assert contexts==[''];assert all(commit==github.base for commit,path in github.downloads if path.endswith('.gitignore'))
    reopened=Store(config.database);assert reopened.findings(REPO,7)[0]['id']==rows[0]['id']
    output=reopened.export(REPO,7);assert output['history'] and output['runs'] and output['comments']


def test_role_permissions_objection_evidence_false_positive_and_comment_history(system):
    config,store,github,service,contexts=system;fid=first(system)
    # Empty pull_request metadata is still a valid issue-comment PR marker.
    event=feedback(fid,'false-positive',actor='outsider');event['issue']['pull_request']={'url':'https://api.github.com/example'}
    service.process('outsider','issue_comment',event);assert store.finding(fid)['status']=='needs_context'
    event=feedback(fid,'false-positive');event['issue']['pull_request']={'url':'x'}
    service.process('dismiss','issue_comment',event);assert store.finding(fid)['status']=='false_positive'
    service.process('dismiss','issue_comment',event)
    history=store.export(REPO,7)['history'];assert len([h for h in history if h['action']=='false-positive'])==1
    assert 'privacy_officer' in next(h['actor_roles'] for h in history if h['action']=='false-positive')
    for action,body in [('edited','Updated evidence'),('deleted','Updated evidence')]:
        changed=copy.deepcopy(event);changed['action']=action;changed['comment']['body']=body
        service.process(action,'issue_comment',changed)
    assert {c['action'] for c in store.export(REPO,7)['comments'] if c['github_id']==500}>={'created','edited','deleted'}
    event=feedback(fid,'evidence',actor='dev',comment_id=501);event['issue']['pull_request']={'url':'x'}
    service.process('evidence','issue_comment',event)
    assert len(contexts)==2 and 'Reviewer statements' in contexts[-1] and 'Reviewed dataset evidence' in contexts[-1]


def test_dismissal_is_scoped_to_evidence_and_line_shift_keeps_identity(system):
    _,store,github,service,_=system;fid=first(system)
    event=feedback(fid,'false-positive');event['issue']['pull_request']={'url':'x'}
    service.process('dismiss','issue_comment',event)
    github.head='c'*40;github.source='# unrelated line\n'+SOURCE
    service.process('shift','pull_request',payload('synchronize'))
    assert len(store.findings(REPO,7))==1 and store.finding(fid)['status']=='false_positive'
    github.head='d'*40;github.source=SOURCE.replace('predict(applications)','predict(applications[:10])')
    service.process('change','pull_request',payload('synchronize'))
    assert store.finding(fid)['status']=='needs_context'


@pytest.mark.parametrize('status',['failed','partial'])
def test_failed_or_partial_scans_never_close_existing_findings(system,status):
    _,store,github,service,_=system;fid=first(system);github.head='c'*40
    service.scanner=lambda *_:ScanResult(status=status,coverage=Coverage(scanned_files=['src/ranker.py']),errors=[ScanError(code='timeout',message='test-only timeout')])
    service.process('failed-scan','pull_request',payload('synchronize'))
    assert store.finding(fid)['status']=='needs_context'


def test_complete_rescan_resolves_and_reintroduced_finding_reopens(system):
    _,store,github,service,_=system;fid=first(system)
    github.head='c'*40;github.source='def shortlist_candidates(applications):\n    return len(applications)\n'
    github.other_files=[{'filename':'README.md','status':'modified'}]
    service.process('clear','pull_request',payload('synchronize'))
    assert store.finding(fid)['status']=='resolved'
    github.head='d'*40;github.source=SOURCE
    service.process('reintroduce','pull_request',payload('synchronize'))
    assert store.finding(fid)['status']=='needs_context'


def test_stale_scan_never_publishes_or_reconciles(system):
    _,store,github,service,_=system;original=service.scanner
    def stale(*args):
        result=original(*args);github.head='c'*40;return result
    service.scanner=stale;service.process('stale','pull_request',payload())
    assert not github.remote and not store.findings(REPO,7) and not store.export(REPO,7)['runs']


def test_retry_after_database_checkpoint_does_not_repeat_inference(system,monkeypatch):
    _,store,github,service,contexts=system;original=store.reconcile
    def fail(*_):raise RuntimeError('simulated process crash after scan checkpoint')
    monkeypatch.setattr(store,'reconcile',fail)
    with pytest.raises(RuntimeError):service.process('crash','pull_request',payload())
    monkeypatch.setattr(store,'reconcile',original)
    service.process('recover','pull_request',payload())
    assert len(contexts)==1 and len(github.remote)==2 and len(store.findings(REPO,7))==1
    service.process('duplicate','pull_request',payload())
    assert len(contexts)==1 and len(github.remote)==2


def test_unsafe_paths_forks_ignore_rules_and_inline_fallback(system):
    _,store,github,service,_=system
    assert not any(allowed_path(path) for path in ['../escape.py','/abs.py','src/.env.py','src/node_modules/x.py','src\\x.py'])
    github.fork=True
    with pytest.raises(BotError,match='fork_review_not_enabled'):first(system)
    github.fork=False;github.reject_inline=True;fid=first(system)
    assert store.finding(fid)['github_kind']=='issue'
    assert right_lines('@@ -1,2 +1,3 @@\n unchanged\n-old\n+new\n+extra')=={1,2,3}


def test_base_gitignore_is_honoured_without_running_pr_code(system,tmp_path):
    _,store,github,service,_=system
    marker=tmp_path/'must-not-exist';github.source=SOURCE+f'\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n'
    first(system);assert not marker.exists()
    github.head='c'*40;github.ignore='src/ranker.py\n';service.process('ignored','pull_request',payload('synchronize'))
    assert store.findings(REPO,7)[0]['status']=='needs_context'
    assert json.loads(store.export(REPO,7)['runs'][-1]['result'])['scan_result']['status']!='complete'


def test_github_blob_reader_rejects_symlink_and_never_follows_remote_source(monkeypatch):
    client=GitHub('test-only','bot[bot]')
    def request(method,path,body=None):
        if '/git/commits/' in path:return {'tree':{'sha':'t'}}
        return {'tree':[{'path':'x.py','mode':'120000','type':'blob','sha':'s','size':10}]}
    monkeypatch.setattr(client,'request',request)
    with pytest.raises(BotError,match='source_not_regular'):client.file_bytes(REPO,'a'*40,'x.py')


def test_http_webhook_ack_is_fast_and_durable(system):
    config,store,_,service,_=system
    server=make_server('127.0.0.1',0,store,config,SECRET)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        raw=json.dumps(payload()).encode();url=f'http://127.0.0.1:{server.server_port}/webhooks/github'
        request=Request(url,data=raw,headers={'X-GitHub-Delivery':'http-test','X-GitHub-Event':'pull_request','X-Hub-Signature-256':signed(raw)})
        with urlopen(request,timeout=5) as response:assert response.status==202
        assert not store.findings(REPO,7)  # HTTP does not wait for model generation.
        assert worker_once(store,service) and store.findings(REPO,7)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)


def test_app_auth_signs_jwt_and_scopes_token_to_one_repository(tmp_path,monkeypatch):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from aiact.github_bot.github import AppAuth
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    path=tmp_path/'app.pem';path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    requests=[]
    def request(self,method,path,body=None):
        claims=jwt.decode(self.token,key.public_key(),algorithms=['RS256'],issuer='123')
        assert claims['exp']-claims['iat']<=600
        requests.append((method,path,body))
        return {'id':123,'slug':'evros-test'} if path=='/app' else {'token':'test-installation-token'}
    monkeypatch.setattr(GitHub,'request',request)
    client=AppAuth('123',path).client(456,42)
    assert client.bot_login=='evros-test[bot]' and client.token=='test-installation-token'
    assert requests[-1][2]=={'repository_ids':[42],'permissions':{'contents':'read','pull_requests':'write','issues':'read'}}


def test_config_requires_cloud_optin_and_explicit_user_lists():
    with pytest.raises(ValueError):BotConfig([REPO])
    with pytest.raises(ValueError):BotConfig([REPO],provider='ollama',roles={'privacy_officer':'dpo'})
    with pytest.raises(ValueError):BotConfig([REPO],provider='ollama',roles={'privacy_officer':['@dpo']})
    config=BotConfig([REPO],provider='gemini',cloud_review=True)
    assert config.required_roles({'citations':[{'section_id':'article-14-4'}]})==['engineering']


def test_signed_ping_ack_and_repository_allowlist(system):
    config,store,_,_,_=system
    raw=b'{"zen":"test-only"}'
    assert not accept(store,config,SECRET,'ping-id','ping',signed(raw),raw)
    other=payload();other['repository']['full_name']='outside/repo';raw=json.dumps(other).encode()
    with pytest.raises(BotError,match='repository_not_allowed'):accept(store,config,SECRET,'other','pull_request',signed(raw),raw)


def test_rendering_neutralises_model_mentions_and_markdown_injection(system):
    from aiact.github_bot.service import render_finding
    config,store,_,_,_=system;fid=first(system);row=store.finding(fid)
    item=json.loads(row['payload']);item['title']='@outside [run](command:evil) <script>'
    item['evidence']['quote']='```\n@outside\n```';row['payload']=json.dumps(item)
    body=render_finding(row,config)
    assert '@outside [run]' not in body and '\\[run\\]' in body and '&lt;script&gt;' in body
    assert '````python' in body and body.count('````')==2
    assert '@dpo' in body


def test_review_command_can_resolve_done_and_reopen_with_audited_roles(system):
    _,store,_,service,_=system;fid=first(system)
    for command,status in [('objection','disputed'),('done','resolved'),('reopen','needs_context')]:
        event=feedback(fid,command,comment_id=600+len(command))
        service.process(command,'issue_comment',event)
        assert store.finding(fid)['status']==status
    assert all(h['actor']=='dpo' for h in store.export(REPO,7)['history'] if h['action'] in {'objection','resolve','reopen'})


def test_dashboard_export_keeps_reviewer_text_and_sorts_review_priority(system):
    _,store,_,service,_=system;fid=first(system)
    service.process('evidence','issue_comment',feedback(fid,'evidence'))
    exported=store.export(REPO,7)
    assert exported['dashboard_findings'][0]['priority']=='high'
    assert any('Reviewed dataset evidence' in h['body'] for h in exported['history'])
    assert any('Reviewed dataset evidence' in c['body'] for c in exported['comments'])


def test_missing_model_credentials_produce_failed_pr_summary_not_silent_job_error(system,monkeypatch):
    config,store,github,_,_=system
    config.provider='gemini';config.model='gemini-3.1-flash-lite';config.cloud_review=True
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    service=Service(config,store,lambda *_:github)
    service.process('no-key','pull_request',payload())
    assert not store.findings(REPO,7)
    assert any('credentials' in comment['body'] and 'review failed' in comment['body'] for _,comment in github.remote)


def test_recovering_a_running_job_preserves_attempt_bounds(system):
    _,store,_,_,_=system
    store.enqueue('interrupted','pull_request',payload())
    for _ in range(3):
        assert store.claim()['id']=='interrupted'
        store.recover()
    assert store.claim() is None
    assert store.export(REPO,7)['jobs'][0]['state']=='failed'


def test_github_client_deadline_and_status_errors_do_not_leak_credentials(monkeypatch):
    import time
    from urllib.error import HTTPError
    client=GitHub('test-private-token','test[bot]')
    client.deadline=time.monotonic()-1
    with pytest.raises(BotError,match='github_job_deadline'):client.request('GET','/app')
    client.deadline=time.monotonic()+20
    def denied(*args,**kwargs):raise HTTPError('https://example.test/test-private-token',403,'test-private-token',{},None)
    monkeypatch.setattr(client.opener,'open',denied)
    with pytest.raises(BotError) as caught:client.request('GET','/app')
    assert str(caught.value)=='github_http_403' and 'test-private-token' not in str(caught.value)


def test_retargeted_base_invalidates_cached_diff_and_restarts_review(system):
    _,_,github,service,contexts=system;first(system)
    github.base='e'*40
    service.process('retarget','pull_request',payload('edited'))
    assert len(contexts)==2


def test_same_text_edits_from_distinct_deliveries_keep_both_events(system):
    _,store,_,service,_=system;fid=first(system)
    event=feedback(fid,'evidence',action='edited')
    service.process('edit-one','issue_comment',event)
    event['sender']['login']='admin'
    service.process('edit-two','issue_comment',event)
    rows=[c for c in store.export(REPO,7)['comments'] if c['action']=='edited']
    assert len(rows)==2 and {c['event_actor'] for c in rows}=={'dpo','admin'}


def test_non_ascii_signature_is_rejected_without_processing(system):
    config,store,_,_,_=system
    with pytest.raises(BotError,match='invalid_signature'):
        accept(store,config,SECRET,'invalid','pull_request','sha256=é',b'{}')
