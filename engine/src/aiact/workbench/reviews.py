"""Tenant-scoped durable review jobs and the single local worker."""
from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url

from aiact.contracts import ReviewSession
from .identity import IdentityStore

metadata = MetaData()
schema = Table("aiact_review_schema", metadata, Column("version", Integer, primary_key=True))
jobs = Table("aiact_review_jobs", metadata,
    Column("id", String(36), primary_key=True), Column("tenant_id", String(36), nullable=False, index=True),
    Column("owner_id", String(36), nullable=False), Column("idempotency_key", String(128)),
    Column("request_hash", String(64), nullable=False), Column("status", String(24), nullable=False, index=True),
    Column("attempts", Integer, nullable=False), Column("request_payload", Text, nullable=False),
    Column("session_payload", Text), Column("answer_payload", Text), Column("error", Text),
    Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False),
    UniqueConstraint("tenant_id", "idempotency_key"))
events = Table("aiact_review_job_events", metadata,
    Column("job_id", String(36), primary_key=True), Column("revision", Integer, primary_key=True),
    Column("type", String(32), nullable=False), Column("created_at", String(40), nullable=False),
    Column("payload", Text, nullable=False), UniqueConstraint("job_id", "revision"))


def _now():
    return datetime.now(timezone.utc).isoformat()


class IdempotencyConflict(ValueError):
    pass


