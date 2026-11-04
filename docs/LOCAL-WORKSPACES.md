# Local workspaces and review API

The local app can host several separate workspaces in one installation. The
first account created for a workspace owns that workspace. Reviews, API keys and
usage records are filtered by its workspace ID. The legal corpus and active RAG
build are shared by this local installation.

This is local account separation for a single installation. It is not a hosted
identity service, team invitation system or production access-control setup.
The app binds to localhost by default.

## Account and session API

Create an account with a workspace name, email and password using
`POST /api/auth/register`, or sign in using `POST /api/auth/login`.
Passwords are stored as scrypt hashes. Browser sessions use an HTTP-only cookie
and expire after seven days. Logging out revokes the session.

## API keys

Sign in, create a named key in **API keys**, and copy it when it is shown. The
secret is only returned once. The database stores its SHA-256 hash, display
prefix and last four characters. A workspace can revoke its own keys. A key can
authenticate requests with:

```sh
curl http://localhost:8000/api/reviews \
  -H 'Authorization: Bearer actk_your_key'
```

Requests authenticated with a key are recorded with route, HTTP status and
measured elapsed milliseconds. The **API usage** screen shows recent records for
the signed-in workspace. Browser-cookie traffic is not counted as API-key use.

## Review jobs

The review API accepts work asynchronously. `POST /api/reviews` returns a job
ID and `queued` status. Poll `GET /api/reviews/{id}` to see progress and its
saved result. If the review asks a context question, post the answer to
`POST /api/reviews/{id}/answer`; the same review resumes against the RAG release
it started with. Use an `Idempotency-Key` header when retrying a start request
after a connection failure. Reusing the key with identical input returns the
same job; different input returns a conflict.

Jobs survive a process restart. The local database temporarily stores the
bounded review input so accepted queued work can resume after restart. Completed
review checkpoints retain the evidence and retrieval context needed to resume;
they do not store provider credentials. Do not put secrets in source code or
scenario text.

Every review endpoint requires a signed-in browser session or a workspace API
key. A workspace cannot list or open another workspace's jobs. API keys cannot
create or revoke API keys.

The local worker runs one review at a time because it shares the embedded RAG
index. SQLite is the default; PostgreSQL is supported for the same tables and
flow when configured. The application does not create external accounts or
publish data to a hosted dashboard.
