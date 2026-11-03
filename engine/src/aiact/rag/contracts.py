"""Versioned, domain-independent retrieval and evaluation contracts."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .official import checksum


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DateRule(Record):
    condition: str
    date: str
    source_id: str
    quote: str


class SourceMetadata(Record):
    origin: str
    binding: bool | None = None
    chapter: str | None = None
    celex: str | None = None
    publication_date: str | None = None
    entry_into_force: str | None = None
    consolidated_date: str | None = None
    applicability_status: str = "unknown"
    applicability_date: str | None = None
    applicability_sources: tuple[str, ...] = ()
    applicability_rules: tuple[DateRule, ...] = ()


class Document(Record):
    id: str
    title: str
    text: str
    source_url: str
    kind: str
    checksum: str
    metadata: SourceMetadata

    @model_validator(mode="after")
    def validate_hash(self):
        if checksum(self.text.encode()) != self.checksum:
            raise ValueError("Document checksum mismatch")
        return self


class Chunk(Record):
    id: str
    document_id: str
    title: str
    text: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    checksum: str
    references: tuple[str, ...] = ()


class Snapshot(Record):
    schema_version: Literal["1"] = "1"
    domain_id: str
    snapshot_id: str
    source_version: str
    parser_version: str
    documents: tuple[Document, ...]
    chunks: tuple[Chunk, ...]
    source_hashes: tuple[str, ...]
    scope_limits: tuple[str, ...]
    complete: bool

    @model_validator(mode="after")
    def validate_content(self):
        docs = {d.id: d for d in self.documents}
        if len(docs) != len(self.documents) or len({c.id for c in self.chunks}) != len(self.chunks):
            raise ValueError("Duplicate document or chunk ID")
        for chunk in self.chunks:
            parent = docs.get(chunk.document_id)
            if not parent or parent.text[chunk.start:chunk.end] != chunk.text or checksum(chunk.text.encode()) != chunk.checksum:
                raise ValueError("Chunk source offset or checksum mismatch")
            if not set(chunk.references) <= docs.keys():
                raise ValueError("Unknown cross reference")
        return self


class KnowledgeDomain(Record):
    id: str
    name: str
    description: str
    reference_hint: str


class ScenarioContext(Record):
    actor_role: str = Field(default="", max_length=500)
    deployment: str = Field(default="", max_length=2000)
    constraints: str = Field(default="", max_length=2000)
    language: Literal["en"] = "en"


class RetrievalRequest(Record):
    domain_id: str = "ai-act"
    scenario: str = Field(min_length=1, max_length=12000)
    context: ScenarioContext = ScenarioContext()
    intents: tuple[str, ...] = Field(default=(), max_length=4)
    kinds: tuple[str, ...] = ()
    limit: int = Field(default=10, ge=1, le=20)

    def fingerprint(self):
        return checksum(self.model_dump(mode="json"))


class StageHit(Record):
    chunk_id: str
    rank: int
    score: float
    reason: str


class Candidate(Record):
    chunk: Chunk
    document: Document
    rank: int
    scores: dict[str, float]
    paths: tuple[str, ...]


class RetrievalResult(Record):
    request: RetrievalRequest
    context_fingerprint: str
    snapshot_id: str
    rag_release_id: str
    candidates: tuple[Candidate, ...]
    stages: dict[str, tuple[StageHit, ...]]
    elapsed_ms: int
    warnings: tuple[str, ...] = ()


class GoldLabel(Record):
    document_id: str
    label: Literal["must_retrieve", "relevant", "not_relevant", "uncertain"]
    rationale: str = Field(min_length=1, max_length=2000)


class GoldenCase(Record):
    schema_version: Literal["1"] = "1"
    id: str
    title: str = Field(min_length=1, max_length=160)
    request: RetrievalRequest
    snapshot_id: str
    rag_release_id: str
    labels: tuple[GoldLabel, ...] = ()
    author: str = Field(min_length=1, max_length=120)
    origin: Literal["human", "model_draft"] = "human"
    status: Literal["draft", "approved"] = "draft"
    approved_by: str | None = None
    split: Literal["development", "holdout", "critical"] = "development"
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_labels(self):
        if len({l.document_id for l in self.labels}) != len(self.labels):
            raise ValueError("Conflicting or duplicate source labels")
        if self.status == "approved" and (not self.approved_by or not self.labels):
            raise ValueError("Approval requires explicit reviewer attribution and source labels")
        return self
