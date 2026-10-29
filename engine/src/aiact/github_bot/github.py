"""Bounded GitHub REST access. No PR checkout, shell hooks or remote URLs."""
import base64
import json
from pathlib import PurePosixPath
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class BotError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise BotError('github_redirect_rejected')


class GitHub:
    def __init__(self, token, bot_login):
        self.token, self.bot_login = token, bot_login
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.trees = {}
        self.requests = 0
        self.deadline = time.monotonic()+300

    def request(self, method, path, body=None):
        self.requests += 1
        if self.requests > 200: raise BotError('github_request_budget')
        remaining = self.deadline-time.monotonic()
        if remaining <= 0: raise BotError('github_job_deadline')
        if not path.startswith('/') or path.startswith('//'):
            raise BotError('github_path_invalid')
        request = Request('https://api.github.com'+path, method=method,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={'Authorization': 'Bearer '+self.token, 'Accept': 'application/vnd.github+json',
                                   'X-GitHub-Api-Version': '2026-03-10', 'Content-Type': 'application/json', 'User-Agent': 'Evros-AI-Act-Copilot'})
        try:
            with self.opener.open(request, timeout=min(20, remaining)) as response:
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise BotError('github_response_budget')
            return json.loads(raw) if raw else {}
        except HTTPError as error:
            raise BotError('github_http_'+str(error.code)) from None
        except (URLError, OSError, ValueError):
            raise BotError('github_unavailable') from None

    def pages(self, path, limit=30):
        result = []
        for page in range(1, limit+1):
            rows = self.request('GET', path+('&' if '?' in path else '?')+f'per_page=100&page={page}')
            if not isinstance(rows, list):
                raise BotError('github_list_invalid')
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise BotError('github_pagination_budget')

    def pull(self, repo, number):
        return self.request('GET', f'/repos/{repo}/pulls/{number}')

    def files(self, repo, number):
        return self.pages(f'/repos/{repo}/pulls/{number}/files')

    def comments(self, repo, number):
        return [('issue', item) for item in self.pages(f'/repos/{repo}/issues/{number}/comments')] + [
            ('review', item) for item in self.pages(f'/repos/{repo}/pulls/{number}/comments')] + [
            ('submission', item) for item in self.pages(f'/repos/{repo}/pulls/{number}/reviews')]

    def permission(self, repo, login):
        data = self.request('GET', f'/repos/{repo}/collaborators/{quote(login, safe="")}/permission')
        role = data.get('role_name')
        return role if role in {'read', 'triage', 'write', 'maintain', 'admin'} else data.get('permission', 'none')

    def file_bytes(self, repo, commit, path, max_bytes=100_000):
        parts = PurePosixPath(path).parts
        if not parts or path.startswith('/') or any(p in {'.', '..'} or '\\' in p or any(ord(c)<32 for c in p) for p in parts):
            raise BotError('source_path_invalid')
        key = (repo, commit)
        if key not in self.trees:
            self.trees[key] = self.request('GET', f'/repos/{repo}/git/commits/{commit}')['tree']['sha']
        tree = self.trees[key]
        for index, part in enumerate(parts):
            cache = (repo, tree, 'tree')
            if cache not in self.trees:
                data = self.request('GET', f'/repos/{repo}/git/trees/{tree}')
                if data.get('truncated'):
                    raise BotError('source_tree_truncated')
                self.trees[cache] = {entry['path']: entry for entry in data['tree']}
            entry = self.trees[cache].get(part)
            if not entry:
                raise BotError('source_missing')
            if index < len(parts)-1:
                if entry.get('mode') != '040000':
                    raise BotError('source_not_directory')
                tree = entry['sha']
            else:
                if entry.get('mode') not in {'100644', '100755'} or entry.get('type') != 'blob':
                    raise BotError('source_not_regular')
                if entry.get('size', max_bytes+1) > max_bytes:
                    raise BotError('source_byte_budget')
                blob = self.request('GET', f'/repos/{repo}/git/blobs/{entry["sha"]}')
                if blob.get('encoding') != 'base64' or blob.get('size', max_bytes+1) > max_bytes:
                    raise BotError('source_blob_invalid')
                try:
                    raw = base64.b64decode(blob['content'].replace('\n', ''), validate=True)
                except (ValueError, KeyError):
                    raise BotError('source_blob_invalid') from None
                if len(raw) > max_bytes:
                    raise BotError('source_byte_budget')
                return raw

    def create_comment(self, repo, number, body, head=None, path=None, line=None):
        if head and path and line:
            return self.request('POST', f'/repos/{repo}/pulls/{number}/comments',
                                {'body': body, 'commit_id': head, 'path': path, 'line': line, 'side': 'RIGHT'})
        return self.request('POST', f'/repos/{repo}/issues/{number}/comments', {'body': body})

    def update_comment(self, repo, kind, github_id, body):
        endpoint = 'pulls/comments' if kind == 'review' else 'issues/comments'
        return self.request('PATCH', f'/repos/{repo}/{endpoint}/{github_id}', {'body': body})

    def reply(self, repo, number, kind, comment_id, body):
        if kind == 'review':
            return self.request('POST', f'/repos/{repo}/pulls/{number}/comments/{int(comment_id)}/replies', {'body': body})
        return self.create_comment(repo, number, body)

    def create_gate(self, repo, number, head, name):
        external_id = f'aiact:{repo}:{number}'
        # Update one App-owned check per PR/head; avoid ambiguous duplicate checks.
        data = self.request('GET', f'/repos/{repo}/commits/{head}/check-runs?check_name={quote(name, safe="")}&filter=latest&per_page=100')
        rows = data.get('check_runs', [])
        if len(rows) >= 100:
            raise BotError('github_check_budget')
        existing = next((row for row in rows if row.get('external_id') == external_id and
                         (row.get('app', {}).get('slug') or '')+'[bot]' == self.bot_login), None)
        if existing:
            # Fail closed before reading potentially edited/deleted replies.
            self.finish_gate(repo, existing['id'], 'failure', 'Rechecking current review and acknowledgement state.')
            return existing['id']
        return self.request('POST', f'/repos/{repo}/check-runs', {
            'name': name, 'head_sha': head, 'status': 'in_progress',
            'external_id': external_id,
            'output': {'title': 'Reviewing acknowledgement state', 'summary': 'Waiting for a complete current review and authorized decisions.'}})['id']

    def finish_gate(self, repo, check_id, conclusion, summary):
        return self.request('PATCH', f'/repos/{repo}/check-runs/{int(check_id)}', {
            'status': 'completed', 'conclusion': conclusion,
            'output': {'title': 'AI Act Copilot acknowledgements', 'summary': summary}})


