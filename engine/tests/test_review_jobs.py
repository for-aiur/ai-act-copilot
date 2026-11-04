import pytest
import time

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
from fastapi.testclient import TestClient
from pydantic import SecretStr

from aiact.contracts import Coverage, Metadata, ReviewSession, ScanResult
from aiact.settings import Settings
from aiact.workbench.api import create_app
from aiact.workbench.reviews import IdempotencyConflict, ReviewJobRepository


def _settings(tmp_path):
    return Settings(data_dir=tmp_path, database_url=SecretStr(f"sqlite:///{tmp_path / 'local.sqlite'}"))


def _register(client, email, workspace):
    response = client.post("/api/auth/register", json={"workspace": workspace, "email": email,
        "password": "a-local-password-long-enough"})
    assert response.status_code == 201, response.text
    return response.json()


def test_local_workspaces_isolate_reviews_and_api_keys(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client_a, TestClient(create_app(settings=settings)) as client_b:
        user_a = _register(client_a, "a@example.test", "Workspace A")
        _register(client_b, "b@example.test", "Workspace B")
        assert client_a.get("/api/auth/me").json()["tenant_id"] == user_a["tenant_id"]

        session = ReviewSession(id="review-one", status="complete", scan_result=ScanResult(
            status="complete", coverage=Coverage(), metadata=Metadata()))
        repo = ReviewJobRepository(settings.database_url.get_secret_value())
        job, created = repo.create(user_a["tenant_id"], user_a["id"],
            {"filename": "review.py", "code": "model.generate()"}, "a" * 64, "first-review-key")
        assert created and job["status"] == "queued"
        repo.set_result(job["id"], "complete", session=session)
        repo.close()

        assert client_a.get("/api/reviews/" + job["id"]).status_code == 200
        assert client_a.get("/api/reviews/summary").json()["total"] == 1
        assert client_b.get("/api/reviews/" + job["id"]).status_code == 404
        assert client_b.get("/api/reviews").json() == []
        assert client_b.get("/api/reviews/summary").json()["total"] == 0

        created_key = client_a.post("/api/api-keys", json={"name": "local script"})
        assert created_key.status_code == 201
        secret = created_key.json()["key"]
        assert secret.startswith("actk_")
        assert "key" not in client_a.get("/api/api-keys").json()[0]
        client_a.cookies.clear()
        assert client_a.get("/api/reviews", headers={"Authorization": f"Bearer {secret}"}).status_code == 200
        assert client_a.get("/api/reviews/missing", headers={"Authorization": f"Bearer {secret}"}).status_code == 404
        client_a.post("/api/auth/login", json={"email": "a@example.test", "password": "a-local-password-long-enough"})
        usage = client_a.get("/api/api-usage").json()
        assert any(entry["route"] == "/api/reviews" for entry in usage)
        assert any(entry["route"] == "/api/reviews/missing" and entry["status_code"] == 404 for entry in usage)

        key_id = created_key.json()["id"]
        assert client_a.delete("/api/api-keys/" + key_id).status_code == 200
        client_a.cookies.clear()
        assert client_a.get("/api/reviews", headers={"Authorization": f"Bearer {secret}"}).status_code == 401


def test_review_job_idempotency_and_restart_state(tmp_path):
    url = _settings(tmp_path).database_url.get_secret_value()
    first = ReviewJobRepository(url)
    payload = {"filename": "review.py", "code": "model.generate()"}
    job, created = first.create("tenant-a", "user-a", payload, "b" * 64, "same-key-123")
    same, created_again = first.create("tenant-a", "user-a", payload, "b" * 64, "same-key-123")
    assert created and not created_again and job["id"] == same["id"]
    with pytest.raises(IdempotencyConflict):
        first.create("tenant-a", "user-a", payload | {"code": "different"}, "c" * 64, "same-key-123")
    first.close()

    reopened = ReviewJobRepository(url)
    restored = reopened.get(job["id"], "tenant-a")
    assert restored["status"] == "queued"
    assert restored["request"]["code"] == "model.generate()"
    assert [event["type"] for event in restored["events"]] == ["queued"]
    assert reopened.get(job["id"], "tenant-b") is None
    reopened.close()


def test_login_requires_valid_password_and_logout_revokes_session(tmp_path):
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        assert client.post("/api/auth/register", json={"workspace": "Test", "email": "bad@example.test",
            "password": "short"}).status_code == 422
        _register(client, "user@example.test", "Test")
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json={"email": "user@example.test",
            "password": "a-local-password-long-enough"}).status_code == 200
        assert client.post("/api/auth/login", json={"email": "user@example.test", "password": "wrong"}).status_code == 401


