import json
from pathlib import Path

import pytest
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
    from aiact.rag.sessions import record_finding_decision
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
    asked = [event for event in started.history if event.type == "question_asked"]
    assert asked and asked[0].finding_id == started.finding_id
    assert asked[0].source_ids
    with pytest.raises(ValueError, match="requires a reason"):
        record_finding_decision(started.id, started.finding_id, "false_positive", settings=settings)
    acknowledged = record_finding_decision(started.id, started.finding_id, "acknowledged",
        actor="Domain reviewer", settings=settings)
    assert acknowledged.status == "context_needed"
    assert acknowledged.decisions[started.finding_id] == "acknowledged"
    assert acknowledged.history[-1].actor == "Domain reviewer"
    dismissed = record_finding_decision(started.id, started.finding_id, "false_positive",
        actor="Domain reviewer", reason="This local example is a mock, not a deployed workflow.", settings=settings)
    assert dismissed.decisions[started.finding_id] == "false_positive"
    assert dismissed.history[-1].reason

    class OtherRelease:
        manifest = {"rag_release_id": "a-different-release"}
    stale_rag = resume_rag_session(started.id, source, provider, OtherRelease(), "Context", settings=settings)
    assert stale_rag.scan_result.errors[0].code == "stale_rag"
    source.write_text(source.read_text() + "\n# changed after pause\n")
    stale_source = resume_rag_session(started.id, source, provider, retriever, "Context", settings=settings)
    assert stale_source.scan_result.errors[0].code == "stale_source"
    source.write_text("def reply(model, text):\n    return model.generate(text)\n")

    resumed = resume_rag_session(started.id, source, provider, retriever,
        "A notice tells every user before the chat begins.", settings=settings, actor="Domain reviewer")
    assert resumed.status == "complete"
    assert resumed.answer_count == 1
    assert resumed.rag_release_id == manifest["rag_release_id"]
    answer_events = [event for event in resumed.history if event.type == "context_answered"]
    assert len(answer_events) == 1
    assert answer_events[0].answer == "A notice tells every user before the chat begins."
    assert answer_events[0].actor == "Domain reviewer"
    assert answer_events[0].source_ids
    assert resumed.decisions[started.finding_id] == "false_positive"
    calls = provider.calls
    retry = resume_rag_session(started.id, source, provider, retriever,
        "A notice tells every user before the chat begins.", settings=settings)
    assert retry.status == "complete"
    assert provider.calls == calls
    retriever.close()


def test_changed_context_revises_and_reopens_a_previously_dismissed_finding(tmp_path):
    from aiact.rag.releases import build_release
    from aiact.rag.retriever import HybridRetriever
    from aiact.rag.sessions import record_finding_decision
    from aiact.rag.sessions import resume_review_session as resume_rag_session
    from aiact.rag.sessions import start_review_session as start_rag_session
    from aiact.settings import Settings
    from test_full_review import FixtureProvider

    class ChangedContextProvider(FixtureProvider):
        def generate_json(self, prompt, schema, timeout):
            if self.calls < 2:
                return super().generate_json(prompt, schema, timeout)
            self.calls += 1
            data = json.loads(prompt.split("UNTRUSTED_DATA:\n", 1)[1])
            passage = next(p for p in data["official_passages"] if p["id"].startswith("article-50-"))
            return {"findings": [{"title": "Clarify notice timing", "explanation": "New context changes when users see the notice.",
                "kind": "context_question", "priority": "medium", "evidence_id": "E1",
                "citations": [{"section_id": passage["id"], "quote": passage["text"][:100]}],
                "suggested_next_action": "Confirm when the notice appears.",
                "context_question": "Does the notice appear before the first generated reply?"}]}

    settings = Settings(data_dir=tmp_path, database_url=SecretStr(f"sqlite:///{tmp_path / 'revision.sqlite'}"))
    manifest = build_release(settings, lexical_only=True)
    retriever = HybridRetriever(settings, manifest["rag_release_id"])
    source = tmp_path / "chat.py"
    source.write_text("def reply(model, text):\n    return model.generate(text)\n")
    provider = ChangedContextProvider()
    started = start_rag_session(source, provider, retriever, settings=settings)
    old_id = started.finding_id
    record_finding_decision(started.id, old_id, "false_positive", reason="Initial context said no disclosure was needed.", settings=settings)

    revised = resume_rag_session(started.id, source, provider, retriever,
        "Correction: notice is shown only after the first generated reply.", settings=settings)
    assert revised.status == "context_needed"
    assert revised.finding_id != old_id
    assert any(event.type == "finding_revision" and event.previous_finding for event in revised.history)
    assert revised.decisions[revised.finding_id] == "reopened"
    assert any(event.type == "reopened" for event in revised.history)
    retriever.close()
