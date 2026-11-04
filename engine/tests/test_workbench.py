import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from aiact.workbench.api import create_app


def test_real_corpus_search_and_provenance(tmp_path):
    client = TestClient(create_app(tmp_path / "db.sqlite"))
    corpus = client.get("/api/corpus").json()
    assert corpus["coverage"] == "legacy_subset"
    assert corpus["total"] == 114
    found = client.get("/api/corpus", params={"q": "Annex III 4(a)"}).json()
    assert any(s["id"] == "annex-iii-4-a" for s in found["sections"])
    assert all(s["url"].startswith("https://ai-act-service-desk.ec.europa.eu/") for s in corpus["sections"])
    assert client.get("/api/corpus", params={"q": "nonexistentxyz"}).json()["sections"] == []
    assert client.get("/api/health").json() == {"status": "ready", "inference": "disabled"}


def test_draft_persists_across_app_restart_and_rejects_stale_sources(tmp_path):
    database = tmp_path / "db.sqlite"
    client = TestClient(create_app(database))
    corpus = client.get("/api/corpus").json()
    draft = {"title": "Recruitment", "scenario": "Rank applicants", "context": "Employer", "source_ids": ["annex-iii-4-a"], "corpus_checksum": corpus["checksum"]}
    saved = client.post("/api/drafts", json=draft)
    assert saved.status_code == 201
    restarted = TestClient(create_app(database))
    assert restarted.get("/api/drafts").json() == [saved.json()]
    assert saved.json()["status"] == "draft"
    assert client.post("/api/drafts", json=draft | {"source_ids": ["invented"]}).status_code == 422
    assert client.post("/api/drafts", json=draft | {"corpus_checksum": "a" * 64}).status_code == 409
    assert client.post("/api/drafts", json=draft | {"title": " "}).status_code == 422


def test_local_host_and_write_origin_protection(tmp_path):
    client = TestClient(create_app(tmp_path / "db.sqlite"))
    assert client.get("/api/corpus", headers={"host": "evil.example"}).status_code == 400
    assert client.post("/api/drafts", json={}, headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/drafts", json={}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
