"""Versioned SQL storage. SQLite locally; PostgreSQL selected explicitly by URL."""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, insert, select, text
from sqlalchemy.engine import make_url

from .contracts import Snapshot

metadata = MetaData()
schema = Table("rag_schema", metadata, Column("version", Integer, primary_key=True))
snapshots = Table("rag_snapshots", metadata, Column("id", String(64), primary_key=True), Column("domain", String(80), nullable=False), Column("payload", Text, nullable=False))
documents = Table("rag_documents", metadata, Column("snapshot_id", String(64), primary_key=True), Column("id", String(160), primary_key=True), Column("payload", Text, nullable=False))
chunks = Table("rag_chunks", metadata, Column("snapshot_id", String(64), primary_key=True), Column("id", String(200), primary_key=True), Column("document_id", String(160), nullable=False), Column("payload", Text, nullable=False))
sources = Table("rag_sources", metadata, Column("snapshot_id", String(64), primary_key=True), Column("hash", String(64), primary_key=True))
links = Table("rag_links", metadata, Column("snapshot_id", String(64), primary_key=True), Column("chunk_id", String(200), primary_key=True), Column("target_id", String(160), primary_key=True))
releases = Table("rag_releases", metadata, Column("id", String(64), primary_key=True), Column("domain", String(80), nullable=False), Column("snapshot_id", String(64), nullable=False), Column("payload", Text, nullable=False))
pointers = Table("rag_pointers", metadata, Column("domain", String(80), primary_key=True), Column("name", String(20), primary_key=True), Column("release_id", String(64), nullable=False))
records = Table("rag_records", metadata, Column("category", String(40), primary_key=True), Column("id", String(80), primary_key=True), Column("revision", Integer, primary_key=True), Column("domain", String(80), nullable=False), Column("created_at", String(40), nullable=False), Column("payload", Text, nullable=False))

