import pytest
from sqlalchemy import create_engine
from aiact.workbench.findings import CustomerFindings


def test_tenant_replay_stale_head_and_decision(tmp_path):
    store = CustomerFindings(create_engine("sqlite:///" + str(tmp_path / "customer.db")))
    store.bind("a", "1", "10", "demo/recruitment")
    record = {"id": "f1", "priority": "high", "title": "Review use"}
    store.ingest("10", "1", 2, "sha1", [record])
    store.ingest("10", "1", 2, "sha1", [record])
    assert len(store.list("a")) == 1
    assert not store.list("b")
    with pytest.raises(ValueError):
        store.ingest("unknown", "1", 2, "sha1", [record])
    with pytest.raises(LookupError):
        store.decide("b", "1:2:f1", "sha1", "resolved", "user", "checked", "event-1")
    with pytest.raises(ValueError):
        store.decide("a", "1:2:f1", "old", "resolved", "user", "checked", "event-1")
    first = store.decide("a", "1:2:f1", "sha1", "acknowledged", "user", "", "event-1")
    assert store.decide("a", "1:2:f1", "sha1", "acknowledged", "user", "", "event-1") == first
    assert len(store.history("a", "1:2:f1")) == 1
    store.ingest("10", "1", 2, "sha2", [record])
    assert store.list("a")[0]["state"] == "open"


def test_retry_github_sync_and_pr_reply_share_decision_handler(tmp_path):
    store = CustomerFindings(create_engine("sqlite:///" + str(tmp_path / "customer.db")))
    store.bind("a", "1", "10", "demo/recruitment")
    store.ingest("10", "1", 2, "sha1", [
        {"id": "f1", "priority": "high"}, {"id": "f2", "priority": "medium"}])

    class FakeGitHub:
        receipts = {}
        fail = True
        def current_head(self, repo, pr):
            return "sha1"
        def apply_decision(self, decision, idempotency_key):
            self.receipts[idempotency_key] = decision["action"]
            if self.fail:
                self.fail = False
                raise OSError("temporary outage")

    client = FakeGitHub()
    store.decide("a", "1:2:f1", "sha1", "resolved", "dashboard-user", "Code fixed", "dashboard-1")
    with pytest.raises(OSError):
        store.sync("a", "dashboard-1", client)
    assert store.history("a", "1:2:f1")[0]["sync_status"] == "pending"
    store.sync("a", "dashboard-1", client)
    store.sync("a", "dashboard-1", client)
    store.decide("a", "1:2:f2", "sha1", "false_positive", "github-user", "Explicit human review", "pr-reply-1")
    store.sync("a", "pr-reply-1", client)
    assert len(client.receipts) == 2
    assert {r["state"] for r in store.list("a")} == {"resolved", "false_positive"}


def test_trusted_bot_adapter_import_is_idempotent_and_tenant_scoped(tmp_path):
    from sqlalchemy import create_engine
    from aiact.github_bot.store import Store
    from aiact.workbench.github_adapter import GitHubFindingAdapter
    engine = create_engine("sqlite:///" + str(tmp_path / "adapter.db"))
    bot = Store(tmp_path / "bot.sqlite3")
    bot.reconcile("org/repo", 7, "head-a", "policy", [{
        "id":"a"*20, "priority":"high", "roles":["write"], "evidence_hash":"evidence", "policy_hash":"policy",
        "payload":{"id":"a"*20,"title":"Review candidate ranking","kind":"potential_issue","priority":"high",
            "explanation":"A score changes hiring order.","evidence":{"path":"src/rank.py","start_line":2,"end_line":2,"quote":"model.predict(x)"},
            "citations":[],"suggested_next_action":"Check use.","context_question":None}}
    ], ["src/rank.py"], "run-1")
    customer = CustomerFindings(engine)
    customer.bind("tenant-a", "repo-id", "install-1", "org/repo")
    adapter = GitHubFindingAdapter(engine, bot, object(), object())
    adapter.import_pr("install-1", "repo-id", "org/repo", 7, "head-a")
    adapter.import_pr("install-1", "repo-id", "org/repo", 7, "head-a")
    assert len(customer.list("tenant-a")) == 1
    assert customer.list("tenant-b") == []
    with pytest.raises(ValueError, match="Unknown repository installation"):
        adapter.import_pr("unknown-install", "repo-id", "org/repo", 7, "head-a")

