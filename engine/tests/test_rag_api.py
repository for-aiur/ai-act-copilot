import pytest
pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
from fastapi.testclient import TestClient
from aiact.workbench.api import create_app
from aiact.rag.releases import build_release
from aiact.rag.store import Store
from aiact.settings import Settings
from pathlib import Path


def test_workbench_case_annotation_approval_and_restart(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "db.sqlite"))
    release = build_release(settings, "workbench-api", lexical_only=True)
    with TestClient(create_app(tmp_path / "legacy.sqlite", settings=settings)) as client:
        library = client.get("/api/rag/library", params={"domain": "workbench-api"}).json()
        assert library["total"] == 3
        assert client.post("/api/rag/activate/" + release["rag_release_id"], params={"domain": "workbench-api"}).status_code == 200
        run = client.post("/api/rag/retrieve", json={"domain_id": "workbench-api", "scenario": "health checks", "limit": 1}).json()
        assert run["result"]["candidates"][0]["document"]["id"] == "health"
        case = {"id": "api-test", "title": "Readiness", "request": run["result"]["request"], "snapshot_id": run["result"]["snapshot_id"], "rag_release_id": run["result"]["rag_release_id"],
            "author": "Test reviewer", "labels": [{"document_id": "health", "label": "must_retrieve", "rationale": "Readiness source"}, {"document_id": "drafts", "label": "must_retrieve", "rationale": "Missing source test"}]}
        assert client.post("/api/rag/cases", json=case).status_code == 201
        assert client.post("/api/rag/cases", json=case).status_code == 409
        approved = client.post("/api/rag/cases/api-test/1/approve", json={"reviewer": "Explicit local reviewer"})
        assert approved.status_code == 200 and approved.json()["revision"] == 2
        evaluation = client.post("/api/rag/evaluate", params={"domain": "workbench-api"}).json()
        assert evaluation["scores"][0]["missed_required"] == ["drafts"]
        assert evaluation["quality_gate"]["status"] == "blocked"
        single = client.post("/api/rag/evaluate", params={"domain": "workbench-api", "case_id": "api-test"}).json()
        assert single["summary"]["cases"] == 1 and single["summary_at_5"]["cases"] == 1
        assert client.post("/api/rag/evaluate", params={"domain": "ai-act", "case_id": "api-test"}).status_code == 404
        assert client.get("/api/rag/cases", params={"domain": "ai-act"}).json() == []
    with TestClient(create_app(tmp_path / "legacy.sqlite", settings=settings)) as client:
        cases = client.get("/api/rag/cases", params={"domain": "workbench-api"}).json()
        assert cases[0]["status"] == "approved"
        assert client.get("/api/rag/library", params={"domain": "ai-act"}).json()["total"] == 360


def test_onboarding_preview_returns_inline_feedback_without_saving_runs(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "preview.sqlite"),
        provider="ollama")
    manifest = build_release(settings, lexical_only=True)
    store = Store(settings.database_url.get_secret_value())
    store.activate("ai-act", manifest["rag_release_id"])
    store.close()

    def fake_review(source, provider, retriever, context, **kwargs):
        assert context == "Visitor question to focus the review (unverified): Who checks the ranking?"
        return {"scan_result": {"status":"complete", "findings":[], "errors":[]}}
    monkeypatch.setattr("aiact.rag.review.review_python", fake_review)
    sample = Path(__file__).parents[2] / "examples/recruitment/bias_audit.py"
    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/api/rag/preview", json={"filename":sample.name,"code":sample.read_text(),
            "question":"Who checks the ranking?"})
        assert response.status_code == 200, response.text
        assert response.json() == {"status":"complete", "findings":[], "errors":[]}
        assert client.get("/api/rag/reviews").json() == []
        assert client.get("/api/rag/runs").json() == []
