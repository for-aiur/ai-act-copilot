"""Local workbench endpoints. One serialized owner for the embedded vector path."""
import threading
import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from aiact.rag.contracts import GoldenCase, RetrievalRequest, RetrievalResult
from aiact.rag.domains import DOMAINS, load_snapshot
from aiact.rag.evaluation import experiment_gate, quality_gate, score_case, summarize
from aiact.rag.feedback import latest_cases, save_case, save_run
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.rag.store import Store
from aiact.settings import Settings, load_settings


class BuildInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_id: str = "ai-act"
    download_model: bool = False
    lexical_only: bool = False


class ApprovalInput(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=100000)
    filename: str = Field(default="review.py", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_. -]{0,119}$")
    context: str = Field(default="", max_length=2000)
    cloud_consent: bool = False


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.database_url.get_secret_value())
        self.lock = threading.RLock()
        self.retriever = None

    def get_retriever(self, domain, identity=None):
        identity = identity or self.store.pointer(domain)
        if not identity:
            raise ValueError("No active RAG build. Build and activate a local candidate in Versions.")
        if self.retriever and self.retriever.manifest["rag_release_id"] != identity:
            self.retriever.close()
            self.retriever = None
        if not self.retriever:
            self.retriever = HybridRetriever(self.settings, identity, store=self.store)
        return self.retriever

    def close(self):
        if self.retriever:
            self.retriever.close()
        self.store.close()

    def update_settings(self, updated):
        if self.retriever:
            self.retriever.close()
            self.retriever = None
        self.settings = updated


