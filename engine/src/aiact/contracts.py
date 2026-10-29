"""Versioned public payload; export schema with python -m aiact.contracts."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Contract):
    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_line < self.start_line or Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ValueError("Evidence must have an inclusive range and repository-relative path")
        return self


class Citation(Contract):
    section_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    url: str = Field(min_length=1)


class Finding(Contract):
    id: str
    title: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    kind: Literal["potential_issue", "context_question"]
    priority: Literal["high", "medium", "low"]
    evidence: Evidence
    citations: list[Citation] = Field(min_length=1)
    suggested_next_action: str = Field(min_length=1)
    context_question: str | None = None


class ScanError(Contract):
    code: str
    message: str
    path: str | None = None


class SkippedFile(Contract):
    path: str
    reason: str


class Coverage(Contract):
    scanned_files: list[str] = Field(default_factory=list)
    skipped_files: list[SkippedFile] = Field(default_factory=list)
    truncated: bool = False
    supported_languages: list[str] = Field(default_factory=lambda: ["python"])
    corpus_scope: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: ["Engineering review only; zero findings does not certify compliance."])


class Metadata(Contract):
    provider: Literal["ollama", "gemini"] | None = None
    model_id: str | None = None
    prompt_version: str = "poc-7"
    corpus_version: str | None = None
    corpus_checksum: str | None = None
    input_fingerprint: str | None = None
    elapsed_ms: int = Field(default=0, ge=0)


class ScanResult(Contract):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["complete", "partial", "failed"]
    findings: list[Finding] = Field(default_factory=list, max_length=4)
    errors: list[ScanError] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)
    metadata: Metadata = Field(default_factory=Metadata)

    @model_validator(mode="after")
    def coherent(self):
        if self.status == "complete" and (self.errors or self.coverage.truncated or self.coverage.skipped_files):
            raise ValueError("Complete results cannot hide errors or incomplete coverage")
        if self.status == "failed" and not self.errors:
            raise ValueError("Failed result requires an operational error")
        return self


if __name__ == "__main__":
    print(json.dumps(ScanResult.model_json_schema(), indent=2))
