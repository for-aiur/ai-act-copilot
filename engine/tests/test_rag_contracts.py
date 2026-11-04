import pytest
from pydantic import ValidationError
from aiact.rag.contracts import GoldLabel, GoldenCase, RetrievalRequest, ScenarioContext
from aiact.rag.domains import load_snapshot, resolve_reference


def test_domains_are_separate_and_source_offsets_validated():
    legal, technical = load_snapshot(), load_snapshot("workbench-api")
    assert legal.complete and technical.complete
    assert not {d.id for d in legal.documents} & {d.id for d in technical.documents}
    assert resolve_reference("ai-act", "Article 75a and Annex XIV") == ("article-75a", "annex-xiv")
    assert resolve_reference("workbench-api", "check /api/health") == ("health",)
    chunk = technical.chunks[0].model_dump()
    with pytest.raises(ValidationError, match="offset"):
        type(technical).model_validate(technical.model_dump() | {"chunks": [chunk | {"start": 1}]})


def test_context_and_domain_are_part_of_identity_and_gold_requires_attribution():
    request = RetrievalRequest(scenario="Review applicant scoring")
    assert request.fingerprint() != request.model_copy(update={"context": ScenarioContext(actor_role="employer")}).fingerprint()
    assert request.fingerprint() != request.model_copy(update={"domain_id": "workbench-api"}).fingerprint()
    with pytest.raises(ValidationError, match="Approval"):
        GoldenCase(id="test", title="Case", request=request, snapshot_id="x", rag_release_id="y", author="author", status="approved")
    with pytest.raises(ValidationError, match="Conflicting"):
        GoldenCase(id="test", title="Case", request=request, snapshot_id="x", rag_release_id="y", author="author",
            labels=(GoldLabel(document_id="x", label="relevant", rationale="reason"), GoldLabel(document_id="x", label="not_relevant", rationale="reason")))