class ReviewJobRepository:
    def __init__(self, database_url: str):
        url = make_url(database_url)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Review jobs support SQLite or PostgreSQL.")
        if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
            Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={"timeout": 15} if url.get_backend_name() == "sqlite" else {}, echo=False)
        metadata.create_all(self.engine)
        with self.engine.begin() as db:
            version = db.execute(select(schema.c.version)).scalar()
            if version is None:
                db.execute(insert(schema).values(version=1))
            elif version != 1:
                raise ValueError("Unsupported review-job schema version.")

    def close(self):
        self.engine.dispose()

    def _event(self, db, identity, kind, payload=None):
        revision = (db.execute(select(events.c.revision).where(events.c.job_id == identity)
            .order_by(events.c.revision.desc()).limit(1)).scalar() or 0) + 1
        db.execute(insert(events).values(job_id=identity, revision=revision, type=kind,
            created_at=_now(), payload=json.dumps(payload or {}, sort_keys=True)))

    def _row(self, db, row, *, include_events=True):
        result = dict(row)
        result["request"] = json.loads(result.pop("request_payload"))
        result["session"] = ReviewSession.model_validate_json(result.pop("session_payload")) if result.get("session_payload") else None
        if result.get("error"):
            result["error"] = json.loads(result["error"])
        result["answer"] = json.loads(result.pop("answer_payload")) if result.get("answer_payload") else None
        result["events"] = [{"revision": e["revision"], "type": e["type"], "created_at": e["created_at"],
            "details": json.loads(e["payload"])} for e in db.execute(select(events).where(events.c.job_id == result["id"])
                .order_by(events.c.revision)).mappings()] if include_events else []
        trace = next((event["details"] for event in reversed(result["events"]) if event["details"].get("trace_id")), {})
        result["trace_id"], result["trace_url"] = trace.get("trace_id"), trace.get("trace_url")
        result["timings"] = trace.get("timings", [])
        result["retrieval_request"] = trace.get("retrieval_request")
        result["sources"] = trace.get("sources", [])
        return result

    def get(self, identity: str, tenant_id: str | None=None):
        with self.engine.connect() as db:
            query = select(jobs).where(jobs.c.id == identity)
            if tenant_id:
                query = query.where(jobs.c.tenant_id == tenant_id)
            row = db.execute(query).mappings().first()
            return self._row(db, row) if row else None

    def list_for_tenant(self, tenant_id: str, limit=100):
        with self.engine.connect() as db:
            rows = db.execute(select(jobs).where(jobs.c.tenant_id == tenant_id)
                .order_by(jobs.c.created_at.desc()).limit(limit)).mappings()
            return [self._row(db, row, include_events=False) for row in rows]

    def summary_for_tenant(self, tenant_id: str):
        with self.engine.connect() as db:
            counts = db.execute(select(jobs.c.status, func.count()).where(jobs.c.tenant_id == tenant_id)
                .group_by(jobs.c.status)).all()
        statuses = {status: count for status, count in counts}
        return {"total": sum(statuses.values()), "by_status": statuses}

    def list_pending(self):
        with self.engine.connect() as db:
            rows = db.execute(select(jobs).where(jobs.c.status.in_(["queued", "answer_queued"]))
                .order_by(jobs.c.created_at)).mappings()
            return [self._row(db, row) for row in rows]

    def create(self, tenant_id, owner_id, request_payload, request_hash, idempotency_key):
        now, identity = _now(), str(uuid4())
        try:
            with self.engine.begin() as db:
                if idempotency_key:
                    prior = db.execute(select(jobs).where(jobs.c.tenant_id == tenant_id,
                        jobs.c.idempotency_key == idempotency_key)).mappings().first()
                    if prior:
                        existing = self._row(db, prior)
                        if existing["request_hash"] != request_hash:
                            raise IdempotencyConflict("That idempotency key was already used for different review input.")
                        return existing, False
                db.execute(insert(jobs).values(id=identity, tenant_id=tenant_id, owner_id=owner_id,
                    idempotency_key=idempotency_key, request_hash=request_hash, status="queued", attempts=0,
                    request_payload=json.dumps(request_payload, sort_keys=True), session_payload=None,
                    answer_payload=None, error=None, created_at=now, updated_at=now))
                self._event(db, identity, "queued")
                row = db.execute(select(jobs).where(jobs.c.id == identity)).mappings().one()
                return self._row(db, row), True
        except IntegrityError:
            # Two requests can pass the initial lookup concurrently. The unique
            # constraint selects one winner, and the other reuses its result.
            if not idempotency_key:
                raise
            existing = self.get_by_idempotency_key(tenant_id, idempotency_key)
            if not existing:
                raise
            if existing["request_hash"] != request_hash:
                raise IdempotencyConflict("That idempotency key was already used for different review input.") from None
            return existing, False

    def get_by_idempotency_key(self, tenant_id, key):
        with self.engine.connect() as db:
            row = db.execute(select(jobs).where(jobs.c.tenant_id == tenant_id,
                jobs.c.idempotency_key == key)).mappings().first()
            return self._row(db, row) if row else None

    def claim(self, identity):
        with self.engine.begin() as db:
            row = db.execute(select(jobs).where(jobs.c.id == identity).with_for_update()).mappings().first()
            if not row or row["status"] not in {"queued", "answer_queued"}:
                return None
            previous_status = row["status"]
            attempts = row["attempts"] + 1
            db.execute(update(jobs).where(jobs.c.id == identity).values(status="running", attempts=attempts, updated_at=_now()))
            self._event(db, identity, "started", {"attempt": attempts, "resume": previous_status == "answer_queued"})
            row = db.execute(select(jobs).where(jobs.c.id == identity)).mappings().one()
            claimed = self._row(db, row)
            claimed["resuming"] = previous_status == "answer_queued"
            return claimed

    def set_result(self, identity, status, session=None, error=None, trace_id=None, trace_url=None, timings=None,
                   retrieval_request=None, sources=None):
        session_payload = session.model_dump_json() if isinstance(session, ReviewSession) else None
        error_payload = json.dumps(error, sort_keys=True) if error else None
        with self.engine.begin() as db:
            row = db.execute(select(jobs).where(jobs.c.id == identity).with_for_update()).mappings().first()
            if not row:
                return None
            db.execute(update(jobs).where(jobs.c.id == identity).values(status=status,
                session_payload=session_payload or row["session_payload"], answer_payload=None,
                error=error_payload, updated_at=_now()))
            details = {k: v for k, v in {"trace_id": trace_id, "trace_url": trace_url}.items() if v}
            if timings:
                details["timings"] = timings
            if retrieval_request:
                details["retrieval_request"] = retrieval_request
            if sources:
                details["sources"] = sources
            self._event(db, identity, status, details)
            return self._row(db, db.execute(select(jobs).where(jobs.c.id == identity)).mappings().one())

    def retry_or_fail(self, identity, message, max_attempts=2):
        with self.engine.begin() as db:
            row = db.execute(select(jobs).where(jobs.c.id == identity).with_for_update()).mappings().first()
            if not row:
                return None
            status = "queued" if row["attempts"] < max_attempts else "failed"
            error = {"code": "worker_error", "message": message[:400]}
            db.execute(update(jobs).where(jobs.c.id == identity).values(status=status, error=json.dumps(error), updated_at=_now()))
            self._event(db, identity, status, {"reason": "retryable worker failure" if status == "queued" else "retry limit reached"})
            return self._row(db, db.execute(select(jobs).where(jobs.c.id == identity)).mappings().one())

    def queue_answer(self, identity, tenant_id, answer):
        with self.engine.begin() as db:
            row = db.execute(select(jobs).where(jobs.c.id == identity, jobs.c.tenant_id == tenant_id).with_for_update()).mappings().first()
            if not row:
                return None, "not_found"
            if row["status"] in {"answer_queued", "running"} and row["answer_payload"]:
                if json.loads(row["answer_payload"])["answer"] == answer:
                    return self._row(db, row), "duplicate"
                return None, "conflict"
            if row["status"] != "context_needed" or not row["session_payload"]:
                return None, "conflict"
            session = ReviewSession.model_validate_json(row["session_payload"])
            if not session.context_question:
                return None, "conflict"
            saved = {"question": session.context_question, "finding_id": session.finding_id, "answer": answer}
            db.execute(update(jobs).where(jobs.c.id == identity).values(status="answer_queued",
                answer_payload=json.dumps(saved, sort_keys=True), updated_at=_now()))
            self._event(db, identity, "answer_queued", {"finding_id": session.finding_id, "question": session.context_question})
            return self._row(db, db.execute(select(jobs).where(jobs.c.id == identity)).mappings().one()), "accepted"

    def recover_running(self, max_attempts=2):
        with self.engine.begin() as db:
            rows = db.execute(select(jobs).where(jobs.c.status == "running").with_for_update()).mappings().all()
            for row in rows:
                status = "queued" if row["attempts"] < max_attempts else "failed"
                error = None if status == "queued" else json.dumps({"code": "retry_limit", "message": "Worker stopped after the retry limit."})
                db.execute(update(jobs).where(jobs.c.id == row["id"]).values(status=status, error=error, updated_at=_now()))
                self._event(db, row["id"], status, {"reason": "recovered after process restart"})


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    workspace: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class ApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


class StartReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=100_000)
    filename: str = Field(default="review.py", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_. -]{0,119}$")
    context: str = Field(default="", max_length=2000)
    cloud_consent: bool = False


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    answer: str = Field(min_length=1, max_length=2000)


class RetrievalFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = Field(min_length=1, max_length=160)
    label: Literal["relevant", "not_relevant", "uncertain"]
    reason: str = Field(default="", max_length=2000)


class ReviewJobResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "answer_queued", "context_needed", "complete", "partial", "failed"]
    attempts: int
    created_at: str
    updated_at: str
    session: ReviewSession | None = None
    error: dict | None = None
    events: list[dict] = Field(default_factory=list)
    trace_id: str | None = None
    trace_url: str | None = None
    timings: list[dict] = Field(default_factory=list)
    retrieval_request: dict | None = None
    sources: list[dict] = Field(default_factory=list)


class ReviewJobWorker:
    def __init__(self, runtime, repository: ReviewJobRepository, identity: IdentityStore, *, poll_seconds=0.2, max_attempts=2):
        self.runtime, self.repository, self.identity = runtime, repository, identity
        self.poll_seconds, self.max_attempts = poll_seconds, max_attempts
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.repository.recover_running(self.max_attempts)
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, name="aiact-review-worker", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            # Keep database handles alive until bounded model calls and the
            # checkpoint save have finished.
            timeout = min(130, max(5, self.runtime.settings.deadline_seconds + 5))
            self.thread.join(timeout=timeout)

    def _loop(self):
        while not self.stop_event.is_set():
            pending = self.repository.list_pending()
            if not pending:
                self.stop_event.wait(self.poll_seconds)
                continue
            for candidate in pending:
                if self.stop_event.is_set():
                    break
                job = self.repository.claim(candidate["id"])
                if job:
                    self._process(job)

    def _process(self, job):
        trace = None
        token = None
        try:
            from aiact.context import Budgets
            from aiact.gemini import Gemini
            from aiact.providers import Ollama
            from aiact.rag.sessions import get_review_retrieval_context, get_review_session, resume_review_session, start_review_session
            from aiact.settings import load_settings
            from aiact.telemetry import CURRENT, Trace

            settings = self.runtime.settings
            request = job["request"]
            if request["settings_fingerprint"] != settings.config_fingerprint():
                self.repository.set_result(job["id"], "failed", error={"code": "settings_changed",
                    "message": "Review settings changed while this job was waiting. Start it again with the current settings."})
                return
            trace = Trace(settings)
            token = CURRENT.set(trace)
            if settings.provider == "gemini":
                settings.require_cloud(request["cloud_consent"])
                provider = Gemini(settings.model, api_key=settings.gemini_api_key.get_secret_value(),
                    temperature=settings.model_temperature, review_output_tokens=settings.model_review_output_tokens,
                    extract_output_tokens=settings.model_extract_output_tokens)
            else:
                provider = Ollama(settings.model, settings.ollama_url, temperature=settings.model_temperature,
                    context_tokens=settings.ollama_context_tokens, review_output_tokens=settings.ollama_review_output_tokens,
                    extract_output_tokens=settings.ollama_extract_output_tokens)
            budgets = Budgets(files=settings.max_files, file_bytes=settings.max_file_bytes,
                source_bytes=settings.max_source_bytes, passages=settings.max_passages, legal_bytes=settings.max_legal_bytes,
                request_seconds=settings.request_seconds, total_seconds=settings.deadline_seconds)
            with tempfile.TemporaryDirectory(prefix="aiact-job-") as temp:
                source = Path(temp) / request["filename"]
                source.write_text(request["code"])
                with self.runtime.lock:
                    retriever = self.runtime.get_retriever("ai-act", request["rag_release_id"])
                    if job.get("resuming"):
                        saved = get_review_session(job["id"], settings)
                        answer = job.get("answer") or {}
                        already_answered = any(event.type == "context_answered" and event.question == answer.get("question")
                            and event.answer == answer.get("answer") for event in saved.history)
                        session = saved if already_answered else resume_review_session(job["id"], source, provider,
                            retriever, answer.get("answer", ""), budgets=budgets, settings=settings, actor=job["request"]["reviewer"])
                    else:
                        saved = get_review_session(job["id"], settings)
                        if saved.scan_result and not (saved.scan_result.status == "failed" and
                                saved.scan_result.errors and saved.scan_result.errors[0].code == "session_not_found"):
                            session = saved
                        else:
                            session = start_review_session(source, provider, retriever, request["context"],
                                budgets=budgets, settings=settings, session_id=job["id"])
            trace.attributes.update(getattr(provider, "usage_totals", {}))
            trace.finish(session.scan_result, request["rag_release_id"])
            try:
                retrieval_context = get_review_retrieval_context(job["id"], settings)
            except Exception:
                retrieval_context = {"request": None, "sources": []}
            trace_url = ("https://cloud.langfuse.com/project/" + settings.langfuse_project_id + "/traces/" + trace.id
                if settings.langfuse_enabled and settings.langfuse_project_id else None)
            timings = [{"stage": step["stage"], "elapsed_ms": max(0, int((step["end_ns"] - step["start_ns"]) / 1_000_000)),
                "status": step["status"]} for step in trace.steps]
            self.repository.set_result(job["id"], session.status, session=session, trace_id=trace.id,
                trace_url=trace_url, timings=timings, retrieval_request=retrieval_context["request"],
                sources=retrieval_context["sources"])
        except Exception:
            # Exception text may contain provider request details. Keep the
            # persisted user-facing error free of source, prompts and secrets.
            self.repository.retry_or_fail(job["id"],
                "Review could not be completed. Check model connection and settings, then retry.", self.max_attempts)
        finally:
            if token is not None:
                CURRENT.reset(token)


