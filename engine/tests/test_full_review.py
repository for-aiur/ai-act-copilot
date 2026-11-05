import pytest
pytest.importorskip("sqlalchemy")
from aiact.rag.contracts import RetrievalRequest
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.rag.review import review_python
from aiact.settings import Settings


class FixtureProvider:
    name = "gemini"
    model = "test-only-provider"

    def __init__(self, invented=False):
        self.calls = 0
        self.invented = invented

    def generate_json(self, prompt, schema, timeout):
        self.calls += 1
        assert 0 < timeout <= 60
        if self.calls == 1:
            return {"ai_use": "unknown", "purpose": "Article 50 chatbot interacting with customers", "facts": [{"evidence_id": "E1", "fact": "A model produces a reply"}], "unknowns": ["Disclosure unknown"], "retrieval_intents": ["Article 50 transparency", "chatbot interaction"]}
        import json
        data = json.loads(prompt.split("UNTRUSTED_DATA:\n")[1].split("\nCitation validation")[0])
        passage = next(p for p in data["official_passages"] if p["id"].startswith("article-50-"))
        return {"findings": [{"title": "Clarify interaction disclosure", "explanation": "The reply flow needs deployment context about how people are informed.", "kind": "context_question", "priority": "medium",
            "evidence_id": "E1", "citations": [{"section_id": "invented" if self.invented else passage["id"], "quote": passage["text"][:100]}],
            "suggested_next_action": "Document the user-facing notice.", "context_question": "How are users told they are interacting with an AI system?"}]}


def test_full_corpus_review_uses_arbitrary_retrieved_provisions_and_rejects_fake_citation(tmp_path):
    settings = Settings(data_dir=tmp_path, database_url="sqlite:///" + str(tmp_path / "db.sqlite"))
    manifest = build_release(settings, lexical_only=True)
    retriever = HybridRetriever(settings, manifest["rag_release_id"])
    source = tmp_path / "chat.py"
    source.write_text("def reply(model, text):\n    return model.generate(text)\n")
    result = review_python(source, FixtureProvider(), retriever, uploaded=True)
    assert result["scan_result"]["status"] == "complete"
    citation = result["scan_result"]["findings"][0]["citations"][0]
    assert citation["url"].startswith("https://eur-lex.europa.eu/")
    assert citation["section_id"].startswith("article-50-")
    failed = review_python(source, FixtureProvider(invented=True), retriever, uploaded=True)
    assert failed["scan_result"]["status"] == "failed"
    assert failed["scan_result"]["errors"][0]["code"] == "citation_invalid"
    retriever.close()