def test_review_job_runs_resumes_and_survives_app_restart(tmp_path, monkeypatch):
    from aiact.rag.releases import build_release
    from aiact.rag.store import Store
    from test_full_review import FixtureProvider

    settings = Settings(data_dir=tmp_path, database_url=SecretStr(f"sqlite:///{tmp_path / 'e2e.sqlite'}"), provider="ollama")
    release = build_release(settings, lexical_only=True)
    store = Store(settings.database_url.get_secret_value())
    store.activate("ai-act", release["rag_release_id"])
    store.close()
    fixture = FixtureProvider()

    class FakeOllama:
        name = "ollama"
        model = "test-ollama-model"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_local_model(self):
            pass

        def generate_json(self, prompt, schema, timeout):
            return fixture.generate_json(prompt, schema, timeout)

    monkeypatch.setattr("aiact.providers.Ollama", FakeOllama)
    source = "def reply(model, text):\n    return model.generate(text)\n"
    with TestClient(create_app(settings=settings)) as client:
        _register(client, "reviewer@example.test", "Review workspace")
        started = client.post("/api/reviews", json={"code": source, "filename": "chat.py"},
            headers={"Idempotency-Key": "demo-review-0001"})
        assert started.status_code == 202, started.text
        identity = started.json()["id"]
        duplicate = client.post("/api/reviews", json={"code": source, "filename": "chat.py"},
            headers={"Idempotency-Key": "demo-review-0001"})
        assert duplicate.json()["id"] == identity

        deadline = time.monotonic() + 10
        current = client.get("/api/reviews/" + identity).json()
        while current["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            current = client.get("/api/reviews/" + identity).json()
        assert current["status"] == "context_needed", current.get("error") or current.get("session", {}).get("scan_result")
        assert {step["stage"] for step in current["timings"]} >= {"code_collection", "purpose_extraction", "legal_retrieval"}
        assert current["sources"] and current["retrieval_request"]
        question = current["session"]["context_question"]
        assert question and question.endswith("?")

        accepted = client.post("/api/reviews/" + identity + "/answer", json={
            "answer": "Every user sees a clear notice before the first generated reply."})
        assert accepted.status_code == 202
        deadline = time.monotonic() + 10
        current = client.get("/api/reviews/" + identity).json()
        while current["status"] in {"answer_queued", "running", "queued"} and time.monotonic() < deadline:
            time.sleep(0.05)
            current = client.get("/api/reviews/" + identity).json()
        assert current["status"] == "complete", current
        assert any(event["type"] == "answer_queued" for event in current["events"])
        assert any(event["type"] == "context_answered" for event in current["session"]["history"])
        feedback = client.post(f"/api/reviews/{identity}/retrieval-feedback", json={
            "source_id": current["sources"][0]["id"], "label": "relevant", "reason": "Supports this scenario."})
        assert feedback.status_code == 201, feedback.text
        saved = client.get("/api/reviews/" + identity).json()
        assert any(event["type"] == "feedback_saved" for event in saved["events"])

    with TestClient(create_app(settings=settings)) as restarted:
        _register(restarted, "other@example.test", "Other workspace")
        assert restarted.get("/api/reviews/" + identity).status_code == 404
