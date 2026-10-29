"""Durable SQLite jobs, review state and append-only history."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS deliveries (
 id TEXT PRIMARY KEY, event TEXT NOT NULL, payload TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
 available REAL NOT NULL DEFAULT 0, updated TEXT NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, repo TEXT NOT NULL, pr INTEGER NOT NULL, head TEXT NOT NULL,
 cache_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL, result TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings (
 id TEXT PRIMARY KEY, repo TEXT NOT NULL, pr INTEGER NOT NULL, path TEXT NOT NULL,
 status TEXT NOT NULL, priority TEXT NOT NULL, evidence_hash TEXT NOT NULL,
 policy_hash TEXT NOT NULL, head TEXT NOT NULL, payload TEXT NOT NULL, roles TEXT NOT NULL,
 github_id INTEGER, github_kind TEXT, published_body TEXT, manual_state INTEGER NOT NULL DEFAULT 0,
 created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history (
 id INTEGER PRIMARY KEY, finding_id TEXT NOT NULL REFERENCES findings(id),
 event_key TEXT NOT NULL UNIQUE, action TEXT NOT NULL, actor TEXT NOT NULL,
 body TEXT NOT NULL, head TEXT, actor_roles TEXT NOT NULL DEFAULT '[]', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS comments (
 id INTEGER PRIMARY KEY, repo TEXT NOT NULL, pr INTEGER NOT NULL, kind TEXT NOT NULL,
 github_id INTEGER NOT NULL, parent_id INTEGER, actor TEXT NOT NULL, body TEXT NOT NULL,
 action TEXT NOT NULL, source_time TEXT NOT NULL, received TEXT NOT NULL, revision TEXT NOT NULL UNIQUE,
 event_actor TEXT, path TEXT, line INTEGER, commit_sha TEXT, delivery_id TEXT);
CREATE INDEX IF NOT EXISTS comments_pr ON comments(repo,pr,source_time,id);
CREATE INDEX IF NOT EXISTS findings_pr ON findings(repo,pr,status);
CREATE VIEW IF NOT EXISTS dashboard_findings AS
 SELECT id,repo,pr,path,status,priority,head,roles,created,updated,payload FROM findings
 ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, updated DESC;
'''


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            additions = {'findings': {'manual_state': 'INTEGER NOT NULL DEFAULT 0'},
                         'history': {'actor_roles': "TEXT NOT NULL DEFAULT '[]'"},
                         'comments': {'event_actor': 'TEXT', 'path': 'TEXT', 'line': 'INTEGER', 'commit_sha': 'TEXT', 'delivery_id': 'TEXT'}}
            for table, columns in additions.items():
                existing = {row['name'] for row in db.execute('PRAGMA table_info('+table+')')}
                for column, definition in columns.items():
                    if column not in existing: db.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+definition)
            db.execute('PRAGMA user_version=1')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, delivery, event, payload):
        with self.connect() as db:
            return db.execute('INSERT OR IGNORE INTO deliveries(id,event,payload,updated) VALUES(?,?,?,?)',
                              (delivery, event, encoded(payload), now())).rowcount == 1

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE deliveries SET state=CASE WHEN attempts>=3 THEN 'failed' ELSE 'queued' END, error='interrupted' WHERE state='running'")

    def claim(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM deliveries WHERE state='queued' AND available<=? ORDER BY rowid LIMIT 1", (time.time(),)).fetchone()
            if row:
                db.execute("UPDATE deliveries SET state='running',attempts=attempts+1,updated=? WHERE id=?", (now(), row['id']))
                return dict(row)

    def finish(self, delivery, error=None):
        with self.connect() as db:
            row = db.execute('SELECT attempts FROM deliveries WHERE id=?', (delivery,)).fetchone()
            retry = error is not None and row['attempts'] < 3
            db.execute('UPDATE deliveries SET state=?,error=?,available=?,updated=? WHERE id=?',
                       ('queued' if retry else 'failed' if error else 'done', error, time.time()+10, now(), delivery))

    def archive_comment(self, repo, pr, kind, comment, action='snapshot', event_actor=None, delivery_id=None):
        actor = comment.get('user', {}).get('login', 'unknown')
        stamp = comment.get('updated_at') or comment.get('submitted_at') or comment.get('created_at') or now()
        body = comment.get('body') or ''
        revision = digest([repo, kind, comment['id'], stamp, action, body, delivery_id])
        with self.connect() as db:
            db.execute('''INSERT OR IGNORE INTO comments(repo,pr,kind,github_id,parent_id,actor,body,action,source_time,received,revision,event_actor,path,line,commit_sha,delivery_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (repo, pr, kind, comment['id'], comment.get('in_reply_to_id'), actor, body, action, stamp, now(), revision, event_actor or actor, comment.get('path'), comment.get('line') or comment.get('original_line'), comment.get('commit_id'), delivery_id))

    def finding(self, finding_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM findings WHERE id=?', (finding_id,)).fetchone()
            return dict(row) if row else None

    def findings(self, repo, pr):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM dashboard_findings WHERE repo=? AND pr=?', (repo, pr))]

    def run(self, cache_key):
        with self.connect() as db:
            row = db.execute('SELECT * FROM runs WHERE cache_key=?', (cache_key,)).fetchone()
            return dict(row) if row else None

    def save_run(self, run_id, repo, pr, head, cache_key, result):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?,?,?,?)',
                       (run_id, repo, pr, head, cache_key, result['scan_result']['status'], encoded(result), now()))

    def reconcile(self, repo, pr, head, policy_hash, records, complete_paths, run_id):
        seen = {record['id'] for record in records}
        with self.connect() as db:
            for item in records:
                old = db.execute('SELECT * FROM findings WHERE id=?', (item['id'],)).fetchone()
                status = 'needs_context' if item['payload']['kind'] == 'context_question' else 'open'
                if old and old['manual_state'] and old['evidence_hash'] == item['evidence_hash'] and old['policy_hash'] == policy_hash:
                    status = old['status'] if old['status'] in {'false_positive', 'resolved', 'disputed'} else status
                values = (item['id'], repo, pr, item['payload']['evidence']['path'], status, item['payload']['priority'],
                          item['evidence_hash'], policy_hash, head, encoded(item['payload']), encoded(item['roles']), now(), now())
                db.execute('''INSERT INTO findings(id,repo,pr,path,status,priority,evidence_hash,policy_hash,head,payload,roles,created,updated)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                           status=excluded.status,priority=excluded.priority,evidence_hash=excluded.evidence_hash,
                           policy_hash=excluded.policy_hash,head=excluded.head,payload=excluded.payload,roles=excluded.roles,updated=excluded.updated''', values)
                manual = int(bool(old and old['manual_state'] and old['evidence_hash'] == item['evidence_hash'] and old['policy_hash'] == policy_hash))
                db.execute('UPDATE findings SET manual_state=? WHERE id=?', (manual, item['id']))
                db.execute('INSERT OR IGNORE INTO history(finding_id,event_key,action,actor,body,head,created) VALUES(?,?,?,?,?,?,?)',
                           (item['id'], run_id+':'+item['id'], 'observed:'+status, 'engine', '', head, now()))
            for old in db.execute('SELECT * FROM findings WHERE repo=? AND pr=?', (repo, pr)).fetchall():
                if old['id'] not in seen and old['path'] in complete_paths and old['status'] not in {'resolved', 'false_positive'}:
                    db.execute("UPDATE findings SET status='resolved',manual_state=0,head=?,updated=? WHERE id=?", (head, now(), old['id']))
                    db.execute('INSERT OR IGNORE INTO history(finding_id,event_key,action,actor,body,head,created) VALUES(?,?,?,?,?,?,?)',
                               (old['id'], run_id+':'+old['id'], 'scan_not_raised', 'engine', 'Not raised in the latest complete scan; not a compliance determination.', head, now()))

    def decision(self, finding_id, event_key, action, actor, body, actor_roles=None):
        states = {'objection': 'disputed', 'false-positive': 'false_positive', 'resolve': 'resolved', 'reopen': 'needs_context'}
        with self.connect() as db:
            row = db.execute('SELECT head FROM findings WHERE id=?', (finding_id,)).fetchone()
            if not row:
                return
            inserted = db.execute('INSERT OR IGNORE INTO history(finding_id,event_key,action,actor,body,head,actor_roles,created) VALUES(?,?,?,?,?,?,?,?)',
                                  (finding_id, event_key, action, actor, body, row['head'], encoded(actor_roles or []), now())).rowcount
            if inserted and action in states:
                db.execute('UPDATE findings SET status=?,manual_state=1,updated=? WHERE id=?', (states[action], now(), finding_id))

    def feedback(self, repo, pr):
        with self.connect() as db:
            rows = db.execute('''SELECT h.finding_id,h.action,h.actor,h.actor_roles,h.body,h.created FROM history h
                              JOIN findings f ON f.id=h.finding_id WHERE f.repo=? AND f.pr=?
                              AND h.actor!='engine' ORDER BY h.id DESC LIMIT 20''', (repo, pr)).fetchall()
            return [dict(row) for row in reversed(rows)]

    def published(self, finding_id, github_id, kind, body):
        with self.connect() as db:
            db.execute('UPDATE findings SET github_id=?,github_kind=?,published_body=? WHERE id=?', (github_id, kind, body, finding_id))

    def export(self, repo=None, pr=None):
        with self.connect() as db:
            where, args = [], []
            if repo: where.append('repo=?'); args.append(repo)
            if pr is not None: where.append('pr=?'); args.append(pr)
            clause = ' WHERE '+' AND '.join(where) if where else ''
            output = {table: [dict(row) for row in db.execute('SELECT * FROM '+table+clause+(' ORDER BY source_time,id' if table=='comments' else ''), args)]
                      for table in ('dashboard_findings', 'runs', 'comments')}
            ids = [row['id'] for row in output['dashboard_findings']]
            output['history'] = [dict(row) for row in db.execute('SELECT * FROM history WHERE finding_id IN ('+','.join('?' for _ in ids)+') ORDER BY created,id', ids)] if ids else []
            jobs = []
            for row in db.execute('SELECT * FROM deliveries ORDER BY updated,id'):
                payload = json.loads(row['payload'])
                target_repo = payload.get('repository', {}).get('full_name', '').lower()
                target_pr = payload.get('number') or payload.get('pull_request', {}).get('number') or payload.get('issue', {}).get('number')
                if repo and target_repo != repo: continue
                if pr is not None and target_pr != pr: continue
                jobs.append({key: row[key] for key in ('id','event','state','attempts','updated','error')})
            output['jobs'] = jobs
            return output
