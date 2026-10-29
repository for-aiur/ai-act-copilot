import json
from pathlib import Path

import pytest

from aiact.corpus import load_corpus
from aiact.providers import ReviewFailure
from aiact.questions import QuestionBank, question_options_for

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "engine/src/aiact/data/questions.json"


def test_packaged_questions_are_topic_specific_with_general_fallback():
    bank = QuestionBank.model_validate_json(DATA.read_text())
    sections = {s["id"] for s in load_corpus()["sections"]}
    recruitment = question_options_for("annex-iii-4-a", sections)
    chatbot = question_options_for("article-50-1", sections)
    general = question_options_for("unknown", sections)
    assert recruitment and chatbot and general
    assert not set(recruitment) & set(chatbot + general)
    assert all(q.topic == "recruitment" and q.asks_about for q in bank.questions if q.question in recruitment)
    assert all(q.legal_source is None for q in bank.questions if q.question in general)


@pytest.mark.parametrize("problem", ["missing", "malformed", "duplicate_id", "invented_source", "missing_domain", "blank"])
def test_bad_question_bank_fails_explicitly(tmp_path, monkeypatch, problem):
    import aiact.questions
    monkeypatch.setattr(aiact.questions, "files", lambda _: tmp_path)
    path = tmp_path / "data/questions.json"
    path.parent.mkdir()
    data = json.loads(DATA.read_text())
    if problem == "duplicate_id":
        data["questions"][1]["id"] = data["questions"][0]["id"]
    elif problem == "invented_source":
        data["questions"][0]["legal_source"] = "made-up-law"
    elif problem == "missing_domain":
        data["questions"] = [q for q in data["questions"] if q["legal_source"] != "annex-iii-4-a"]
    elif problem == "blank":
        data["questions"][0]["question"] = "   "
    if problem != "missing":
        path.write_text("{" if problem == "malformed" else json.dumps(data))
    with pytest.raises(ReviewFailure) as caught:
        question_options_for("annex-iii-4-a", {s["id"] for s in load_corpus()["sections"]})
    assert caught.value.code == "question_bank_invalid"


def test_every_passage_has_a_scoped_evidence_question_and_institutional_duties_are_separate():
    from aiact.questions import load_question_bank, review_questions_for
    sections={s['id'] for s in load_corpus()['sections']}
    bank=load_question_bank(sections)
    evidence=[q for q in bank.questions if q.depth=='evidence']
    assert {q.legal_source for q in evidence}==sections
    assert all(q.applies_when.strip() and q.evidence_expected.strip() and len(q.question)<=250 for q in evidence)
    maintenance={'article-6-5','article-6-6','article-6-7','article-6-8','article-11-3','article-15-2','article-50-7'}
    assert {q.legal_source for q in bank.questions if q.audience=='regulatory_maintenance'}==maintenance
    assert not review_questions_for(bank,maintenance)
    chosen=review_questions_for(bank,{'article-10-2','article-14-4'})
    assert chosen and chosen[0].depth=='evidence'
    assert all(q.legal_source in {'article-10-2','article-14-4'} and q.audience=='developer' for q in chosen)


def test_deep_questions_request_concrete_training_oversight_and_sensitive_data_evidence():
    from aiact.questions import load_question_bank
    bank=load_question_bank({s['id'] for s in load_corpus()['sections']})
    by_id={q.id:q for q in bank.questions}
    assert by_id['training_split_leakage'].legal_source=='annex-iv-2-g'
    assert 'overlap' in by_id['training_split_leakage'].evidence_expected
    assert 'experiment' in by_id['parameters_selection_tradeoff'].evidence_expected.lower()
    assert 'exercise' in by_id['oversight_automation_bias'].evidence_expected.lower()
    assert by_id['bias_audit_deletion_copies'].legal_source=='article-4a-1'
    assert 'bias audit' in by_id['bias_audit_deletion_copies'].question
    assert 'not general PII erasure' in by_id['bias_audit_deletion_copies'].applies_when


@pytest.mark.parametrize('problem',['duplicate_text','missing_evidence','missing_condition','oversized_question','unknown_audience'])
def test_invalid_editorial_metadata_is_rejected(tmp_path,monkeypatch,problem):
    import aiact.questions
    data=json.loads(DATA.read_text());evidence=next(q for q in data['questions'] if q.get('depth')=='evidence')
    if problem=='duplicate_text':data['questions'][1]['question']=data['questions'][0]['question']
    elif problem=='missing_evidence':evidence['evidence_expected']=' '
    elif problem=='missing_condition':evidence['applies_when']=' '
    elif problem=='oversized_question':evidence['question']='x'*251
    else:evidence['audience']='everyone'
    path=tmp_path/'data/questions.json';path.parent.mkdir();path.write_text(json.dumps(data))
    monkeypatch.setattr(aiact.questions,'files',lambda _:tmp_path)
    with pytest.raises(ReviewFailure) as caught:
        aiact.questions.load_question_bank({s['id'] for s in load_corpus()['sections']})
    assert caught.value.code=='question_bank_invalid'


def test_question_selection_bounds_prompt_growth_without_losing_context_fallback():
    from aiact.questions import load_question_bank, review_questions_for
    sections={s['id'] for s in load_corpus()['sections']}
    bank=load_question_bank(sections)
    chosen=review_questions_for(bank,{'article-10-2'},include_general=True)
    assert len([q for q in chosen if q.legal_source=='article-10-2'])<=6
    assert len([q for q in chosen if q.legal_source is None])==2
    assert chosen[0].depth=='evidence'
    assert all(q.legal_source in {'article-10-2',None} for q in chosen)


def test_legacy_bank_format_still_loads_without_new_metadata():
    old_record=json.loads(DATA.read_text())['questions'][0]
    old_record={key:old_record[key] for key in ['id','question','topic','asks_about','legal_source']}
    bank=QuestionBank.model_validate({'version':'1.0','questions':[old_record]})
    assert bank.questions[0].audience=='developer'
    assert bank.questions[0].depth=='context'
