"""Reviewed question data, separate from prompts and executable rules."""
from importlib.resources import files
from typing import Literal

from pydantic import Field

from .contracts import Contract
from .providers import ReviewFailure


class Question(Contract):
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=10, max_length=250)
    topic: str = Field(min_length=1, max_length=100)
    asks_about: str = Field(min_length=1, max_length=150)
    legal_source: str | None
    audience: Literal["developer", "regulatory_maintenance"] = "developer"
    depth: Literal["context", "evidence"] = "context"
    applies_when: str = Field(default="", max_length=500)
    evidence_expected: str = Field(default="", max_length=400)


class QuestionBank(Contract):
    version: Literal["1.0", "1.1"]
    questions: list[Question] = Field(min_length=1, max_length=1000)


def load_question_bank(known_sections: set[str]) -> QuestionBank:
    """Validate editorial data. Tags describe questions, not proof of missing facts."""
    try:
        bank = QuestionBank.model_validate_json(files("aiact").joinpath("data/questions.json").read_text())
        ids = [q.id for q in bank.questions]
        texts = [q.question.casefold().strip() for q in bank.questions]
        if len(ids) != len(set(ids)) or len(texts) != len(set(texts)) or any(
            not all(value.strip() for value in (q.id, q.question, q.topic, q.asks_about))
            or (q.legal_source is not None and q.legal_source not in known_sections)
            or (q.depth == "evidence" and (not q.applies_when.strip() or not q.evidence_expected.strip()))
            or not q.question.endswith("?")
            for q in bank.questions
        ):
            raise ValueError("Invalid question identity or source")
        return bank
    except (OSError, ValueError):
        raise ReviewFailure("question_bank_invalid", "Question bank is missing or invalid. Check data/questions.json or reinstall the engine.") from None


def question_options_for(section_id: str, known_sections: set[str]) -> list[str]:
    selected = None if section_id == "unknown" else section_id
    options = [q.question for q in load_question_bank(known_sections).questions if q.legal_source == selected and q.audience == "developer"]
    if not options:
        raise ReviewFailure("question_bank_invalid", "Question bank has no options for the selected legal topic.")
    return options


def review_questions_for(bank: QuestionBank, section_ids: set[str], include_general: bool = False) -> list[Question]:
    """Prefer concrete evidence questions without inflating the scan finding budget.

    Maintenance-only paragraphs never become developer implementation questions.
    Applicability text guides the model; it is not an automated legal assessment.
    """
    selected = [q for q in bank.questions if q.audience == "developer" and
                (q.legal_source in section_ids or (include_general and q.legal_source is None))]
    # Bound prompt growth as the editorial bank expands: four detailed options
    # plus two context alternatives per passage, and two general fallbacks.
    groups: dict[str | None, list[Question]] = {}
    for question in selected:
        groups.setdefault(question.legal_source, []).append(question)
    bounded = []
    for source, questions in groups.items():
        detailed = [q for q in questions if q.depth == "evidence"]
        contextual = [q for q in questions if q.depth == "context"]
        bounded.extend(detailed[:4] + contextual[:2] if source else contextual[:2])
    return sorted(bounded, key=lambda q: q.depth != "evidence")
