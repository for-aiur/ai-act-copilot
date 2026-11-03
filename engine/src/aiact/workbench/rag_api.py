"""Local workbench endpoints. One serialized owner for the embedded vector path."""
import threading
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from aiact.rag.contracts import GoldenCase, RetrievalRequest, RetrievalResult
from aiact.rag.domains import DOMAINS, load_snapshot
from aiact.rag.evaluation import quality_gate, score_case, summarize
from aiact.rag.feedback import latest_cases, save_case, save_run
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.rag.store import Store
from aiact.settings import load_settings


class BuildInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_id: str = "ai-act"
    download_model: bool = False
    lexical_only: bool = False


class ApprovalInput(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)


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

    @routes.get("/domains")
    def domains():
        rt = runtime()
        return [d.model_dump() | {"active": rt.store.pointer(d.id)} for d in DOMAINS]

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
            "kinds": sorted({d.kind for d in snapshot.documents}), "documents": docs}

    @routes.get("/versions")
    def versions(domain="ai-act"):
        rt = runtime()
        return {"active": rt.store.pointer(domain), "previous": rt.store.pointer(domain, "previous"), "releases": rt.store.list_releases(domain),
                "provider": rt.settings.provider, "model": rt.settings.model, "cloud_key_configured": bool(rt.settings.gemini_api_key.get_secret_value()),
                "tracing_enabled": rt.settings.langfuse_enabled}

    @routes.post("/build")
    def build(body: BuildInput):
        rt = runtime()
        if body.domain_id not in {d.id for d in DOMAINS}:
            raise HTTPException(422, "Unknown domain")
        with rt.lock:
            return build_release(rt.settings, body.domain_id, body.download_model, body.lexical_only)

    @routes.post("/activate/{identity}")
    def activate(identity: str, domain="ai-act"):
        rt = runtime()
        with rt.lock:
            from aiact.rag.releases import verify_bundle
            manifest, _, _ = verify_bundle(rt.settings.data_dir / "releases" / identity)
            if manifest["domain_id"] != domain:
                raise HTTPException(409, "Release belongs to a different domain.")
            rt.store.activate(domain, identity)
            return {"active": identity, "quality_status": manifest["quality_status"], "scope": "local_tooling_candidate"}

    @routes.post("/retrieve")
    def retrieve(body: RetrievalRequest):
        rt = runtime()
        with rt.lock:
            result = rt.get_retriever(body.domain_id).search(body)
            identity = save_run(rt.store, result)
        return {"id": identity, "result": result.model_dump(mode="json")}

    @routes.get("/runs")
    def runs(domain="ai-act"):
        return runtime().store.list_records("retrieval", domain, limit=30)

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
    def evaluate(domain="ai-act", release: str | None = None, include_holdout: bool = False):
        rt = runtime()
        cases = latest_cases(rt.store, domain)
        selected = [c for c in cases if include_holdout or c.split != "holdout"]
        scores = []
        with rt.lock:
            retriever = rt.get_retriever(domain, release)
            for case in selected:
                result = retriever.search(case.request)
                scores.append(score_case(case, result))
            payload = {"id": str(uuid4()), "domain_id": domain, "rag_release_id": retriever.manifest["rag_release_id"],
                "scores": scores, "summary": summarize(scores), "quality_gate": quality_gate(cases, scores)}
            rt.store.append("evaluation", payload["id"], domain, payload)
        return payload

    @routes.get("/evaluations")
    def evaluations(domain="ai-act"):
        return runtime().store.list_records("evaluation", domain, limit=30)

    return routes
