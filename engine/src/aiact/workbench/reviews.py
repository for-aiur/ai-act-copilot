"""Tenant-scoped durable review jobs and the single local worker."""
from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, func, insert, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.engine import make_url

from aiact.contracts import ReviewSession
from .ai_systems import AiInventory, EvidenceInput, LinkInput, SystemInput
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


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    repository_ids: list[str] = Field(default_factory=list, max_length=200)


class FindingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    head: str = Field(min_length=1, max_length=64)
    action: Literal["acknowledged", "false_positive", "resolved", "open", "context", "fp_approve", "unsure"]
    reason: str = Field(default="", max_length=2000)
    event_id: str = Field(min_length=8, max_length=128)
    category: Literal["irrelevant_source", "code_misread", "missing_context", "other"] | None = None


class FalsePositivePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["immediate", "approval"]


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    answer: str = Field(min_length=1, max_length=2000)


class RescanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cloud_consent: bool = False


class RetrievalFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = Field(min_length=1, max_length=160)
    label: Literal["relevant", "not_relevant", "uncertain"]
    reason: str = Field(default="", max_length=2000)


class ReviewJobResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "answer_queued", "context_needed", "complete", "partial", "failed"]
    attempts: int
    filename: str | None = None
    legal_source: dict | None = None
    created_at: str
    updated_at: str
    session: ReviewSession | None = None
    error: dict | None = None
    events: list[dict] = Field(default_factory=list)
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
            saved = self.repository.set_result(job["id"], session.status, session=session, trace_id=trace.id,
                trace_url=trace_url, timings=timings, retrieval_request=retrieval_context["request"],
                sources=retrieval_context["sources"])
            from .findings import CustomerFindings, add_review_findings
            add_review_findings(CustomerFindings(self.repository.engine), job["tenant_id"], job["id"],
                session, saved["updated_at"] if saved else _now())
        except Exception:
            # Exception text may contain provider request details. Keep the
            # persisted user-facing error free of source, prompts and secrets.
            failed = self.repository.retry_or_fail(job["id"],
                "Review could not be completed. Check model connection and settings, then retry.", self.max_attempts)
            if failed and failed["status"] == "failed":
                from .findings import CustomerFindings
                store = CustomerFindings(self.repository.engine)
                store.bind(job["tenant_id"], "local-reviews", "local-workspace", "Local code reviews")
                store.record_review(job["tenant_id"], "local-reviews", "failed", failed["updated_at"])
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


def _pinned_source(job, store, source_cache):
    from .source_updates import source_info
    release_id = (job.get("request") or {}).get("rag_release_id")
    if release_id and release_id not in source_cache:
        try:
            source_cache[release_id] = source_info(store.snapshot(store.release(release_id)["snapshot_id"]))
        except NoResultFound:
            source_cache[release_id] = None
    return source_cache.get(release_id)


