"""Optional real PostgreSQL parity gate, enabled in CI with an isolated database."""
import os
import pytest
pytest.importorskip("sqlalchemy")
from aiact.rag.contracts import RetrievalRequest
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.rag.store import Store, metadata
from aiact.settings import Settings


@pytest.mark.skipif(not os.environ.get("AIACT_TEST_POSTGRES_URL"), reason="Requires the isolated PostgreSQL CI service")
def test_postgres_matches_sqlite_reference_cases_and_restart(tmp_path):
    postgres = os.environ["AIACT_TEST_POSTGRES_URL"]
    results = []
    for name, url in [("sqlite", "sqlite:///" + str(tmp_path / "db.sqlite")), ("postgres", postgres)]:
        settings = Settings(data_dir=tmp_path / name, database_url=url)
        store = Store(url)
        if name == "postgres":
            metadata.drop_all(store.engine)
            store.close()
            store = Store(url)
        release = build_release(settings, "workbench-api", lexical_only=True)
        retriever = HybridRetriever(settings, release["rag_release_id"], store=store)
        results.append([retriever.search(RetrievalRequest(domain_id="workbench-api", scenario=q, limit=1)).candidates[0].document.id
            for q in ["/api/health readiness", "/api/drafts persistence"]])
        store.activate("workbench-api", release["rag_release_id"])
        retriever.close()
        store.close()
        restarted = Store(url)
        assert restarted.pointer("workbench-api") == release["rag_release_id"]
        restarted.close()
    assert results == [["health", "drafts"], ["health", "drafts"]]


@pytest.mark.skipif(not os.environ.get("AIACT_TEST_POSTGRES_URL"), reason="Requires the isolated PostgreSQL CI service")
def test_checkpointed_rag_review_survives_postgres_reopen(tmp_path):
    from aiact.rag.sessions import resume_review_session, start_review_session
    from test_full_review import FixtureProvider

    settings = Settings(data_dir=tmp_path, database_url=os.environ["AIACT_TEST_POSTGRES_URL"])
    manifest = build_release(settings, "ai-act", lexical_only=True)
    retriever = HybridRetriever(settings, manifest["rag_release_id"])
    source = tmp_path / "chat.py"
    source.write_text("def reply(model, text):\n    return model.generate(text)\n")
    provider = FixtureProvider()

    started = start_review_session(source, provider, retriever, settings=settings)
    assert started.status == "context_needed"
    resumed = resume_review_session(started.id, source, provider, retriever,
        "A notice tells every user before the chat begins.", settings=settings)
    assert resumed.status == "complete"
    assert resumed.rag_release_id == manifest["rag_release_id"]
    retriever.close()
