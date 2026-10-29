from pathlib import Path
import json
import pytest
from aiact.contracts import Evidence
from aiact.corpus import load_corpus
from aiact.pipeline import scan
from aiact.providers import ReviewFailure
from aiact.retrieval import retrieve
from aiact.validation import validate_evidence

ROOT = Path(__file__).resolve().parents[2]


def review_payload():
    return {"findings": [{"title": "Recruitment: confirm how scores affect selection", "explanation": "The recruitment or selection context may be relevant to Annex III 4(a). Confirm how the model outputs influence real candidate selection; actual deployment and actor role are not established by this snippet.",
        "kind": "context_question", "priority": "high", "evidence_id": "E1",
        "citations": [{"section_id": "annex-iii-4-a", "quote": "AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;"}],
        "suggested_next_action": "Document how recruiters use scores and whether they materially influence selection.",
        "context_question": "Will these scores affect real hiring decisions in the EU, and who reviews the shortlist?"}]}


class Stub:
    """Test-only provider. Product has no stub/recorded mode."""
    model = "test-only"

    def __init__(self, output=None):
        self.calls = 0
        self.output = output

    def generate_json(self, prompt, schema, timeout):
        assert 0 < timeout <= 60
        self.calls += 1
        if self.calls == 1:
            data = json.loads(prompt.split("UNTRUSTED_DATA_JSON:\n", 1)[1])
            if not any(s["potential_model_calls"] for s in data["source"]):
                return {"ai_use": "none", "purpose": "Ordinary Python operations", "facts": [], "unknowns": []}
            return {"ai_use": "evidenced", "purpose": "Recruitment AI shortlisting", "facts": [{"evidence_id": "E1", "fact": "Uses suitability_model.predict to rank applicants"}], "unknowns": ["Deployment role unknown"]}
        return self.output if self.output is not None else review_payload()


def test_retrieval_and_valid_scan():
    assert retrieve("AI recruitment resume candidate model", load_corpus())[0]["id"] == "annex-iii-4-a"
    result = scan(ROOT / "examples/recruitment/ranker.py", Stub())
    assert result.status == "complete" and len(result.findings) == 1
    assert result.findings[0].context_question.endswith("?")
    assert result.findings[0].citations[0].url.startswith("https://ai-act-service-desk.ec.europa.eu/")


def test_biometric_image_does_not_imply_generated_content():
    passages = retrieve("identify_person camera image face model encode enrolled_gallery", load_corpus())
    assert passages[0]["id"] == "annex-iii-1-a"
    assert "article-50-2" not in {p["id"] for p in passages}


@pytest.mark.parametrize("field,value", [("section_id", "invented"), ("quote", "This quotation does not exist in official law")])
def test_invented_citations_rejected(field, value):
    output = review_payload()
    output["findings"][0]["citations"][0][field] = value
    result = scan(ROOT / "examples/recruitment/ranker.py", Stub(output))
    assert result.status == "failed" and result.errors[0].code == "citation_invalid"
    assert not result.findings


def test_wrong_range_or_source_rejected():
    with pytest.raises(ReviewFailure, match="range"):
        validate_evidence(Evidence(path="x.py", start_line=2, end_line=5, quote="x=1"), {"x.py": "x=1"})
    with pytest.raises(ReviewFailure, match="quote"):
        validate_evidence(Evidence(path="x.py", start_line=1, end_line=1, quote="invented"), {"x.py": "x=1"})


def test_negative_malformed_and_timeout():
    assert scan(ROOT / "examples/negative_control/totals.py", Stub({"findings": []})).status == "complete"
    class Broken(Stub):
        def generate_json(self, *args):
            self.calls += 1
            return {"bad": "shape"}
    broken = Broken()
    result = scan(ROOT / "examples/recruitment/ranker.py", broken)
    assert result.status == "failed" and broken.calls == 2
    class Timeout(Stub):
        def generate_json(self, *args):
            raise ReviewFailure("timeout", "timeout")
    assert scan(ROOT / "examples/recruitment/ranker.py", Timeout()).errors[0].code == "timeout"


def test_scan_never_fetches_official_or_executes_source(tmp_path, monkeypatch):
    import aiact.corpus
    monkeypatch.setattr(aiact.corpus, "fetch_official", lambda *args: pytest.fail("network on scan"))
    source = tmp_path / "source.py"
    marker = tmp_path / "executed"
    source.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    result = scan(source, Stub({"findings": []}))
    assert result.status == "complete" and not marker.exists()


