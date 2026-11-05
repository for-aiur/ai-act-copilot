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
    findings: list[DraftFinding] = Field(max_length=4)


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
        assertions = item.title + " " + item.explanation + " " + item.context_question + " " + item.suggested_next_action
        if re.search(r"\bGDPR\b|\b(?:is|are) (?:fully )?compliant\b|\b(?:is|are) (?:a )?high[- ]risk\b|\bnot\b[^.]{0,60}\bhigh[- ]risk\b", assertions, re.I):
            raise ReviewFailure("review_unsupported", "Model made an unsupported legal classification or referenced law outside the reviewed corpus.")
        if re.search(r"\b(?:is|are|was|were)\s+(?:fully\s+)?(?:ethically trained|unbiased|free of (?:bias|personal data)|clean and compliant)\b", assertions, re.I):
            raise ReviewFailure("review_unsupported", "Model asserted an unverified training or data-quality guarantee.")
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
        stable = f"{ev.path}:{ev.start_line}:{ev.end_line}:{','.join(sorted(c.section_id for c in citations))}:{item.kind}:{item.context_question}"
        findings.append(Finding(id=hashlib.sha256(stable.encode()).hexdigest()[:16], title=item.title,
            explanation=item.explanation, kind=item.kind, priority=item.priority, evidence=ev,
            citations=citations, suggested_next_action=item.suggested_next_action,
            context_question=item.context_question))
    return findings


def citation_quote_sources(passages: list[dict], max_quote_chars: int = 300) -> dict[str, list[str]]:
    """Return bounded exact quote choices and the passage IDs containing each."""
    sources: dict[str, set[str]] = {}
    for passage in passages:
        text = passage["text"]
        passage_id = passage["id"]
        candidates = set()
        if 10 <= len(text) <= max_quote_chars:
            candidates.add(text)
        if len(text) >= 10:
            candidates.add(text[:min(100, max_quote_chars)])
        for sentence in re.split(r"(?<=[.!?;:])\s+", text):
            sentence = sentence.strip()
            if 10 <= len(sentence) <= max_quote_chars:
                candidates.add(sentence)
        start = 0
        while start < len(text):
            end = min(start + max_quote_chars, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + max_quote_chars // 2, end)
                if boundary > start:
                    end = boundary
            quote = text[start:end].strip()
            if len(quote) >= 10:
                candidates.add(quote)
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
        for quote in candidates:
            if len(quote) <= max_quote_chars and quote in text:
                sources.setdefault(quote, set()).add(passage_id)
    return {quote: sorted(ids) for quote, ids in sources.items()}


def bind_exact_citations(draft: DraftReview, quote_sources: dict[str, list[str]],
                         passage_ids: set[str]) -> DraftReview:
    """Bind every exact quote to the retrieved passage that actually contains it."""
    findings = []
    for finding in draft.findings:
        citations = []
        for citation in finding.citations:
            source_ids = quote_sources.get(citation.quote, [])
            if citation.section_id not in passage_ids:
                raise ReviewFailure("citation_invalid", "Review selected a section outside the pinned passages.")
            # The quote list is a compact aid for safely mapping ambiguous IDs,
            # not an allowlist. validate_review checks every quote verbatim
            # against the selected passage immediately after this step.
            if source_ids and citation.section_id not in source_ids:
                if len(source_ids) != 1:
                    raise ReviewFailure("citation_invalid", "Review paired a quote with the wrong source passage.")
                citation = citation.model_copy(update={"section_id": source_ids[0]})
            citations.append(citation)
        findings.append(finding.model_copy(update={"citations": citations}))
    return draft.model_copy(update={"findings": findings})