def _job_response(job, store, source_cache=None):
    legal_source = _pinned_source(job, store, {} if source_cache is None else source_cache)
    session = job.get("session")
    if session:
        visible = session.model_dump(mode="json")
        visible["rag_release_id"] = None
        metadata = (visible.get("scan_result") or {}).get("metadata") or {}
        for field in ("provider", "model_id", "corpus_version", "corpus_checksum"):
            metadata[field] = None
        session = ReviewSession.model_validate(visible)
    return ReviewJobResponse(id=job["id"], status=job["status"], attempts=job["attempts"],
        filename=(job.get("request") or {}).get("filename"), legal_source=legal_source,
        created_at=job["created_at"], updated_at=job["updated_at"], session=session,
        error=job.get("error"), events=[dict(event, details={key: value for key, value in event["details"].items() if key not in {"trace_id", "trace_url", "retrieval_request", "timings", "sources"}}) for event in job.get("events", [])],
        sources=job.get("sources", []))


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

    def customer_findings():
        from .findings import CustomerFindings
        return CustomerFindings(runtime_getter().review_jobs.engine)

    def project_scope(store, tenant_id, project):
        if project is None:
            return None
        repo_ids = store.project_repository_ids(tenant_id, project)
        if repo_ids is None:
            raise HTTPException(404, "Project not found.")
        return repo_ids

    @routes.get("/api/customer/projects")
    def list_projects(user=Depends(current_user)):
        return customer_findings().projects(user["tenant_id"])

    def save_project(body, user, project_id=None):
        if user["auth_type"] != "session":
            raise HTTPException(403, "Sign in to manage projects.")
        try:
            return customer_findings().save_project(
                user["tenant_id"], body.name, body.repository_ids, project_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @routes.post("/api/customer/projects", status_code=201)
    def create_project(body: ProjectInput, user=Depends(current_user)):
        return save_project(body, user)

    @routes.put("/api/customer/projects/{project_id}")
    def update_project(project_id: str, body: ProjectInput, user=Depends(current_user)):
        return save_project(body, user, project_id)

    def require_demo(user):
        if not runtime_getter().settings.demo_mode or user["auth_type"] != "session":
            raise HTTPException(404, "Demo is unavailable.")
        demo = runtime_getter().identity.find_user_by_email(runtime_getter().settings.demo_user_email)
        if not demo or demo["tenant_id"] != user["tenant_id"]:
            raise HTTPException(403, "Use the demo account.")

    @routes.get("/api/demo/status")
    def demo_status(user=Depends(current_user)):
        rt = runtime_getter()
        demo = rt.identity.find_user_by_email(rt.settings.demo_user_email) if rt.settings.demo_mode else None
        return {"enabled": bool(demo and user["auth_type"] == "session" and demo["tenant_id"] == user["tenant_id"])}

    @routes.get("/api/review-policy")
    def review_policy():
        return {"cloud_review_requires_consent": runtime_getter().settings.provider == "gemini"}

    def inventory_call(user, operation, *args):
        if user["auth_type"] != "session":
            raise HTTPException(403, "Sign in to manage AI systems.")
        runtime = runtime_getter()
        customer_findings()  # Initialize the shared customer tables.
        inventory = AiInventory(runtime.review_jobs.engine)
        try:
            return getattr(inventory, operation)(user["tenant_id"], *args)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    def evidence_source():
        from .source_updates import source_info
        store = runtime_getter().store
        active = store.pointer("ai-act")
        return source_info(store.snapshot(store.release(active)["snapshot_id"])) if active else None

    ai_systems_path = "/api/customer/projects/{project_id}/ai-systems"

    @routes.get(ai_systems_path)
    def list_ai_systems(project_id: str, user=Depends(current_user)):
        return inventory_call(user, "view", project_id)

    @routes.post(ai_systems_path, status_code=201)
    def add_ai_system(project_id: str, body: SystemInput, user=Depends(current_user)):
        return inventory_call(user, "save_system", project_id, body)

    @routes.put(ai_systems_path + "/{system_id}")
    def update_ai_system(project_id: str, system_id: str, body: SystemInput, user=Depends(current_user)):
        return inventory_call(user, "save_system", project_id, body, system_id)

    @routes.post(ai_systems_path + "/relationships", status_code=201)
    def link_ai_systems(project_id: str, body: LinkInput, user=Depends(current_user)):
        return inventory_call(user, "add_link", project_id, body)

    @routes.delete(ai_systems_path + "/relationships/{link_id}")
    def unlink_ai_systems(project_id: str, link_id: str, user=Depends(current_user)):
        inventory_call(user, "remove_link", project_id, link_id)
        return {"removed": True}

    @routes.get(ai_systems_path + "/{system_id}/evidence")
    def list_release_evidence(project_id: str, system_id: str, user=Depends(current_user)):
        return inventory_call(user, "evidence", project_id, system_id)

    @routes.post(ai_systems_path + "/{system_id}/evidence", status_code=201)
    def save_release_evidence(project_id: str, system_id: str, body: EvidenceInput, user=Depends(current_user)):
        return inventory_call(user, "save_evidence", project_id, system_id, body, evidence_source())

    @routes.post("/api/demo/ai-systems")
    def demo_ai_systems(user=Depends(current_user)):
        require_demo(user)
        return inventory_call(user, "seed_demo", evidence_source())

    @routes.post("/api/demo/seed")
    def demo_seed(user=Depends(current_user)):
        require_demo(user)
        from .findings import seed_demo
        seed_demo(customer_findings(), user["tenant_id"])
        return {"seeded": True}

    @routes.post("/api/demo/findings/{finding_id}/pr-reply")
    def demo_reply(finding_id: str, body: FindingDecision, user=Depends(current_user)):
        require_demo(user)
        if not finding_id.startswith("demo-"):
            raise HTTPException(422, "Choose a synthetic finding.")
        store = customer_findings()
        try:
            from .findings import DemoGitHub
            if body.action == "fp_approve":
                raise HTTPException(403, "Approve from the workspace.")
            decision = store.decide(user["tenant_id"], finding_id, body.head, body.action,
                "simulated-github-reviewer", body.reason, body.event_id, body.category)
            if decision["action"] != "fp_pending":
                store.sync(user["tenant_id"], body.event_id, DemoGitHub(store, user["tenant_id"]))
                decision["sync_status"] = "synced"
            return decision | {"simulated": True}
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @routes.get("/api/customer/overview")
    def customer_overview(project: str | None = None, user=Depends(current_user)):
        from .findings import policy_counts
        store = customer_findings()
        tenant = user["tenant_id"]
        repo_ids = project_scope(store, tenant, project)
        rows = store.list(tenant)
        inventory = store.inventory(tenant)
        if repo_ids is not None:
            rows = [row for row in rows if row["repository_id"] in repo_ids]
            inventory = [repo for repo in inventory if repo["id"] in repo_ids]
        bot_rows = [row for row in rows if row["payload"].get("source_type") != "local_review"]
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=30)).isoformat()
        priority_order = {"high": 0, "medium": 1, "low": 2}
        stages = {
            stage: dict.fromkeys(priority_order, 0)
            for stage in ("open_pr", "merged", "released", "unknown")
        }
        for row in bot_rows:
            if row["state"] == "open" and row["priority"] in priority_order:
                stage = row["payload"].get("code_stage")
                stages.get(stage, stages["unknown"])[row["priority"]] += 1
        queue = sorted(
            (row for row in bot_rows if row["state"] == "open"),
            key=lambda row: (priority_order.get(row["priority"], 3), row["created_at"], row["id"]),
        )[:5]
        return {
            "open_by_code_stage": stages,
            "policies": policy_counts(row for row in bot_rows if row["state"] != "false_positive"),
            "needs_review": [{
                "id": row["id"], "repository": row["name"], "pr": row["pr"],
                "priority": row["priority"], "title": row["payload"].get("title") or "Review finding",
                "branch": row["payload"].get("branch"),
            } for row in queue],
            "open_high": sum(r["state"] == "open" and r["priority"] == "high" for r in bot_rows),
            "awaiting_context": sum(r["state"] == "open" and r["payload"].get("context_question") is not None for r in bot_rows),
            "resolved_recently": sum(r["state"] == "resolved" and r["updated_at"] >= cutoff for r in bot_rows),
            "repositories": [dict(repo) | {
                "policies": policy_counts(r for r in bot_rows if r["repository_id"] == repo["id"] and r["state"] != "false_positive"),
                "open": sum(r["repository_id"] == repo["id"] and r["state"] == "open" for r in rows),
                "open_high": sum(r["repository_id"] == repo["id"] and r["state"] == "open" and r["priority"] == "high" for r in rows),
                "open_medium": sum(r["repository_id"] == repo["id"] and r["state"] == "open" and r["priority"] == "medium" for r in rows),
                "open_low": sum(r["repository_id"] == repo["id"] and r["state"] == "open" and r["priority"] == "low" for r in rows)
            } for repo in inventory]}

    @routes.get("/api/customer/source-updates")
    def customer_source_updates(project: str | None = None, user=Depends(current_user)):
        from .source_updates import affected_findings, source_changes, source_info
        rt = runtime_getter()
        active = rt.store.pointer("ai-act")
        current = rt.store.snapshot(rt.store.release(active)["snapshot_id"]) if active else None
        store = customer_findings()
        repo_ids = project_scope(store, user["tenant_id"], project)
        rows = [row for row in store.list(user["tenant_id"])
                if repo_ids is None or row["repository_id"] in repo_ids]
        comparisons = []
        if current:
            previous_ids = {
                row["payload"]["source_snapshot_id"] for row in rows
                if row["payload"].get("source_snapshot_id")
                and row["payload"]["source_snapshot_id"] != current.snapshot_id
            }
            for identity in sorted(previous_ids):
                try:
                    previous = rt.store.snapshot(identity)
                except NoResultFound:
                    continue
                if previous.domain_id != current.domain_id:
                    continue
                changes = source_changes(previous, current)
                if not changes:
                    continue
                impacted = affected_findings(previous, current, rows)
                direct = {item["repository"] for item in impacted}
                candidates = sorted({row["name"] for row in rows
                    if row["payload"].get("source_snapshot_id") == identity
                    and row["name"] not in direct})
                comparisons.append({"previous": source_info(previous), "changes": changes,
                    "affected": impacted, "candidates": candidates})
        demo = demo_status(user)["enabled"]
        sample = next((row for row in rows if row["id"] == "demo-recruitment:14:demo-finding"), None) if demo else None
        return {"active": source_info(current) if current else None, "comparisons": comparisons,
            "demo_finding": {"id": sample["id"], "repository": sample["name"],
                "title": sample["payload"]["title"]} if sample else None}

    @routes.get("/api/customer/usage")
    def customer_usage(user=Depends(current_user)):
        from .identity import api_usage
        rt = runtime_getter()
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        first_day = now.date() - timedelta(days=13)
        with rt.review_jobs.engine.connect() as db:
            completed = db.execute(select(func.count(func.distinct(jobs.c.id))).select_from(
                jobs.join(events, jobs.c.id == events.c.job_id)).where(
                jobs.c.tenant_id == user["tenant_id"], jobs.c.status == "complete",
                events.c.type == "complete", events.c.created_at >= start)).scalar()
        with rt.identity.engine.connect() as db:
            calls = db.execute(select(func.count()).select_from(api_usage).where(
                api_usage.c.tenant_id == user["tenant_id"], api_usage.c.created_at >= start)).scalar()
            day = func.substr(api_usage.c.created_at, 1, 10)
            counts = dict(db.execute(select(day, func.count()).where(
                api_usage.c.tenant_id == user["tenant_id"],
                api_usage.c.created_at >= first_day.isoformat(),
                api_usage.c.created_at <= now.isoformat(),
            ).group_by(day)).all())
        daily_requests = []
        for offset in range(14):
            date = (first_day + timedelta(days=offset)).isoformat()
            daily_requests.append({"date": date, "requests": counts.get(date, 0)})
        return {"completed_reviews": completed, "api_requests": calls, "estimated_charge": round(completed * rt.settings.review_unit_price, 2) if rt.settings.review_unit_price is not None else None,
            "currency": rt.settings.billing_currency if rt.settings.review_unit_price is not None else None, "period_start": start, "daily_requests": daily_requests}

    @routes.get("/api/customer/false-positive-policy")
    def get_fp_policy(user=Depends(current_user)):
        return customer_findings().fp_policy(user["tenant_id"])

    @routes.put("/api/customer/false-positive-policy")
    def set_fp_policy(body: FalsePositivePolicy, user=Depends(current_user)):
        if user["auth_type"] != "session":
            raise HTTPException(403, "Sign in to manage false-positive policy.")
        try:
            return customer_findings().set_fp_policy(user["tenant_id"], body.mode, user["email"])
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None

    @routes.get("/api/customer/false-positive-metrics")
    def fp_metrics(project: str | None = None, history: bool = False, user=Depends(current_user)):
        from collections import Counter
        from .findings import finding_policies
        store = customer_findings()
        repo_ids = project_scope(store, user["tenant_id"], project)
        rows = [row for row in store.list(user["tenant_id"])
                if repo_ids is None or row["repository_id"] in repo_ids]
        marks = store.fp_marks(user["tenant_id"])
        dimensions = {key: Counter() for key in ("priority", "policy", "category", "model", "rag_release", "repository", "day")}
        by_id = {row["id"]: row for row in rows}
        submissions = [mark for mark in store.fp_submissions(user["tenant_id"])
                       if mark["finding_id"] in by_id]
        events = submissions if history else [mark for key, mark in marks.items() if key in by_id]
        for mark in events:
            row = by_id[mark["finding_id"]]
            payload = row["payload"] if row["head"] == mark["head"] else {}
            dimensions["priority"][row["priority"] if payload else "Unknown"] += 1
            dimensions["policy"].update(finding_policies(payload))
            dimensions["category"][mark["category"] or "unspecified"] += 1
            dimensions["model"][payload.get("model_id") or "Unknown"] += 1
            dimensions["rag_release"][payload.get("rag_release_id") or "Unknown"] += 1
            dimensions["repository"][row["name"]] += 1
            dimensions["day"][mark["created_at"][:10]] += 1
        return {"findings": len(rows), "marked": sum(key in by_id for key in marks),
            "submissions": len(submissions),
            "pending": sum(mark["pending"] for key, mark in marks.items() if key in by_id),
            "breakdowns": {key: dict(values) for key, values in dimensions.items()}}

    @routes.get("/api/findings")
    def list_findings(project: str | None = None, user=Depends(current_user)):
        from .findings import finding_policies
        rt = runtime_getter()
        source_cache, review_versions = {}, {}
        result = []
        store = customer_findings()
        repo_ids = project_scope(store, user["tenant_id"], project)
        marks = store.fp_marks(user["tenant_id"])
        legal = store.legal_requests(user["tenant_id"])
        for row in store.list(user["tenant_id"]):
            if repo_ids is not None and row["repository_id"] not in repo_ids:
                continue
            payload = row["payload"]
            version = payload.get("source_version")
            review_id = payload.get("source_review_id")
            if not version and review_id and payload.get("source_type") == "local_review":
                if review_id not in review_versions:
                    job = rt.review_jobs.get(review_id, user["tenant_id"])
                    source = _pinned_source(job, rt.store, source_cache) if job else None
                    review_versions[review_id] = source["version"] if source else None
                version = review_versions[review_id]
            result.append(dict(row) | {"policies": finding_policies(payload), "source_version": version, "fp_mark": marks.get(row["id"]), "legal_request": legal.get(row["id"])})
        return result

    @routes.get("/api/repositories")
    def list_repositories(user=Depends(current_user)):
        return customer_findings().inventory(user["tenant_id"])

    @routes.get("/api/findings/{finding_id}/history")
    def finding_history(finding_id: str, user=Depends(current_user)):
        try:
            return customer_findings().history(user["tenant_id"], finding_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None

    @routes.post("/api/findings/{finding_id}/decision")
    def finding_decision(finding_id: str, body: FindingDecision, user=Depends(current_user)):
        if user["auth_type"] != "session":
            raise HTTPException(403, "Sign in to record a decision.")
        try:
            store = customer_findings()
            decision = store.decide(user["tenant_id"], finding_id, body.head,
                body.action, user["email"], body.reason, body.event_id, body.category)
            if runtime_getter().settings.demo_mode and finding_id.startswith("demo-") and decision["action"] != "fp_pending":
                from .findings import DemoGitHub
                store.sync(user["tenant_id"], body.event_id, DemoGitHub(store, user["tenant_id"]))
                decision["sync_status"] = "synced"
            return decision
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

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
        return _job_response(job, runtime_getter().store)

    @routes.get("/api/reviews")
    def list_reviews(user=Depends(current_user)):
        _, repository = stores()
        source_cache = {}
        store = runtime_getter().store
        return [_job_response(job, store, source_cache) for job in repository.list_for_tenant(user["tenant_id"])]

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
        return _job_response(job, runtime_getter().store)

    @routes.post("/api/reviews/{identity_id}/rescan", status_code=202, response_model=ReviewJobResponse)
    def rescan_review(identity_id: str, body: RescanRequest, request: Request,
                      idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                      user=Depends(current_user)):
        rt = runtime_getter()
        original = rt.review_jobs.get(identity_id, user["tenant_id"])
        if not original:
            raise HTTPException(404, "Review was not found in this workspace.")
        if original["status"] not in {"complete", "partial", "context_needed", "failed"}:
            raise HTTPException(409, "Wait for the original review to finish.")
        saved = original["request"]
        return start_review(StartReviewRequest(
            filename=saved["filename"], code=saved["code"], context=saved.get("context", ""),
            cloud_consent=body.cloud_consent), request, idempotency_key, user)

    @routes.post("/api/reviews/{identity_id}/answer", status_code=202)
    def answer_review(identity_id: str, body: AnswerRequest, user=Depends(current_user)):
        _, repository = stores()
        job, result = repository.queue_answer(identity_id, user["tenant_id"], body.answer)
        if result == "not_found":
            raise HTTPException(404, "Review was not found in this workspace.")
        if result == "conflict":
            raise HTTPException(409, "This review is not waiting for this answer. Reload the review first.")
        return _job_response(job, runtime_getter().store)

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