def router(settings=None):
    state = {}
    init_lock = threading.RLock()
    @asynccontextmanager
    async def lifespan(app):
        yield
        if "runtime" in state:
            state["runtime"].close()
    routes = APIRouter(prefix="/api/rag", lifespan=lifespan)

    def runtime():
        with init_lock:
            if "runtime" not in state:
                state["runtime"] = Runtime(settings or load_settings())
        return state["runtime"]

    @routes.get("/settings")
    def get_settings():
        rt = runtime()
        return {"values": rt.settings.editable_config(), "fingerprint": rt.settings.config_fingerprint(),
            "saved": rt.settings.workbench_config_path.is_file(),
            "secrets": {"gemini_api_key": bool(rt.settings.gemini_api_key.get_secret_value()),
                "langfuse_keys": bool(rt.settings.langfuse_public_key.get_secret_value() and rt.settings.langfuse_secret_key.get_secret_value())},
            "fixed_quality_gate": {"approved_cases": 50, "source_areas": 10, "holdout_recall": 0.95,
                "critical_cases": "all approved critical cases must have no misses"}}

    @routes.put("/settings")
    def put_settings(body: dict):
        rt = runtime()
        allowed = set(rt.settings.editable_config())
        if set(body) != allowed:
            raise HTTPException(422, "Send the complete settings form. Unknown or missing fields.")
        validated = Settings.model_validate(rt.settings.model_dump() | body)
        path = validated.workbench_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(validated.editable_config(), indent=2, sort_keys=True) + "\n")
        os.replace(temporary, path)
        rt.update_settings(validated)
        return {"values": validated.editable_config(), "fingerprint": validated.config_fingerprint(), "saved": True}

    @routes.get("/domains")
    def domains():
        rt = runtime()
        return [d.model_dump() | {"active": rt.store.pointer(d.id)} for d in DOMAINS]

    @routes.get("/health")
    def readiness():
        rt = runtime()
        identity = rt.store.pointer("ai-act")
        if not identity:
            raise HTTPException(503, "Initial RAG setup is not complete.")
        from aiact.rag.releases import verify_bundle
        manifest, snapshot, _ = verify_bundle(rt.settings.data_dir / "releases" / identity)
        return {"status": "ready", "rag_release_id": identity, "source_complete": snapshot.complete,
                "quality_status": manifest["quality_status"], "inference_provider": rt.settings.provider}

    @routes.get("/library")
    def library(domain: str = "ai-act", q: str = Query(default="", max_length=200), kind: str = ""):
        rt = runtime()
        identity = rt.store.pointer(domain)
        snapshot = rt.store.snapshot(rt.store.release(identity)["snapshot_id"]) if identity else load_snapshot(domain)
        terms = q.casefold().split()
        docs = [d.model_dump(mode="json") for d in snapshot.documents if (not kind or d.kind == kind) and all(t in (d.title + " " + d.text).casefold() for t in terms)]
        return {"domain_id": domain, "snapshot_id": snapshot.snapshot_id, "source_version": snapshot.source_version,
            "complete": snapshot.complete, "total": len(snapshot.documents), "chunk_count": len(snapshot.chunks),
            "source_count": len(snapshot.source_hashes), "scope_limits": snapshot.scope_limits,
            "kinds": sorted({d.kind for d in snapshot.documents}), "documents": docs,
            "chunks": [c.model_dump(mode="json") for c in snapshot.chunks]}

    @routes.get("/versions")
    def versions(domain="ai-act"):
        rt = runtime()
        from aiact.rag.official import checksum
        items = rt.store.list_releases(domain)
        first = {}
        releases = []
        for manifest in items:
            effective = checksum({k:v for k,v in manifest.items() if k not in {"git_revision", "rag_release_id", "schema_version"}})
            equivalent = first.setdefault(effective, manifest["rag_release_id"])
            from aiact.rag.releases import compatibility
            releases.append(manifest | compatibility(manifest, rt.settings) | {"removal_blockers": rt.store.removal_blockers(manifest["rag_release_id"]),
                "equivalent_to": equivalent if equivalent != manifest["rag_release_id"] else None})
        return {"active": rt.store.pointer(domain), "previous": rt.store.pointer(domain, "previous"), "releases": releases,
                "provider": rt.settings.provider, "model": rt.settings.model, "cloud_key_configured": bool(rt.settings.gemini_api_key.get_secret_value()),
                "tracing_enabled": rt.settings.langfuse_enabled,
                "active_compatible": next((m["compatible"] for m in releases if m["rag_release_id"] == rt.store.pointer(domain)), False)}

    @routes.post("/build")
    def build(body: BuildInput):
        rt = runtime()
        if body.domain_id not in {d.id for d in DOMAINS}:
            raise HTTPException(422, "Unknown domain")
        with rt.lock:
            before = {m["rag_release_id"] for m in rt.store.list_releases(body.domain_id)}
            manifest = build_release(rt.settings, body.domain_id, body.download_model, body.lexical_only)
            return manifest | {"already_exists": manifest["rag_release_id"] in before}

    @routes.delete("/versions/{identity}")
    def remove_version(identity: str, domain="ai-act"):
        rt = runtime()
        with rt.lock:
            try:
                rt.store.remove_release(identity, domain)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            if rt.retriever and rt.retriever.manifest["rag_release_id"] == identity:
                rt.retriever.close()
                rt.retriever = None
            return {"removed": identity}

    @routes.post("/activate/{identity}")
    def activate(identity: str, domain="ai-act"):
        rt = runtime()
        with rt.lock:
            from aiact.rag.releases import verify_bundle
            manifest, _, _ = verify_bundle(rt.settings.data_dir / "releases" / identity)
            if manifest["domain_id"] != domain:
                raise HTTPException(409, "Release belongs to a different domain.")
            from aiact.rag.releases import compatibility
            state = compatibility(manifest, rt.settings)
            if not state["compatible"]:
                raise HTTPException(409, state["compatibility_reason"])
            rt.store.activate(domain, identity)
            return {"active": identity, "quality_status": manifest["quality_status"], "scope": "local_tooling_candidate"}

    @routes.post("/retrieve")
    def retrieve(body: RetrievalRequest, release: str | None = None):
        rt = runtime()
        with rt.lock:
            result = rt.get_retriever(body.domain_id, release).search(body)
            identity = save_run(rt.store, result)
        return {"id": identity, "result": result.model_dump(mode="json")}

    @routes.get("/runs")
    def runs(domain="ai-act"):
        return runtime().store.list_records("retrieval", domain, limit=30)

    @routes.post("/review")
    def review(body: ReviewInput):
        import tempfile
        from pathlib import Path
        from aiact.gemini import Gemini
        from aiact.providers import Ollama
        from aiact.rag.review import review_python
        rt = runtime()
        from aiact.rag.uploaded import validate_upload
        validate_upload(body.filename, body.code, body.context, rt.settings.max_source_bytes)
        rt.settings.require_cloud(body.cloud_consent)
        provider = Gemini(rt.settings.model, api_key=rt.settings.gemini_api_key.get_secret_value(),
            temperature=rt.settings.model_temperature, review_output_tokens=rt.settings.model_review_output_tokens,
            extract_output_tokens=rt.settings.model_extract_output_tokens) if rt.settings.provider == "gemini" else Ollama(
            rt.settings.model, rt.settings.ollama_url, temperature=rt.settings.model_temperature,
            context_tokens=rt.settings.ollama_context_tokens, review_output_tokens=rt.settings.ollama_review_output_tokens,
            extract_output_tokens=rt.settings.ollama_extract_output_tokens)
        with rt.lock, tempfile.TemporaryDirectory(prefix="aiact-review-") as temporary:
            source = Path(temporary) / body.filename
            source.write_text(body.code)
            from aiact.context import Budgets
            budgets = Budgets(files=rt.settings.max_files, file_bytes=rt.settings.max_file_bytes,
                source_bytes=rt.settings.max_source_bytes, passages=rt.settings.max_passages,
                legal_bytes=rt.settings.max_legal_bytes, request_seconds=rt.settings.request_seconds,
                total_seconds=rt.settings.deadline_seconds)
            payload = review_python(source, provider, rt.get_retriever("ai-act"), body.context, budgets=budgets, uploaded=True)
            payload["configuration"] = {"fingerprint": rt.settings.config_fingerprint(),
                "values": rt.settings.editable_config()}
            from aiact.telemetry import Trace
            from aiact.contracts import ScanResult
            trace = Trace(rt.settings)
            trace.steps = payload["steps"]
            trace.attributes.update(payload.get("usage") or {})
            if trace.steps:
                trace.started = trace.steps[0]["start_ns"]
            trace.finish(ScanResult.model_validate(payload["scan_result"]), payload["rag_release_id"])
            payload["trace_id"] = trace.id
            payload["trace_url"] = ("https://cloud.langfuse.com/project/" + rt.settings.langfuse_project_id + "/traces/" + trace.id) if rt.settings.langfuse_enabled and rt.settings.langfuse_project_id else None
            if payload.get("retrieval"):
                payload["retrieval_run_id"] = save_run(rt.store, RetrievalResult.model_validate(payload["retrieval"]))
            identity = str(uuid4())
            rt.store.append("review", identity, "ai-act", payload)
        return {"id": identity, **payload}

    @routes.get("/reviews")
    def reviews():
        return runtime().store.list_records("review", "ai-act", limit=30)

    @routes.get("/cases")
    def cases(domain="ai-act"):
        return [c.model_dump(mode="json") for c in latest_cases(runtime().store, domain)]

    @routes.post("/cases", status_code=201)
    def create_case(case: GoldenCase):
        if case.status != "draft" or case.approved_by:
            raise HTTPException(422, "Save as a draft; approve through the explicit reviewer action.")
        try:
            return save_case(runtime().store, case).model_dump(mode="json")
        except IntegrityError:
            raise HTTPException(409, "That immutable case revision already exists. Create a new revision.") from None

    @routes.post("/cases/{identity}/{revision}/approve")
    def approve_case(identity: str, revision: int, body: ApprovalInput):
        rt = runtime()
        case = GoldenCase.model_validate(rt.store.record("case", identity, revision))
        current = next(c for c in latest_cases(rt.store, case.request.domain_id) if c.id == identity)
        if current.revision != revision or current.status == "approved":
            raise HTTPException(409, "Case changed or was already approved. Reload before deciding.")
        approved = GoldenCase.model_validate(case.model_dump() | {"status": "approved", "approved_by": body.reviewer.strip(), "revision": revision + 1})
        save_case(rt.store, approved)
        return approved.model_dump(mode="json")

    @routes.post("/evaluate")
    def evaluate(domain="ai-act", release: str | None = None, include_holdout: bool = False, case_id: str | None = None):
        rt = runtime()
        cases = latest_cases(rt.store, domain)
        selected = [c for c in cases if (include_holdout or c.split != "holdout") and (case_id is None or c.id == case_id)]
        if case_id and not selected:
            raise HTTPException(404, "Case is unavailable in this domain or is an excluded holdout.")
        scores, scores_at_preview, scores_at_5 = [], [], []
        expert_scores = []
        with rt.lock:
            retriever = rt.get_retriever(domain, release)
            for case in selected:
                result = retriever.search(case.request,
                    result_limit=max(rt.settings.evaluation_k, rt.settings.evaluation_preview_k, 10))
                scores.append(score_case(case, result, k=rt.settings.evaluation_k))
                scores_at_preview.append(score_case(case, result, k=rt.settings.evaluation_preview_k))
                scores_at_5.append(score_case(case, result, k=5))
                expert_scores.append(score_case(case, result, k=10))
            payload = {"id": str(uuid4()), "domain_id": domain, "rag_release_id": retriever.manifest["rag_release_id"],
                "scores": scores, "summary": summarize(scores), "scores_at_preview": scores_at_preview,
                "summary_at_preview": summarize(scores_at_preview), "scores_at_5": scores_at_5,
                "summary_at_5": summarize(scores_at_5), "quality_gate": quality_gate(cases, expert_scores),
                "experiment_gate": experiment_gate(scores, rt.settings.minimum_holdout_recall),
                "configuration": {"fingerprint": rt.settings.config_fingerprint(), "values": rt.settings.editable_config(),
                    "evaluation_k": rt.settings.evaluation_k, "preview_k": rt.settings.evaluation_preview_k}}
            rt.store.append("evaluation", payload["id"], domain, payload)
        return payload

    @routes.get("/evaluations")
    def evaluations(domain="ai-act"):
        return runtime().store.list_records("evaluation", domain, limit=30)

    return routes