removed = Table("rag_removed_releases", metadata, Column("release_id", String(64), primary_key=True))


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, database_url: str):
        url = make_url(database_url)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Unsupported storage backend")
        if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={"timeout": 15} if url.get_backend_name() == "sqlite" else {}, echo=False)
        if self.sqlite:
            with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text("PRAGMA journal_mode=WAL"))
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            version = connection.execute(select(schema.c.version)).scalar()
            if version is None:
                connection.execute(insert(schema).values(version=1))
            elif version != 1:
                raise ValueError("Unsupported database schema version; explicit migration required")
            if self.sqlite:
                connection.execute(text("PRAGMA journal_mode=WAL"))
                connection.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(snapshot_id UNINDEXED, chunk_id UNINDEXED, title, body, tokenize='unicode61')"))
            else:
                connection.execute(text("CREATE INDEX IF NOT EXISTS rag_documents_domain_index ON rag_documents(snapshot_id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS rag_chunks_fts_index ON rag_chunks USING GIN (to_tsvector('english', CAST(payload AS jsonb)->>'text'))"))

    @property
    def sqlite(self):
        return self.engine.dialect.name == "sqlite"

    def close(self):
        self.engine.dispose()

    def put_snapshot(self, snapshot: Snapshot):
        payload = snapshot.model_dump_json()
        with self.engine.begin() as db:
            existing = db.execute(select(snapshots.c.payload).where(snapshots.c.id == snapshot.snapshot_id)).scalar()
            if existing is not None:
                if Snapshot.model_validate_json(existing) != snapshot:
                    raise ValueError("Snapshot identity collision; immutable data cannot be overwritten")
                return
            db.execute(insert(snapshots).values(id=snapshot.snapshot_id, domain=snapshot.domain_id, payload=payload))
            db.execute(insert(documents), [{"snapshot_id": snapshot.snapshot_id, "id": d.id, "payload": d.model_dump_json()} for d in snapshot.documents])
            db.execute(insert(chunks), [{"snapshot_id": snapshot.snapshot_id, "id": c.id, "document_id": c.document_id, "payload": c.model_dump_json()} for c in snapshot.chunks])
            db.execute(insert(sources), [{"snapshot_id": snapshot.snapshot_id, "hash": h} for h in snapshot.source_hashes])
            references = [{"snapshot_id": snapshot.snapshot_id, "chunk_id": c.id, "target_id": ref} for c in snapshot.chunks for ref in c.references]
            if references:
                db.execute(insert(links), references)
            if self.sqlite:
                db.execute(text("INSERT INTO rag_fts(snapshot_id,chunk_id,title,body) VALUES (:s,:c,:t,:b)"),
                    [{"s": snapshot.snapshot_id, "c": c.id, "t": c.title, "b": c.text} for c in snapshot.chunks])

    def snapshot(self, identity: str) -> Snapshot:
        with self.engine.connect() as db:
            payload = db.execute(select(snapshots.c.payload).where(snapshots.c.id == identity)).scalar_one()
        return Snapshot.model_validate_json(payload)

    def put_release(self, manifest: dict):
        with self.engine.begin() as db:
            existing = db.execute(select(releases.c.payload).where(releases.c.id == manifest["rag_release_id"])).scalar()
            if existing is not None:
                if json.loads(existing) != manifest:
                    raise ValueError("Immutable release identity collision")
                return
            db.execute(insert(releases).values(id=manifest["rag_release_id"], domain=manifest["domain_id"], snapshot_id=manifest["snapshot_id"], payload=encode(manifest)))

    def release(self, identity: str) -> dict:
        with self.engine.connect() as db:
            return json.loads(db.execute(select(releases.c.payload).where(releases.c.id == identity)).scalar_one())

    def list_releases(self, domain: str):
        with self.engine.connect() as db:
            return [json.loads(row[0]) for row in db.execute(select(releases.c.payload).where(releases.c.domain == domain, ~releases.c.id.in_(select(removed.c.release_id))))]

    def activate(self, domain: str, identity: str, *, promotion: dict | None = None):
        manifest = self.release(identity)
        with self.engine.connect() as db:
            if db.execute(select(removed.c.release_id).where(removed.c.release_id == identity)).scalar():
                raise ValueError("Candidate was removed. Rebuild it before activating.")
        if manifest["domain_id"] != domain:
            raise ValueError("Release belongs to a different domain")
        with self.engine.begin() as db:
            if promotion is not None:
                from uuid import uuid4
                db.execute(insert(records).values(category="promotion", id=uuid4().hex, revision=1, domain=domain,
                    created_at=datetime.now(timezone.utc).isoformat(), payload=encode(promotion)))
            active = db.execute(select(pointers.c.release_id).where(pointers.c.domain == domain, pointers.c.name == "active")).scalar()
            if active == identity:
                return
            for name, value in [("previous", active), ("active", identity)]:
                if value:
                    db.execute(pointers.delete().where(pointers.c.domain == domain, pointers.c.name == name))
                    db.execute(insert(pointers).values(domain=domain, name=name, release_id=value))

    def removal_blockers(self, identity, db=None):
        if db is None:
            with self.engine.connect() as connection:
                return self.removal_blockers(identity, connection)
        blockers = []
        if db.execute(select(pointers.c.domain).where(pointers.c.release_id == identity, pointers.c.name == "active")).first():
            blockers.append("Active RAG: select another version first.")
        def refers(value):
            if isinstance(value, dict):
                return value.get("rag_release_id") == identity or any(refers(v) for v in value.values())
            return isinstance(value, list) and any(refers(v) for v in value)
        counts = {}
        for category, payload in db.execute(select(records.c.category, records.c.payload)):
            if refers(json.loads(payload)):
                counts[category] = counts.get(category, 0) + 1
        blockers.extend(f"Used by {count} saved {category} record(s)." for category, count in sorted(counts.items()))
        return blockers

    def remove_release(self, identity, domain):
        with self.engine.begin() as db:
            actual_domain = db.execute(select(releases.c.domain).where(releases.c.id == identity)).scalar()
            if actual_domain != domain:
                raise ValueError("Candidate not found in this collection.")
            blockers = self.removal_blockers(identity, db)
            if blockers:
                raise ValueError(" ".join(blockers))
            if not db.execute(select(removed.c.release_id).where(removed.c.release_id == identity)).scalar():
                db.execute(insert(removed).values(release_id=identity))
            db.execute(pointers.delete().where(pointers.c.release_id == identity, pointers.c.name == "previous"))

    def restore_release(self, identity):
        with self.engine.begin() as db:
            db.execute(removed.delete().where(removed.c.release_id == identity))

    def pointer(self, domain: str, name="active"):
        with self.engine.connect() as db:
            return db.execute(select(pointers.c.release_id).where(pointers.c.domain == domain, pointers.c.name == name)).scalar()

    def append(self, category: str, identity: str, domain: str, payload: dict, revision=1):
        # A primary-key conflict is explicit. Revisions are never updated in place.
        with self.engine.begin() as db:
            db.execute(insert(records).values(category=category, id=identity, revision=revision, domain=domain,
                created_at=datetime.now(timezone.utc).isoformat(), payload=encode(payload)))

    def list_records(self, category: str, domain: str, limit=100):
        with self.engine.connect() as db:
            rows = db.execute(select(records).where(records.c.category == category, records.c.domain == domain).order_by(records.c.created_at.desc()).limit(limit)).mappings()
            return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]

    def record(self, category: str, identity: str, revision: int):
        with self.engine.connect() as db:
            payload = db.execute(select(records.c.payload).where(records.c.category == category, records.c.id == identity, records.c.revision == revision)).scalar_one()
            return json.loads(payload)
