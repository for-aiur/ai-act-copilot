import pytest
pytest.importorskip("sqlalchemy")
from aiact.rag.contracts import RetrievalRequest, ScenarioContext
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.settings import Settings


def test_lexical_baseline_domain_context_and_explicit_reference(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "db.sqlite"))
    release = build_release(settings, lexical_only=True)
    retriever = HybridRetriever(settings, release["rag_release_id"])
    result = retriever.search(RetrievalRequest(scenario="Article 113 high-risk application dates"))
    assert result.candidates[0].document.id == "article-113"
    assert result.stages["lexical"] and result.stages["exact"]
    assert result.snapshot_id == retriever.snapshot.snapshot_id
    assert all(c.document.text[c.chunk.start:c.chunk.end] == c.chunk.text for c in result.candidates)
    assert any("Lexical baseline" in w for w in result.warnings)
    with pytest.raises(ValueError, match="domains differ"):
        retriever.search(RetrievalRequest(domain_id="workbench-api", scenario="health"))
    changed = retriever.search(RetrievalRequest(scenario="Article 113 high-risk application dates", context=ScenarioContext(actor_role="deployer")))
    assert changed.context_fingerprint != result.context_fingerprint
    retriever.close()


def test_same_core_handles_technical_reference_domain(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "db.sqlite"))
    release = build_release(settings, "workbench-api", lexical_only=True)
    retriever = HybridRetriever(settings, release["rag_release_id"])
    for scenario, expected in [("health database readiness", "health"), ("drafts scenario persistence", "drafts")]:
        result = retriever.search(RetrievalRequest(domain_id="workbench-api", scenario=scenario))
        assert result.candidates[0].document.id == expected
    retriever.close()
