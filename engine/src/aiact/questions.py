"""Reviewed question data, separate from prompts and executable rules."""
from importlib.resources import files
from typing import Literal

from pydantic import Field

from .contracts import Contract
from .providers import ReviewFailure


class Question(Contract):
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=500)
    topic: str = Field(min_length=1, max_length=100)
    asks_about: str = Field(min_length=1, max_length=150)
    legal_source: str | None


class QuestionBank(Contract):
    version: Literal["1.0"]
    questions: list[Question] = Field(min_length=1, max_length=1000)


def question_options_for(section_id: str, known_sections: set[str]) -> list[str]:
    """Load matching options; unknown use cases get the explicit general group.

    Topic and asks_about describe editorial intent. They do not implement
    missing-fact detection or automatic suppression of answered questions.
    """
    try:
        bank = QuestionBank.model_validate_json(files("aiact").joinpath("data/questions.json").read_text())
        ids = [q.id for q in bank.questions]
        if len(ids) != len(set(ids)) or any(
            not all(value.strip() for value in (q.id, q.question, q.topic, q.asks_about))
            or (q.legal_source is not None and q.legal_source not in known_sections)
            for q in bank.questions
        ):
            raise ValueError("Invalid question identity or source")
        selected_source = None if section_id == "unknown" else section_id
        options = [q.question for q in bank.questions if q.legal_source == selected_source]
        if not options:
            raise ValueError("No question options for selected domain")
        return options
    except (OSError, ValueError):
        raise ReviewFailure(
            "question_bank_invalid",
            "Question bank is missing or invalid. Check data/questions.json or reinstall the engine.",
        ) from None
