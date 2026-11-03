"""Local-only corpus inspection and persistent scenario drafts, with no inference."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from aiact.corpus import validate_corpus
from aiact.providers import ReviewFailure


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    scenario: str = Field(min_length=1, max_length=12000)
    context: str = Field(default="", max_length=6000)
    source_ids: list[str] = Field(default_factory=list, max_length=50)
    corpus_checksum: str = Field(min_length=64, max_length=64)


def create_app(db_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI Act Copilot Workbench", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
    database = db_path or Path(os.environ.get("AIACT_WORKBENCH_DB", ".aiact-workbench/drafts.sqlite3"))

    @contextmanager
    def connect():
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
                yield connection
        finally:
            connection.close()

    def corpus():
        # Pin this foundation to the packaged subset, never an ambient user cache.
        return validate_corpus(json.loads(files("aiact").joinpath("data/corpus.json").read_text()))

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # No CORS: browsers use the same-origin Vite proxy. Reject cross-site writes.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            from urllib.parse import urlsplit
            if origin and (urlsplit(origin).netloc != request.headers.get("host") or urlsplit(origin).scheme != "http"):
                return JSONResponse({"detail": "Cross-origin writes are disabled."}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site writes are disabled."}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ReviewFailure)
    async def corpus_error(request, exc):
        return JSONResponse({"detail": "Packaged corpus failed validation. Reinstall the engine."}, status_code=503)

    @app.get("/api/health")
    def health():
        corpus()
        with connect() as db:
            db.execute("SELECT 1")
        return {"status": "ready", "inference": "disabled"}

    @app.get("/api/corpus")
    def get_corpus(q: str = Query(default="", max_length=200)):
        data = corpus()
        terms = q.casefold().split()
        sections = [s for s in data["sections"] if all(t in (s["title"] + " " + s["id"] + " " + s["text"]).casefold() for t in terms)]
        return {
            "domain": "AI Act", "coverage": "legacy_subset",
            "version": data["version"], "checksum": data["checksum"],
            "source_identity": data["source_identity"], "verified_at": data["verified_at"],
            "scope_limits": data["scope_limits"], "total": len(data["sections"]),
            "source_count": len({s["url"] for s in data["sections"]}),
            "sections": sections,
        }

    @app.get("/api/drafts")
    def list_drafts():
        with connect() as db:
            rows = db.execute("SELECT * FROM drafts ORDER BY created_at DESC, id DESC LIMIT 100").fetchall()
        return [json.loads(row["payload"]) | {"id": row["id"], "created_at": row["created_at"], "status": "draft"} for row in rows]

    @app.post("/api/drafts", status_code=201)
    def save_draft(draft: DraftInput):
        data = corpus()
        if draft.corpus_checksum != data["checksum"]:
            raise HTTPException(409, "Corpus changed. Reload before saving.")
        if len(set(draft.source_ids)) != len(draft.source_ids) or not set(draft.source_ids) <= {s["id"] for s in data["sections"]}:
            raise HTTPException(422, "Source references must be unique IDs from this corpus.")
        draft_id, created = str(uuid4()), datetime.now(timezone.utc).isoformat()
        payload = draft.model_dump() | {"corpus_version": data["version"]}
        with connect() as db:
            db.execute("INSERT INTO drafts VALUES (?, ?, ?)", (draft_id, json.dumps(payload), created))
        return payload | {"id": draft_id, "created_at": created, "status": "draft"}

    return app
