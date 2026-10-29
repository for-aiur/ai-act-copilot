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
