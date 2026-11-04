import json
from pathlib import Path

from pydantic import SecretStr

from aiact.contracts import ReviewSession
from aiact.pipeline import get_review_session, resume_review_session, start_review_session
from aiact.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


class SessionProvider:
    name = "ollama"
    model = "session-test"

    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt, schema, timeout):
        self.calls += 1
        assert 0 < timeout <= 60
        if self.calls == 1:
            json.loads(prompt.split("UNTRUSTED_DATA_JSON:\n", 1)[1])
            return {"ai_use": "evidenced", "purpose": "Recruitment AI ranking", "facts": [],
                    "unknowns": ["Deployment context unknown"]}
        if "User-provided review context:" in prompt:
            return {"findings": []}
        data = json.loads(prompt.split("UNTRUSTED_DATA_JSON:\n", 1)[1])
        passage = data["official_passages"][0]
        question = next(item["question"] for item in data["review_questions"]
                        if item["legal_source"] == passage["section_id"])
        return {"findings": [{
            "title": "Confirm how ranking affects hiring",
            "explanation": "The code ranks applicants; confirm whether recruiters use these scores in selection.",
            "kind": "context_question", "priority": "medium", "evidence_id": "E1",
            "citations": [{"section_id": passage["section_id"], "quote": passage["quote_options"][0]}],
            "suggested_next_action": "Describe how recruiters use the ranking.",
            "context_question": question,
        }]}


def _settings(tmp_path):
    return Settings(database_url=SecretStr(f"sqlite:///{tmp_path / 'reviews.sqlite'}"))


def test_review_session_persists_interrupt_resumes_and_is_idempotent(tmp_path):
    settings = _settings(tmp_path)
    source = ROOT / "examples/recruitment/ranker.py"
    provider = SessionProvider()

    started = start_review_session(source, provider, settings=settings)
    assert started.status == "context_needed", started.scan_result.errors
    assert started.scan_result.status == "partial"
    assert started.context_question
    assert get_review_session(started.id, settings).status == "context_needed"

    resumed = resume_review_session(started.id, source, provider,
        "Recruiters review every score before making a decision.", settings=settings)
    assert resumed.status == "complete"
    assert resumed.answer_count == 1
    assert resumed.scan_result.status == "complete"
    assert resumed.scan_result.findings == []

    calls = provider.calls
    retry = resume_review_session(started.id, source, provider,
        "Recruiters review every score before making a decision.", settings=settings)
    assert retry.status == "complete"
    assert provider.calls == calls


def test_review_session_rejects_changed_source_without_model_call(tmp_path):
    settings = _settings(tmp_path)
    source = tmp_path / "ranking.py"
    source.write_text((ROOT / "examples/recruitment/ranker.py").read_text())
    provider = SessionProvider()
    started = start_review_session(source, provider, settings=settings)
    assert started.status == "context_needed", started.scan_result.errors

    source.write_text(source.read_text() + "\n# changed after pause\n")
    calls = provider.calls
    resumed = resume_review_session(started.id, source, provider, "Context", settings=settings)
    assert resumed.status == "failed"
    assert resumed.scan_result.errors[0].code == "stale_source"
    assert provider.calls == calls


def test_review_session_contract_is_additive():
    session = ReviewSession(id="review-1", status="pending")
    assert session.status == "pending"
    assert session.scan_result is None


def test_full_corpus_session_pins_active_release_across_pause_and_resume(tmp_path):
    from aiact.rag.releases import build_release
    from aiact.rag.retriever import HybridRetriever
    from aiact.rag.sessions import get_review_session as get_rag_session
    from aiact.rag.sessions import resume_review_session as resume_rag_session
    from aiact.rag.sessions import start_review_session as start_rag_session
    from aiact.settings import Settings
    from test_full_review import FixtureProvider

    settings = Settings(data_dir=tmp_path, database_url=SecretStr(f"sqlite:///{tmp_path / 'rag-sessions.sqlite'}"))
    manifest = build_release(settings, lexical_only=True)
    retriever = HybridRetriever(settings, manifest["rag_release_id"])
    source = tmp_path / "chat.py"
    source.write_text("def reply(model, text):\n    return model.generate(text)\n")
    provider = FixtureProvider()

    started = start_rag_session(source, provider, retriever, settings=settings)
    assert started.status == "context_needed"
    assert started.rag_release_id == manifest["rag_release_id"]
    assert get_rag_session(started.id, settings).rag_release_id == manifest["rag_release_id"]

    class OtherRelease:
        manifest = {"rag_release_id": "a-different-release"}
    stale_rag = resume_rag_session(started.id, source, provider, OtherRelease(), "Context", settings=settings)
    assert stale_rag.scan_result.errors[0].code == "stale_rag"
    source.write_text(source.read_text() + "\n# changed after pause\n")
    stale_source = resume_rag_session(started.id, source, provider, retriever, "Context", settings=settings)
    assert stale_source.scan_result.errors[0].code == "stale_source"
    source.write_text("def reply(model, text):\n    return model.generate(text)\n")

    resumed = resume_rag_session(started.id, source, provider, retriever,
        "A notice tells every user before the chat begins.", settings=settings)
    assert resumed.status == "complete"
    assert resumed.answer_count == 1
    assert resumed.rag_release_id == manifest["rag_release_id"]
    calls = provider.calls
    retry = resume_rag_session(started.id, source, provider, retriever,
        "A notice tells every user before the chat begins.", settings=settings)
    assert retry.status == "complete"
    assert provider.calls == calls
    retriever.close()