def test_customer_api_filters_tenants(tmp_path):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from aiact.settings import Settings
    from aiact.workbench.api import create_app
    settings = Settings(data_dir=tmp_path, database_url=SecretStr("sqlite:///" + str(tmp_path / "app.db")))
    with TestClient(create_app(settings=settings)) as client:
        user = client.post("/api/auth/register", json={"workspace":"One", "email":"one@example.test",
            "password":"long-enough-test-password"}).json()
        store = CustomerFindings(create_engine(settings.database_url.get_secret_value()))
        store.bind(user["tenant_id"], "1", "10", "demo/repo")
        store.ingest("10", "1", 1, "sha", [{"id":"f", "priority":"high"}])
        assert client.get("/api/customer/overview").json()["open_high"] == 1
        assert client.get("/api/customer/usage").json()["completed_reviews"] == 0
        response = client.post("/api/findings/1:1:f/decision", json={
            "head":"sha", "action":"resolved", "reason":"Checked", "event_id":"test-event-1"})
        assert response.status_code == 200
        assert client.get("/api/customer/overview").json()["resolved_recently"] == 1


def test_synthetic_demo_both_paths(tmp_path):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from aiact.settings import Settings
    from aiact.workbench.identity import IdentityStore
    from aiact.workbench.api import create_app
    settings = Settings(demo_mode=True, data_dir=tmp_path,
        database_url=SecretStr("sqlite:///" + str(tmp_path / "demo.db")))
    identity = IdentityStore(settings.database_url.get_secret_value())
    other = identity.register("Other workspace", "other@example.test", "long-enough-test-password")
    other_cookie = identity.create_session(other["id"])
    identity.close()
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/api/demo/seed").status_code == 401
        client.cookies.set("aiact_session", other_cookie)
        assert client.post("/api/demo/seed").status_code == 403
        client.cookies.clear()
        assert client.post("/api/auth/demo").status_code == 200
        assert client.post("/api/demo/seed").status_code == 200
        rows = client.get("/api/findings").json()
        assert len(rows) == 5
        overview = client.get("/api/customer/overview").json()
        repo_rows = {item["name"]: item for item in overview["repositories"]}
        assert repo_rows["example/unreviewed"]["latest_review_at"] is None
        assert repo_rows["example/unreviewed"]["latest_review_outcome"] is None
        assert repo_rows["example/recruitment"]["latest_review_outcome"] == "complete"
        assert repo_rows["example/recruitment"]["open_high"] == 2
        assert repo_rows["example/recruitment"]["policies"] == [
            {"id": "annex-iii", "total": 2, "open": 2},
            {"id": "article-14", "total": 2, "open": 2},
        ]
        assert overview["policies"][0] == {"id": "article-50", "total": 3, "open": 3}
        assert next(row for row in rows if row["pr"] == "14")["policies"] == ["annex-iii", "article-14"]
        assert [item["priority"] for item in overview["needs_review"]] == ["high", "high", "medium", "medium", "low"]
        assert len({item["branch"] for item in overview["needs_review"]}) == 5
        assert overview["open_by_code_stage"]["released"]["high"] == 1
        assert overview["open_by_code_stage"]["merged"]["low"] == 1
        assert sum(overview["open_by_code_stage"]["open_pr"].values()) == 3
        project_path = "/api/customer/projects"
        created = client.post(project_path, json={"name": "Hiring", "repository_ids": ["demo-recruitment"]})
        assert created.status_code == 201
        project_id = created.json()["id"]
        scope = {"project": project_id}
        assert client.post(project_path, json={"name": "Shared", "repository_ids": ["demo-recruitment"]}).status_code == 201
        assert len(client.get("/api/findings").json()) == 5
        scoped = client.get("/api/customer/overview", params=scope).json()
        assert [repo["id"] for repo in scoped["repositories"]] == ["demo-recruitment"]
        assert scoped["open_high"] == 2
        assert len(client.get("/api/findings", params=scope).json()) == 2
        assert client.put(f"{project_path}/{project_id}", json={"name": "Hiring", "repository_ids": []}).status_code == 200
        assert client.get("/api/findings", params=scope).json() == []
        assert client.put(f"{project_path}/{project_id}", json={"name": "Hiring", "repository_ids": ["missing"]}).status_code == 422
        demo_cookie = client.cookies.get("aiact_session")
        client.cookies.clear()
        client.cookies.set("aiact_session", other_cookie)
        assert client.get("/api/customer/overview", params=scope).status_code == 404
        assert client.get(project_path).json() == []
        client.cookies.clear()
        client.cookies.set("aiact_session", demo_cookie)
        for row, route in zip((row for row in rows if row["pr"] == "1"), ["decision", "pr-reply"]):
            prefix = "/api/findings/" if route == "decision" else "/api/demo/findings/"
            result = client.post(prefix + row["id"] + "/" + route, json={
                "head": row["head"], "action": "resolved", "reason": "Reviewed synthetic example",
                "event_id": "demo-event-" + route})
            assert result.status_code == 200, result.text
            history = client.get("/api/findings/" + row["id"] + "/history").json()
            assert history[0]["sync_status"] == "synced"
        assert client.get("/api/customer/overview").json()["resolved_recently"] == 2
        client.post("/api/demo/seed")
        assert sum(row["state"] == "resolved" for row in client.get("/api/findings").json()) == 2
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.post("/api/auth/demo").status_code == 200
        rows = restarted.get("/api/findings").json()
        assert sum(row["state"] == "resolved" for row in rows) == 2
        pr_row = next(row for row in rows if row["name"] == "example/chatbot" and row["pr"] == "1")
        duplicate = restarted.post("/api/demo/findings/" + pr_row["id"] + "/pr-reply", json={
            "head": pr_row["head"], "action": "resolved", "reason": "Reviewed synthetic example",
            "event_id": "demo-event-pr-reply"})
        assert duplicate.status_code == 200
        assert len(restarted.get("/api/findings/" + pr_row["id"] + "/history").json()) == 1