def test_non_ai_extraction_still_gets_review_and_rejects_generic_concerns():
    class NonAI(Stub):
        def generate_json(self, prompt, schema, timeout):
            self.calls += 1
            if self.calls == 1:
                return {"ai_use": "none", "purpose": "Ordinary invoice arithmetic", "facts": [], "unknowns": []}
            assert schema["properties"]["findings"]["maxItems"] == 0
            return {"findings": []}
    provider = NonAI()
    result = scan(ROOT / "examples/negative_control/totals.py", provider)
    assert result.status == "complete" and not result.findings and provider.calls == 2
    class BadNonAI(NonAI):
        def generate_json(self, prompt, schema, timeout):
            output = super().generate_json(prompt, schema, timeout)
            return review_payload() if self.calls == 2 else output
    result = scan(ROOT / "examples/negative_control/totals.py", BadNonAI())
    assert result.status == "failed" and result.errors[0].code == "review_unsupported"


def test_unsupported_legal_classification_fails_explicitly():
    output = review_payload()
    output["findings"][0]["explanation"] = "This system is compliant and is not high-risk."
    result = scan(ROOT / "examples/recruitment/ranker.py", Stub(output))
    assert result.status == "failed" and result.errors[0].code == "review_unsupported"


def test_question_data_controls_model_options_and_independent_validation(tmp_path, monkeypatch):
    import aiact.questions
    bank = json.loads((ROOT / "engine/src/aiact/data/questions.json").read_text())
    original = bank["questions"][0]["question"]
    replacement = "Who reviews the candidate shortlist before a hiring decision?"
    bank["questions"][0]["question"] = replacement
    path = tmp_path / "data/questions.json"
    path.parent.mkdir()
    path.write_text(json.dumps(bank))
    monkeypatch.setattr(aiact.questions, "files", lambda _: tmp_path)

    class CheckOptions(Stub):
        def generate_json(self, prompt, schema, timeout):
            if self.calls:
                choices = schema["$defs"]["DraftFinding"]["properties"]["context_question"]["enum"]
                assert replacement in choices and original not in choices
                data = json.loads(prompt.split("UNTRUSTED_DATA_JSON:\n", 1)[1])
                assert [q["question"] for q in data["review_questions"]] == choices
            return super().generate_json(prompt, schema, timeout)

    output = review_payload()
    output["findings"][0]["context_question"] = replacement
    result = scan(ROOT / "examples/recruitment/ranker.py", CheckOptions(output))
    assert result.status == "complete" and result.findings[0].context_question == replacement
    result = scan(ROOT / "examples/recruitment/ranker.py", CheckOptions(review_payload()))
    assert result.status == "failed" and result.errors[0].code == "invalid_response"


def test_missing_question_bank_is_an_operational_error(tmp_path, monkeypatch):
    import aiact.questions
    monkeypatch.setattr(aiact.questions, "files", lambda _: tmp_path)
    result = scan(ROOT / "examples/recruitment/ranker.py", Stub())
    assert result.status == "failed" and not result.findings
    assert result.errors[0].code == "question_bank_invalid"


def test_gemini_shares_pipeline_without_ollama(monkeypatch):
    from aiact.gemini import Gemini
    from aiact.providers import Ollama
    provider = Gemini(api_key="test-only-key")
    monkeypatch.setattr(provider, "generate_json", Stub().generate_json)
    monkeypatch.setattr(Ollama, "ensure_local_model", lambda _: pytest.fail("Gemini must not require Ollama"))
    result = scan(ROOT / "examples/recruitment/ranker.py", provider)
    assert result.status == "complete" and result.metadata.provider == "gemini"
    assert result.findings[0].citations[0].section_id == "annex-iii-4-a"


def test_pipeline_exposes_evidence_requirements_in_bounded_question_options():
    class EvidenceOptions(Stub):
        def generate_json(self,prompt,schema,timeout):
            if self.calls:
                data=json.loads(prompt.split('UNTRUSTED_DATA_JSON:\n',1)[1])
                options=data['review_questions']
                assert options[0]['depth']=='evidence' and options[0]['evidence_expected']
                assert all(q['audience']=='developer' for q in options)
                assert len(options)<=6*6+2
                assert 'concrete evidence_expected artifacts' in prompt
            return super().generate_json(prompt,schema,timeout)
    assert scan(ROOT/'examples/recruitment/ranker.py',EvidenceOptions()).status=='complete'
