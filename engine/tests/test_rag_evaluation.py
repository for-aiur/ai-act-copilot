import pytest
pytest.importorskip("sqlalchemy")
from aiact.rag.contracts import GoldenCase, GoldLabel, RetrievalRequest
from aiact.rag.domains import load_snapshot
from aiact.rag.evaluation import quality_gate, score_case
from aiact.rag.feedback import save_case, latest_cases
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.rag.store import Store
from aiact.settings import Settings


def test_missing_source_is_false_negative_and_draft_cannot_pass_quality_gate(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "db.sqlite"))
    manifest = build_release(settings, "workbench-api", lexical_only=True)
    store = Store(settings.database_url.get_secret_value())
    retriever = HybridRetriever(settings, manifest["rag_release_id"], store=store)
    request = RetrievalRequest(domain_id="workbench-api", scenario="health readiness", limit=1)
    result = retriever.search(request)
    case = GoldenCase(id="case", title="Readiness", request=request, snapshot_id=result.snapshot_id,
        rag_release_id=result.rag_release_id, author="test author",
        labels=(GoldLabel(document_id="health", label="must_retrieve", rationale="Readiness source"),
                GoldLabel(document_id="drafts", label="must_retrieve", rationale="Deliberately missed source")))
    save_case(store, case)
    score = score_case(case, result)
    assert score["missed_required"] == ["drafts"]
    assert score["recall"] == .5
    assert quality_gate([case], [score])["status"] == "blocked"
    second = case.model_copy(update={"revision": 2, "status": "approved", "approved_by": "explicit reviewer"})
    save_case(store, second)
    assert latest_cases(store, "workbench-api") == [second]
    assert store.record("case", "case", 1)["status"] == "draft"
    assert latest_cases(store, "ai-act") == []
    with pytest.raises(ValueError, match="reference"):
        save_case(store, case.model_copy(update={"id": "bad", "labels": (GoldLabel(document_id="made-up", label="relevant", rationale="No source"),)}))
    retriever.close()
    store.close()