def test_synthetic_examples_have_grounded_distinct_code_and_sources(tmp_path):
    import json
    from importlib.resources import files
    from sqlalchemy import create_engine
    from aiact.workbench.findings import seed_demo
    store = CustomerFindings(create_engine("sqlite:///" + str(tmp_path / "seed.db")))
    seed_demo(store, "tenant")
    rows = store.list("tenant")
    assert len(rows) == 5
    assert all(row["payload"]["source_type"] == "simulated_github" for row in rows)
    assert all(row["payload"]["evidence"]["start_line"] == 2 for row in rows)
    assert len({row["payload"]["code_sample"] for row in rows}) == 2
    corpus = json.loads(files("aiact").joinpath("data/corpus.json").read_text())
    legal = {section["id"]: section for section in corpus["sections"]}
    for row in rows:
        citation = row["payload"]["citations"][0]
        assert citation["quote"] in legal[citation["section_id"]]["text"]
        assert citation["url"] == legal[citation["section_id"]]["url"]


def test_local_review_findings_link_back_and_preserve_partial_or_failed_status(tmp_path):
    from sqlalchemy import create_engine
    from aiact.contracts import Coverage, Evidence, Finding, Metadata, ReviewSession, ScanError, ScanResult
    from aiact.workbench.findings import add_review_findings
    store = CustomerFindings(create_engine("sqlite:///" + str(tmp_path / "review-results.db")))
    store.bind("tenant", "local-reviews", "local-workspace", "Local code reviews")
    finding = Finding(id="f1", title="Check human review", explanation="A score changes candidate order.",
        kind="potential_issue", priority="high", evidence=Evidence(path="review.py", start_line=2,
        end_line=2, quote="scores = model.predict(candidates)"), citations=[{"section_id":"annex-iii-4-a",
        "quote":"Recruitment or selection of natural persons", "url":"https://example.test/law"}],
        suggested_next_action="Check the actual use.", context_question="Can a person override the score?")
    partial = ReviewSession(id="job-partial", status="partial", scan_result=ScanResult(status="partial",
        findings=[finding], coverage=Coverage(), metadata=Metadata()))
    add_review_findings(store, "tenant", "job-partial", partial, "2026-11-04T10:00:00+00:00")
    row, = store.list("tenant")
    assert store.inventory("tenant") == []
    assert row["payload"]["source_type"] == "local_review"
    assert row["payload"]["source_review_id"] == "job-partial"
    assert row["payload"]["review_status"] == "partial"
    failed = ReviewSession(id="job-failed", status="failed", scan_result=ScanResult(status="failed",
        errors=[ScanError(code="timeout", message="Synthetic failure")], coverage=Coverage(), metadata=Metadata()))
    add_review_findings(store, "tenant", "job-failed", failed, "2026-11-04T11:00:00+00:00")
    assert len(store.list("tenant")) == 1
    assert store.inventory("tenant") == []

    add_review_findings(store, "another-tenant", "job-partial", partial, "2026-11-04T10:00:00+00:00")
    other, = store.list("another-tenant")
    assert row["repository_id"] == "local-reviews"
    assert other["repository_id"] == "local-reviews:another-tenant"
    assert row["id"] != other["id"]
    assert store.inventory("another-tenant") == []


