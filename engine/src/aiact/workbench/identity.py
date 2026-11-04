"""Local users, workspaces, browser sessions and tenant API keys."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, delete, insert, select, update
from sqlalchemy.engine import make_url

metadata = MetaData()
schema = Table("aiact_identity_schema", metadata, Column("version", Integer, primary_key=True))
tenants = Table("aiact_tenants", metadata,
    Column("id", String(36), primary_key=True), Column("name", String(160), nullable=False),
    Column("created_at", String(40), nullable=False))
users = Table("aiact_users", metadata,
    Column("id", String(36), primary_key=True), Column("tenant_id", String(36), nullable=False, index=True),
    Column("email", String(320), nullable=False, unique=True), Column("password_hash", String(256), nullable=False),
    Column("created_at", String(40), nullable=False))
sessions = Table("aiact_browser_sessions", metadata,
    Column("token_hash", String(64), primary_key=True), Column("user_id", String(36), nullable=False, index=True),
    Column("expires_at", String(40), nullable=False), Column("created_at", String(40), nullable=False),
    Column("last_seen_at", String(40), nullable=False))
api_keys = Table("aiact_tenant_api_keys", metadata,
    Column("id", String(36), primary_key=True), Column("tenant_id", String(36), nullable=False, index=True),
    Column("created_by", String(36), nullable=False), Column("name", String(100), nullable=False),
    Column("key_hash", String(64), nullable=False, unique=True), Column("prefix", String(16), nullable=False),
    Column("last_four", String(4), nullable=False), Column("created_at", String(40), nullable=False),
    Column("last_used_at", String(40)), Column("revoked_at", String(40)))
api_usage = Table("aiact_tenant_api_usage", metadata,
    Column("id", String(36), primary_key=True), Column("tenant_id", String(36), nullable=False, index=True),
    Column("api_key_id", String(36), index=True), Column("route", String(200), nullable=False),
    Column("status_code", Integer, nullable=False), Column("elapsed_ms", Integer, nullable=False),
    Column("created_at", String(40), nullable=False))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${hashed.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class IdentityStore:
    """Database-agnostic local identity and tenant store."""
    def __init__(self, database_url: str, *, session_days=7):
        url = make_url(database_url)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Identity storage supports SQLite and PostgreSQL.")
        if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
            Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={"timeout": 15} if url.get_backend_name() == "sqlite" else {}, echo=False)
        metadata.create_all(self.engine)
        with self.engine.begin() as db:
            version = db.execute(select(schema.c.version)).scalar()
            if version is None:
                db.execute(insert(schema).values(version=1))
            elif version != 1:
                raise ValueError("Unsupported local identity schema version.")
        self.session_days = session_days

    @property
    def sqlite(self):
        return self.engine.dialect.name == "sqlite"

    def close(self):
        self.engine.dispose()

    def register(self, workspace: str, email: str, password: str):
        workspace, email = workspace.strip(), email.strip().casefold()
        if not 2 <= len(workspace) <= 160 or not 3 <= len(email) <= 320 or "@" not in email:
            raise ValueError("Enter a workspace name and a valid email address.")
        if not 12 <= len(password) <= 1024:
            raise ValueError("Password must contain 12 to 1024 characters.")
        tenant_id, user_id, created = str(uuid4()), str(uuid4()), _now()
        with self.engine.begin() as db:
            if db.execute(select(users.c.id).where(users.c.email == email)).first():
                raise ValueError("An account already exists for this email.")
            db.execute(insert(tenants).values(id=tenant_id, name=workspace, created_at=created))
            db.execute(insert(users).values(id=user_id, tenant_id=tenant_id, email=email,
                password_hash=_password_hash(password), created_at=created))
        return {"id": user_id, "tenant_id": tenant_id, "email": email, "workspace": workspace}

    def authenticate(self, email: str, password: str):
        email = email.strip().casefold()
        with self.engine.connect() as db:
            row = db.execute(select(users.c.id, users.c.tenant_id, users.c.email, users.c.password_hash,
                tenants.c.name.label("workspace")).join(tenants, users.c.tenant_id == tenants.c.id)
                .where(users.c.email == email)).mappings().first()
        if not row or not _verify_password(password, row["password_hash"]):
            return None
        return {"id": row["id"], "tenant_id": row["tenant_id"], "email": row["email"], "workspace": row["workspace"]}

    def create_session(self, user_id: str):
        raw = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as db:
            db.execute(insert(sessions).values(token_hash=_token_hash(raw), user_id=user_id,
                created_at=now.isoformat(), last_seen_at=now.isoformat(),
                expires_at=(now + timedelta(days=self.session_days)).isoformat()))
        return raw

    def user_for_session(self, raw: str | None):
        if not raw:
            return None
        token = _token_hash(raw)
        now = _now()
        with self.engine.begin() as db:
            row = db.execute(select(sessions.c.user_id, sessions.c.expires_at, users.c.tenant_id,
                users.c.email, tenants.c.name.label("workspace")).join(users, sessions.c.user_id == users.c.id)
                .join(tenants, users.c.tenant_id == tenants.c.id).where(sessions.c.token_hash == token)).mappings().first()
            if not row or row["expires_at"] <= now:
                db.execute(delete(sessions).where(sessions.c.token_hash == token))
                return None
            db.execute(update(sessions).where(sessions.c.token_hash == token).values(last_seen_at=now))
        return {"id": row["user_id"], "tenant_id": row["tenant_id"], "email": row["email"], "workspace": row["workspace"], "auth_type": "session"}

    def revoke_session(self, raw: str | None):
        if raw:
            with self.engine.begin() as db:
                db.execute(delete(sessions).where(sessions.c.token_hash == _token_hash(raw)))

    def create_api_key(self, tenant_id: str, user_id: str, name: str):
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("API key name must contain 1 to 100 characters.")
        raw = "actk_" + secrets.token_urlsafe(32)
        identity, created = str(uuid4()), _now()
        with self.engine.begin() as db:
            db.execute(insert(api_keys).values(id=identity, tenant_id=tenant_id, created_by=user_id,
                name=name, key_hash=_token_hash(raw), prefix=raw[:10], last_four=raw[-4:], created_at=created))
        return {"id": identity, "name": name, "key": raw, "prefix": raw[:10], "last_four": raw[-4:], "created_at": created}

    def authenticate_api_key(self, raw: str | None):
        if not raw or len(raw) > 128:
            return None
        key_hash, now = _token_hash(raw), _now()
        with self.engine.begin() as db:
            row = db.execute(select(api_keys.c.id, api_keys.c.tenant_id, users.c.id.label("user_id"),
                users.c.email, tenants.c.name.label("workspace")).join(users, api_keys.c.created_by == users.c.id)
                .join(tenants, api_keys.c.tenant_id == tenants.c.id)
                .where(api_keys.c.key_hash == key_hash, api_keys.c.revoked_at.is_(None))).mappings().first()
            if not row:
                return None
            db.execute(update(api_keys).where(api_keys.c.id == row["id"]).values(last_used_at=now))
        return {"id": row["user_id"], "tenant_id": row["tenant_id"], "email": row["email"],
            "workspace": row["workspace"], "auth_type": "api_key", "api_key_id": row["id"]}

    def list_api_keys(self, tenant_id: str):
        with self.engine.connect() as db:
            rows = db.execute(select(api_keys).where(api_keys.c.tenant_id == tenant_id)
                .order_by(api_keys.c.created_at.desc())).mappings()
            return [{k: row[k] for k in ("id", "name", "prefix", "last_four", "created_at", "last_used_at", "revoked_at")} for row in rows]

    def revoke_api_key(self, tenant_id: str, identity: str):
        with self.engine.begin() as db:
            result = db.execute(update(api_keys).where(api_keys.c.id == identity,
                api_keys.c.tenant_id == tenant_id, api_keys.c.revoked_at.is_(None)).values(revoked_at=_now()))
            return result.rowcount == 1

    def record_usage(self, user: dict, route: str, status_code: int, elapsed_ms: int):
        with self.engine.begin() as db:
            db.execute(insert(api_usage).values(id=str(uuid4()), tenant_id=user["tenant_id"],
                api_key_id=user.get("api_key_id"), route=route[:200], status_code=status_code,
                elapsed_ms=max(0, elapsed_ms), created_at=_now()))

    def list_usage(self, tenant_id: str, limit=100):
        with self.engine.connect() as db:
            rows = db.execute(select(api_usage).where(api_usage.c.tenant_id == tenant_id)
                .order_by(api_usage.c.created_at.desc()).limit(limit)).mappings()
            return [dict(row) for row in rows]