class AppAuth:
    def __init__(self, app_id, private_key_path=None, key_bytes=None):
        self.app_id, self.private_key_path, self.key_bytes = app_id, private_key_path, key_bytes

    def _app(self):
        try:
            import jwt
        except ImportError:
            raise BotError('github_app_dependency_missing') from None
        try:
            from pathlib import Path
            token = jwt.encode({'iat': int(time.time())-60, 'exp': int(time.time())+540, 'iss': str(self.app_id)},
                               (self.key_bytes if self.key_bytes is not None else Path(self.private_key_path).read_bytes()), algorithm='RS256')
        except (OSError, ValueError, jwt.PyJWTError):
            raise BotError('github_app_credentials_invalid') from None
        app = GitHub(token, '')
        info = app.request('GET', '/app')
        if str(info.get('id')) != str(self.app_id) or not re.fullmatch(r'[A-Za-z0-9-]+', info.get('slug', '')):
            raise BotError('github_app_identity_invalid')
        return app, info

    def client(self, installation, repository_id):
        app, info = self._app()
        auth = app.request('POST', f'/app/installations/{int(installation)}/access_tokens',
                           {'repository_ids': [int(repository_id)], 'permissions': {'contents': 'read', 'pull_requests': 'write', 'issues': 'read'}})
        return GitHub(auth['token'], info['slug']+'[bot]')

    def repository_client(self, repo, repository_id):
        app, info = self._app()
        installation = app.request('GET', f'/repos/{repo}/installation')['id']
        auth = app.request('POST', f'/app/installations/{int(installation)}/access_tokens', {
            'repository_ids': [int(repository_id)],
            'permissions': {'contents': 'read', 'pull_requests': 'write', 'issues': 'read', 'checks': 'write'}})
        return GitHub(auth['token'], info['slug']+'[bot]')