def test_customer_usage_counts_distinct_completed_jobs_and_configured_estimate(tmp_path):
    from datetime import datetime, timedelta, timezone
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from aiact.contracts import ReviewSession, ScanResult, Coverage, Metadata
    from aiact.settings import Settings
    from aiact.workbench.api import create_app
    from aiact.workbench.reviews import ReviewJobRepository
    settings = Settings(data_dir=tmp_path, review_unit_price=2.0, billing_currency="EUR",
        database_url=SecretStr("sqlite:///" + str(tmp_path / "usage.db")))
    with TestClient(create_app(settings=settings)) as client:
        user = client.post("/api/auth/register", json={"workspace":"Usage", "email":"usage@example.test",
            "password":"long-enough-test-password"}).json()
        repository = ReviewJobRepository(settings.database_url.get_secret_value())
        session = ReviewSession(id="usage-session", status="complete", scan_result=ScanResult(
            status="complete", coverage=Coverage(), metadata=Metadata()))
        for index in range(3):
            job, created = repository.create(user["tenant_id"], user["id"], {"filename":"x.py","code":"pass"},
                str(index) * 64, f"usage-key-{index}")
            assert created
            repository.set_result(job["id"], "complete", session=session)
            duplicate, duplicate_created = repository.create(user["tenant_id"], user["id"],
                {"filename":"x.py","code":"pass"}, str(index) * 64, f"usage-key-{index}")
            assert not duplicate_created and duplicate["id"] == job["id"]
        usage = client.get("/api/customer/usage").json()
        assert usage["completed_reviews"] == 3
        assert usage["api_requests"] == 0
        assert usage["estimated_charge"] == 6.0
        assert usage["currency"] == "EUR"
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        old_job, _ = repository.create(user["tenant_id"], user["id"], {"filename":"x.py","code":"pass"},
            "d" * 64, "usage-key-last-month")
        repository.set_result(old_job["id"], "complete", session=session)
        with repository.engine.begin() as db:
            from aiact.workbench.reviews import events
            db.execute(events.update().where(events.c.job_id == old_job["id"], events.c.type == "complete")
                .values(created_at=(start - timedelta(seconds=1)).isoformat()))
            repository._event(db, job["id"], "complete")
        usage = client.get("/api/customer/usage").json()
        assert usage["completed_reviews"] == 3
        repository.close()


def test_false_positive_approval_preserves_open_until_distinct_approver(tmp_path):
    from sqlalchemy import create_engine
    store = CustomerFindings(create_engine("sqlite:///" + str(tmp_path / "false-positive.db")))
    store.bind("tenant", "repo", "install", "example/repo")
    store.ingest("install", "repo", 7, "sha", [{"id":"f", "priority":"high"}])
    identity = "repo:7:f"
    immediate = store.decide("tenant", identity, "sha", "false_positive", "reviewer", "", "mark-first")
    assert immediate["action"] == "false_positive"
    assert store.list("tenant")[0]["state"] == "false_positive"
    store.decide("tenant", identity, "sha", "open", "reviewer", "", "reopen-first")
    store.set_fp_policy("tenant", "approval", "approver")
    pending = store.decide("tenant", identity, "sha", "false_positive", "bot-reviewer", "", "mark-second", "missing_context")
    assert pending["action"] == "fp_pending"
    assert store.list("tenant")[0]["state"] == "open"
    with pytest.raises(PermissionError):
        store.decide("tenant", identity, "sha", "fp_approve", "bot-reviewer", "", "self-approve")
    store.decide("tenant", identity, "sha", "fp_approve", "approver", "", "valid-approve")
    assert store.list("tenant")[0]["state"] == "false_positive"
    assert store.fp_marks("tenant")[identity]["category"] == "missing_context"
    assert len(store.fp_submissions("tenant")) == 2
    assert store.fp_submissions("other") == []


