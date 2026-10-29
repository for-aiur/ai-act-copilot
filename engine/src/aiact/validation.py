"""Resolve source and URL provenance independently of model output."""
import hashlib
import re
from typing import Literal
from pydantic import Field
from .contracts import Contract, Citation, Evidence, Finding
from .providers import ReviewFailure


class DraftCitation(Contract):
    section_id: str
    quote: str = Field(min_length=10, max_length=300)


class DraftFinding(Contract):
    title: str = Field(min_length=1, max_length=160)
    explanation: str = Field(min_length=1, max_length=300)
    kind: Literal["potential_issue", "context_question"]
    priority: Literal["high", "medium", "low"]
    evidence_id: str
    citations: list[DraftCitation] = Field(min_length=1, max_length=3)
    suggested_next_action: str = Field(min_length=1, max_length=180)
    context_question: str = Field(min_length=10, max_length=250)


class DraftReview(Contract):
    findings: list[DraftFinding] = Field(max_length=3)


def validate_evidence(evidence: Evidence, sources: dict[str, str]):
    if evidence.path not in sources:
        raise ReviewFailure("evidence_invalid", "Model referenced a source outside the scanned files.")
    lines = sources[evidence.path].splitlines()
    if evidence.end_line > len(lines) or evidence.quote != "\n".join(lines[evidence.start_line - 1:evidence.end_line]):
        raise ReviewFailure("evidence_invalid", "Code quote or source range does not match reviewed input.")


def validate_review(draft: DraftReview, evidence: dict[str, Evidence], sources: dict[str, str], passages: list[dict]) -> list[Finding]:
    allowed = {p["id"]: p for p in passages}
    findings = []
    for item in draft.findings:
        # Conservative rejection of especially misleading classifications, not a
        # claim to solve semantic legal validation. Fixture review is still required.
        assertions = item.explanation + " " + item.context_question + " " + item.suggested_next_action
        if re.search(r"\bGDPR\b|\b(?:is|are) (?:fully )?compliant\b|\b(?:is|are) (?:a )?high[- ]risk\b|\bnot\b[^.]{0,60}\bhigh[- ]risk\b", assertions, re.I):
            raise ReviewFailure("review_unsupported", "Model made an unsupported legal classification or referenced law outside the reviewed corpus.")
        if item.evidence_id not in evidence:
            raise ReviewFailure("evidence_invalid", "Model referenced an unknown code evidence ID.")
        ev = evidence[item.evidence_id]
        validate_evidence(ev, sources)
        citations = []
        for citation in item.citations:
            section = allowed.get(citation.section_id)
            if section is None or citation.quote not in section["text"] or not citation.quote.strip():
                raise ReviewFailure("citation_invalid", "Legal section or exact supporting quote was not in the retrieved passages.")
            citations.append(Citation(section_id=section["id"], quote=citation.quote, url=section["url"]))
        stable = f"{ev.path}:{ev.start_line}:{ev.end_line}:{','.join(sorted(c.section_id for c in citations))}:{item.kind}"
        findings.append(Finding(id=hashlib.sha256(stable.encode()).hexdigest()[:16], title=item.title,
            explanation=item.explanation, kind=item.kind, priority=item.priority, evidence=ev,
            citations=citations, suggested_next_action=item.suggested_next_action,
            context_question=item.context_question if not findings else None))
    return findings
