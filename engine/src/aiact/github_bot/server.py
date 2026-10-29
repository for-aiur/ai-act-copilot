"""Small signed-webhook service with one durable-job worker."""
import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading

from .config import BotConfig
from .github import AppAuth, BotError
from .service import Service
from .store import Store

EVENTS = {'pull_request', 'issue_comment', 'pull_request_review_comment', 'pull_request_review'}
IGNORED_EVENTS = {'ping', 'installation', 'installation_repositories', 'installation_target', 'meta'}


def accept(store, config, secret, delivery, event, signature, raw):
    expected = 'sha256='+hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not secret or not re.fullmatch(r'sha256=[0-9a-f]{64}', signature or '') or not hmac.compare_digest(signature, expected):
        raise BotError('invalid_signature')
    if not re.fullmatch(r'[A-Za-z0-9-]{1,100}', delivery or '') or event not in EVENTS | IGNORED_EVENTS:
        raise BotError('unsupported_delivery')
    if len(raw) > 1_000_000: raise BotError('webhook_body_budget')
    if event in IGNORED_EVENTS: return False
    try:
        payload = json.loads(raw)
        repo = payload['repository']['full_name'].lower()
        if repo not in config.repositories: raise BotError('repository_not_allowed')
        if not isinstance(payload.get('installation', {}).get('id'), int): raise BotError('installation_missing')
    except (ValueError, TypeError, KeyError, AttributeError):
        raise BotError('invalid_payload') from None
    return store.enqueue(delivery, event, payload)


def worker_once(store, service):
    job = store.claim()
    if not job: return False
    try:
        service.process(job['id'], job['event'], json.loads(job['payload']))
        store.finish(job['id'])
    except BotError as exc:
        store.finish(job['id'], str(exc))
    except Exception:
        # Never log request bodies, model outputs, credentials or raw tracebacks.
        store.finish(job['id'], 'bot_internal_error')
    return True


def make_server(host, port, store, config, secret):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, status, value):
            raw = json.dumps(value).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            self.reply(200 if self.path == '/healthz' else 404, {'service': 'AI Act Copilot', 'ready': self.path == '/healthz'})
        def do_POST(self):
            if self.path != '/webhooks/github': self.reply(404, {'error': 'not_found'}); return
            try:
                if self.headers.get('Transfer-Encoding'): raise BotError('invalid_payload')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1_000_000:
                    self.reply(413, {'error': 'webhook_body_budget'}); return
                self.connection.settimeout(10)
                raw = self.rfile.read(length)
                if len(raw) != length: raise BotError('invalid_payload')
                created = accept(store, config, secret, self.headers.get('X-GitHub-Delivery'),
                                 self.headers.get('X-GitHub-Event'), self.headers.get('X-Hub-Signature-256'), raw)
                self.reply(200 if self.headers.get('X-GitHub-Event') in IGNORED_EVENTS else 202, {'accepted': True, 'duplicate': not created})
            except BotError as exc:
                self.reply(401 if str(exc) == 'invalid_signature' else 400, {'error': str(exc)})
            except (ValueError, OSError):
                self.reply(400, {'error': 'invalid_request'})
    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aiact-bot')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve'); serve.add_argument('--config', type=Path, required=True)
    serve.add_argument('--host', default='127.0.0.1'); serve.add_argument('--port', type=int, default=8787)
    export = sub.add_parser('export'); export.add_argument('--database', type=Path, required=True)
    export.add_argument('--repo'); export.add_argument('--pr', type=int)
    args = parser.parse_args(argv)
    os.umask(0o077)
    if args.command == 'export':
        if not args.database.is_file(): parser.error('Database does not exist.')
        print(json.dumps(Store(args.database).export(args.repo, args.pr), indent=2)); return 0
    config = BotConfig.load(args.config)
    config.database = os.environ.get('AIACT_BOT_DATABASE', config.database)
    secret = os.environ.get('AIACT_BOT_WEBHOOK_SECRET', '')
    app_id = os.environ.get('AIACT_BOT_APP_ID', '')
    key_path = os.environ.get('AIACT_BOT_PRIVATE_KEY_PATH', '')
    key_bytes = None
    if os.environ.get('AIACT_BOT_PRIVATE_KEY_B64'):
        try: key_bytes = base64.b64decode(os.environ['AIACT_BOT_PRIVATE_KEY_B64'], validate=True)
        except ValueError: parser.error('Private-key environment value is not valid base64.')
    if len(secret) < 32 or not app_id.isdigit() or not (key_bytes or Path(key_path).is_file()):
        parser.error('Configure App ID, private-key file and a webhook secret of at least 32 characters.')
    store = Store(config.database); store.recover()
    service = Service(config, store, AppAuth(app_id, key_path, key_bytes).client)
    server = make_server(args.host, args.port, store, config, secret)
    stopping = threading.Event()
    def run_worker():
        while not stopping.is_set():
            if not worker_once(store, service): stopping.wait(0.5)
    thread = threading.Thread(target=run_worker, daemon=True); thread.start()
    try: server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt: pass
    finally: stopping.set(); server.server_close(); thread.join(timeout=5)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
