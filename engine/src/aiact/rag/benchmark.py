"""Fixture import and reproducible scoring. Drafts never become gold implicitly."""
import json
from importlib.resources import files
from pathlib import Path

from .contracts import GoldenCase, RetrievalRequest
from .evaluation import quality_gate, score_case, summarize
from .feedback import latest_cases, save_case
from .official import checksum
from .retriever import HybridRetriever
from .store import Store


def fixture_cases(domain, snapshot_id, rag_release_id):
    name = "ai-act-drafts.json" if domain == "ai-act" else "technical.json"
    data = json.loads(files("aiact").joinpath("data/evaluation/" + name).read_text())
    if data["domain_id"] != domain:
        raise ValueError("Fixture domain mismatch")
    cases = []
    for row in data["cases"]:
        request = RetrievalRequest(domain_id=domain, scenario=row["scenario"], context=row["context"])
        cases.append(GoldenCase(id=row["id"], title=row["title"], request=request, snapshot_id=snapshot_id,
            rag_release_id=rag_release_id, labels=row["labels"], author=row["author"], origin=row["origin"], status=row["status"],
            approved_by=row.get("approved_by"), area=row["area"], split=row["split"]))
    return data["dataset_version"], cases


def seed_fixtures(settings, domain, release_id):
    store = Store(settings.database_url.get_secret_value())
    try:
        manifest = store.release(release_id)
        version, cases = fixture_cases(domain, manifest["snapshot_id"], release_id)
        existing = {c.id for c in latest_cases(store, domain)}
        count = 0
        for case in cases:
            if case.id not in existing:
                save_case(store, case)
                count += 1
        return {"dataset_version": version, "created": count, "existing": len(cases) - count,
                "expert_approved_legal_cases": 0}
    finally:
        store.close()


def benchmark(settings, domain, release_id, dataset=None, include_holdout=False):
    store = Store(settings.database_url.get_secret_value())
    retriever = HybridRetriever(settings, release_id, store=store)
    try:
        if dataset:
            data = json.loads(Path(dataset).read_text())
            cases = [GoldenCase.model_validate(row) for row in data["cases"]]
            dataset_version = checksum(data)
        else:
            cases = latest_cases(store, domain)
            dataset_version = checksum([c.model_dump(mode="json") for c in cases])
        selected = [c for c in cases if include_holdout or c.split != "holdout"]
        scores = []
        for case in selected:
            result = retriever.search(case.request)
            scores.append(score_case(case, result))
        return {"schema_version": "1", "domain_id": domain, "dataset_version": dataset_version,
            "rag_release_id": release_id, "snapshot_id": retriever.snapshot.snapshot_id,
            "scores": scores, "summary": summarize(scores), "quality_gate": quality_gate(cases, scores),
            "draft_count": sum(c.status == "draft" for c in cases),
            "approved_count": sum(c.status == "approved" for c in cases),
            "holdout_included": include_holdout}
    finally:
        retriever.close()
        store.close()