class ApiKeyUsageMiddleware:
    """Record measured status and latency for successfully authenticated API-key calls."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.monotonic()

        async def record_and_send(message):
            if message["type"] == "http.response.start":
                state = scope.get("state", {})
                user, identity = state.get("aiact_identity"), state.get("aiact_identity_store")
                if user and user.get("auth_type") == "api_key" and identity:
                    try:
                        identity.record_usage(user, scope.get("path", ""), message["status"],
                            int((time.monotonic() - started) * 1000))
                    except Exception:
                        pass
            await send(message)

        await self.app(scope, receive, record_and_send)


def _job_response(job):
    return ReviewJobResponse(id=job["id"], status=job["status"], attempts=job["attempts"],
        created_at=job["created_at"], updated_at=job["updated_at"], session=job.get("session"),
        error=job.get("error"), events=job.get("events", []), trace_id=job.get("trace_id"), trace_url=job.get("trace_url"),
        timings=job.get("timings", []), retrieval_request=job.get("retrieval_request"), sources=job.get("sources", []))


def router(runtime_getter):
    routes = APIRouter()

    def stores():
        rt = runtime_getter()
        return rt.identity, rt.review_jobs

    def current_user(request: Request, allow_api_key=True):
        identity, _ = stores()
        token = request.cookies.get("aiact_session")
        user = identity.user_for_session(token)
        authorization = request.headers.get("authorization", "")
        if not user and allow_api_key and authorization.startswith("Bearer "):
            user = identity.authenticate_api_key(authorization[7:].strip())
        if not user:
            raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
        state = request.scope.setdefault("state", {})
        state["aiact_identity"] = user
        state["aiact_identity_store"] = identity
        return user

    @routes.post("/api/auth/register", status_code=201)
    def register(body: RegisterRequest, response: Response):
        rt = runtime_getter()
        if rt.settings.demo_mode:
            raise HTTPException(404, "Account creation is not available in this demo.")
        identity = rt.identity
        try:
            user = identity.register(body.workspace, body.email, body.password)
        except ValueError as exc:
            raise HTTPException(409 if "already exists" in str(exc) else 422, str(exc)) from None
        token = identity.create_session(user["id"])
        response.set_cookie("aiact_session", token, httponly=True, samesite="lax", secure=False,
            max_age=7 * 24 * 60 * 60, path="/")
        return {k: user[k] for k in ("id", "tenant_id", "email", "workspace")}

    @routes.post("/api/auth/login")
    def login(body: LoginRequest, response: Response):
        identity, _ = stores()
        user = identity.authenticate(body.email, body.password)
        if not user:
            raise HTTPException(401, "Email or password is incorrect.")
        token = identity.create_session(user["id"])
        response.set_cookie("aiact_session", token, httponly=True, samesite="lax", secure=False,
            max_age=7 * 24 * 60 * 60, path="/")
        return {k: user[k] for k in ("id", "tenant_id", "email", "workspace")}

    @routes.post("/api/auth/demo")
    def demo_login(response: Response):
        rt = runtime_getter()
        if not rt.settings.demo_mode:
            raise HTTPException(404, "Demo sign-in is not enabled.")
        user = rt.identity.find_user_by_email(rt.settings.demo_user_email)
        if not user:
            raise HTTPException(503, "Demo account is not ready. Restart the local app.")
        token = rt.identity.create_session(user["id"])
        response.set_cookie("aiact_session", token, httponly=True, samesite="lax", secure=False,
            max_age=7 * 24 * 60 * 60, path="/")
        return {k: user[k] for k in ("id", "tenant_id", "email", "workspace")}

    @routes.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response):
        identity, _ = stores()
        identity.revoke_session(request.cookies.get("aiact_session"))
        response.delete_cookie("aiact_session", path="/")

    @routes.get("/api/auth/me")
    def me(user=Depends(current_user)):
        return {k: user[k] for k in ("id", "tenant_id", "email", "workspace")}

    @routes.post("/api/api-keys", status_code=201)
    def create_key(body: ApiKeyRequest, request: Request, user=Depends(current_user)):
        if user["auth_type"] != "session":
            raise HTTPException(403, "Sign in with your workspace account to create API keys.")
        identity, _ = stores()
        try:
            return identity.create_api_key(user["tenant_id"], user["id"], body.name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @routes.get("/api/api-keys")
    def list_keys(user=Depends(current_user)):
        identity, _ = stores()
        return identity.list_api_keys(user["tenant_id"])

    @routes.delete("/api/api-keys/{identity_id}")
    def revoke_key(identity_id: str, user=Depends(current_user)):
        if user["auth_type"] != "session":
            raise HTTPException(403, "Sign in with your workspace account to revoke API keys.")
        identity, _ = stores()
        if not identity.revoke_api_key(user["tenant_id"], identity_id):
            raise HTTPException(404, "API key was not found in this workspace.")
        return {"revoked": identity_id}

    @routes.get("/api/api-usage")
    def usage(user=Depends(current_user)):
        identity, _ = stores()
        return identity.list_usage(user["tenant_id"])

    @routes.post("/api/reviews", status_code=202, response_model=ReviewJobResponse)
    def start_review(body: StartReviewRequest, request: Request,
                     idempotency_key: str | None=Header(default=None, alias="Idempotency-Key"),
                     user=Depends(current_user)):
        rt = runtime_getter()
        try:
            from aiact.rag.uploaded import validate_upload
            validate_upload(body.filename, body.code, body.context, rt.settings.max_source_bytes)
            rt.settings.require_cloud(body.cloud_consent)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if idempotency_key and not 8 <= len(idempotency_key) <= 128:
            raise HTTPException(422, "Idempotency-Key must contain 8 to 128 characters.")
        with rt.lock:
            release_id = rt.store.pointer("ai-act")
            if not release_id:
                raise HTTPException(503, "Build and activate a local RAG version before starting a review.")
        payload = body.model_dump() | {"filename": body.filename, "rag_release_id": release_id,
            "settings_fingerprint": rt.settings.config_fingerprint(), "reviewer": user["email"]}
        request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        try:
            job, _ = rt.review_jobs.create(user["tenant_id"], user["id"], payload, request_hash, idempotency_key)
        except IdempotencyConflict as exc:
            raise HTTPException(409, str(exc)) from None
        return _job_response(job)

    @routes.get("/api/reviews")
    def list_reviews(user=Depends(current_user)):
        _, repository = stores()
        return [_job_response(job) for job in repository.list_for_tenant(user["tenant_id"])]

    @routes.get("/api/reviews/summary")
    def review_summary(user=Depends(current_user)):
        _, repository = stores()
        return repository.summary_for_tenant(user["tenant_id"])

    @routes.get("/api/reviews/{identity_id}")
    def get_review(identity_id: str, user=Depends(current_user)):
        _, repository = stores()
        job = repository.get(identity_id, user["tenant_id"])
        if not job:
            raise HTTPException(404, "Review was not found in this workspace.")
        return _job_response(job)

    @routes.post("/api/reviews/{identity_id}/answer", status_code=202)
    def answer_review(identity_id: str, body: AnswerRequest, user=Depends(current_user)):
        _, repository = stores()
        job, result = repository.queue_answer(identity_id, user["tenant_id"], body.answer)
        if result == "not_found":
            raise HTTPException(404, "Review was not found in this workspace.")
        if result == "conflict":
            raise HTTPException(409, "This review is not waiting for this answer. Reload the review first.")
        return _job_response(job)

    @routes.post("/api/reviews/{identity_id}/retrieval-feedback", status_code=201)
    def retrieval_feedback(identity_id: str, body: RetrievalFeedbackRequest, user=Depends(current_user)):
        rt = runtime_getter()
        job = rt.review_jobs.get(identity_id, user["tenant_id"])
        if not job:
            raise HTTPException(404, "Review was not found in this workspace.")
        source = next((item for item in job.get("sources", []) if item.get("id") == body.source_id), None)
        if not source or not job.get("retrieval_request") or not job.get("session"):
            raise HTTPException(409, "This review has no saved source list to label.")
        from aiact.rag.contracts import GoldLabel, GoldenCase, RetrievalRequest
        from aiact.rag.feedback import latest_cases, save_case
        request_data = RetrievalRequest.model_validate(job["retrieval_request"])
        case_id = "review-" + identity_id
        existing = next((case for case in latest_cases(rt.store, "ai-act") if case.id == case_id), None)
        if existing and existing.status == "approved":
            raise HTTPException(409, "This review feedback is already approved and cannot be changed.")
        prior_labels = list(existing.labels) if existing else []
        current = next((label for label in prior_labels if label.chunk_id == body.source_id), None)
        reason = body.reason or "No additional reason provided."
        if current and current.label == body.label and current.rationale == reason:
            return {"case_id": case_id, "revision": existing.revision, "label": body.label, "saved": True}
        labels = [label for label in prior_labels if label.chunk_id != body.source_id]
        labels.append(GoldLabel(document_id=source["document_id"], chunk_id=body.source_id,
            label=body.label, rationale=reason))
        session = job["session"]
        scan = session.scan_result
        if not scan or not scan.metadata.corpus_checksum or not session.rag_release_id:
            raise HTTPException(409, "This review has no pinned source version for feedback.")
        try:
            case = GoldenCase(id=case_id, title="Review feedback " + identity_id[:8], request=request_data,
                snapshot_id=scan.metadata.corpus_checksum, rag_release_id=session.rag_release_id,
                labels=tuple(labels), author=user["email"], origin="human", status="draft",
                split="development", area="review feedback", revision=(existing.revision + 1 if existing else 1))
            save_case(rt.store, case)
        except (ValueError, TypeError):
            raise HTTPException(409, "This source feedback could not be saved for the pinned RAG version.") from None
        with rt.review_jobs.engine.begin() as db:
            rt.review_jobs._event(db, identity_id, "feedback_saved", {"source_id": body.source_id,
                "label": body.label, "reason": reason, "case_id": case_id, "revision": case.revision})
        return {"case_id": case_id, "revision": case.revision, "label": body.label, "saved": True}

    @routes.get("/api/system/health")
    def product_health():
        rt = runtime_getter()
        return {"status": "ready", "worker": "running" if rt.review_worker and rt.review_worker.thread and rt.review_worker.thread.is_alive() else "stopped",
            "storage": rt.store.engine.dialect.name}

    return routes
