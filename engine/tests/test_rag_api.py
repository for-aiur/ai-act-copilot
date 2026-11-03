import pytest
pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
from fastapi.testclient import TestClient
from aiact.workbench.api import create_app
from aiact.rag.releases import build_release
from aiact.settings import Settings


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
        assert client.get("/api/rag/cases", params={"domain": "ai-act"}).json() == []
    with TestClient(create_app(tmp_path / "legacy.sqlite", settings=settings)) as client:
        cases = client.get("/api/rag/cases", params={"domain": "workbench-api"}).json()
        assert cases[0]["status"] == "approved"
        assert client.get("/api/rag/library", params={"domain": "ai-act"}).json()["total"] == 360