def test_legacy_decision_schema_can_be_opened_concurrently(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    engine = create_engine("sqlite:///" + str(tmp_path / "legacy.db"))
    CustomerFindings(engine)
    with engine.begin() as db:
        db.exec_driver_sql("ALTER TABLE aiact_customer_decisions DROP COLUMN category")
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(lambda _: CustomerFindings(engine).fp_marks("tenant"), range(3))) == [{}, {}, {}]


def test_unsure_routes_open_finding_to_legal_until_decided(tmp_path):
    store = CustomerFindings(create_engine("sqlite:///" + str(tmp_path / "legal.db")))
    store.bind("tenant", "repo", "install", "example/repo")
    store.ingest("install", "repo", 7, "sha", [{"id":"f", "priority":"high"}])
    identity = "repo:7:f"
    store.decide("tenant", identity, "sha", "unsure", "developer", "Check applicability", "unsure-one")
    assert store.legal_requests("tenant")[identity]["reason"] == "Check applicability"
    assert store.legal_requests("other") == {}
    assert store.list("tenant")[0]["state"] == "open"
    store.decide("tenant", identity, "sha", "resolved", "legal", "Checked source", "legal-resolve")
    assert store.legal_requests("tenant") == {}
    assert store.list("tenant")[0]["state"] == "resolved"


def test_project_ai_inventory_and_release_evidence_are_scoped_and_persistent(tmp_path):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from aiact.settings import Settings
    from aiact.workbench.api import create_app

    settings = Settings(data_dir=tmp_path, demo_mode=True,
        database_url=SecretStr("sqlite:///" + str(tmp_path / "inventory.db")))
    root = "/api/customer/projects"
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/api/auth/demo").status_code == 200
        seed_response = client.post("/api/demo/ai-systems")
        assert seed_response.status_code == 200, seed_response.text
        seed = seed_response.json()
        assert client.post("/api/demo/ai-systems").json() == seed
        project = client.post(root, json={"name": "Test project"}).json()["id"]
        base = f"{root}/{seed['project_id']}/ai-systems"
        data = client.get(base).json()
        assert len(data["systems"]) == 3
        assert len(data["links"]) == 2
        evidence_path = f"{base}/{seed['system_id']}/evidence"
        original, = client.get(evidence_path).json()
        assert original["demo"] and original["repository"] == "example/health-pricing"
        assert not original["items"]["validation"]
        body = {"name": "Sandbox", "purpose": "Test independent system registration"}
        assert client.post(f"{root}/{project}/ai-systems",
            json=body | {"repository_id": data["repositories"][0]["id"]}).status_code == 422
        system = client.post(f"{root}/{project}/ai-systems", json=body).json()
        edge = {"source": seed["system_id"], "target": system["id"], "kind": "calls"}
        assert client.post(f"{base}/relationships", json=edge).status_code == 404
        edge["target"] = data["links"][0]["source"]
        created = client.post(f"{base}/relationships", json=edge)
        assert created.status_code == 201, created.text
        assert client.post(f"{base}/relationships", json=edge).status_code == 422
        assert client.delete(f"{base}/relationships/{created.json()['id']}").status_code == 200
        saved = client.post(evidence_path, json={"release":"v2.2", "commit":"abcdef1234567",
            "model_version":"v2.2", "items":{"validation":"A test reference"}})
        assert saved.status_code == 201, saved.text
        assert client.put(f"{base}/{seed['system_id']}", json=body).status_code == 200
        assert client.get(evidence_path).json()[0]["system"]["name"] == "Health insurance pricing"
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(base).status_code == 401
        assert restarted.post("/api/auth/demo").status_code == 200
        assert len(restarted.get(evidence_path).json()) == 2
        assert restarted.get(f"{root}/{project}/ai-systems/{seed['system_id']}/evidence").status_code == 404
    with TestClient(create_app(settings=settings.model_copy(update={"demo_mode": False}))) as other:
        assert other.post("/api/auth/register", json={"workspace":"Other", "email":"other-inventory@example.test",
            "password":"long-enough-test-password"}).status_code == 201
        assert other.get(base).status_code == 404
        assert other.get(evidence_path).status_code == 404
