"""Central settings for the M1 runtime. Existing adapters retain explicit inputs."""
import os
import shlex
import json
import hashlib
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    provider: Literal["gemini", "ollama"] = "gemini"
    model: str = "gemini-3.1-flash-lite"
    model_temperature: float = Field(default=0, ge=0, le=2)
    model_review_output_tokens: int = Field(default=4096, ge=128, le=8192)
    model_extract_output_tokens: int = Field(default=2048, ge=128, le=8192)
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_context_tokens: int = Field(default=8192, ge=1024, le=32768)
    ollama_review_output_tokens: int = Field(default=2400, ge=128, le=8192)
    ollama_extract_output_tokens: int = Field(default=1100, ge=128, le=8192)
    database_url: SecretStr = SecretStr("sqlite:///.aiact-workbench/aiact.db")
    data_dir: Path = Path(".aiact-workbench")
    vector_backend: Literal["qdrant-local"] = "qdrant-local"
    vector_path_override: Path | None = None
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "file-sha256-pinned-at-build"
    langfuse_enabled: bool = False
    langfuse_host: Literal["https://cloud.langfuse.com"] = "https://cloud.langfuse.com"
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_project_id: str = Field(default="", pattern=r"^[a-zA-Z0-9_-]*$", max_length=100)
    review_unit_price: float | None = Field(default=None, ge=0)
    billing_currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    demo_mode: bool = False
    demo_tenant_name: str = "AI Act Demo"
    demo_user_email: str = "demo@example.test"
    gemini_api_key: SecretStr = SecretStr("")
    request_seconds: int = Field(default=60, ge=1, le=60)
    deadline_seconds: int = Field(default=120, ge=1, le=120)
    max_query_bytes: int = Field(default=16000, ge=100, le=24000)
    max_files: int = Field(default=10, ge=1, le=50)
    max_file_bytes: int = Field(default=100_000, ge=1_000, le=1_000_000)
    max_source_bytes: int = Field(default=24_000, ge=1_000, le=100_000)
    max_passages: int = Field(default=6, ge=1, le=20)
    max_legal_bytes: int = Field(default=12_000, ge=1_000, le=100_000)
    retrieval_limit: int = Field(default=10, ge=1, le=20)
    stage_candidates: int = Field(default=30, ge=1, le=100)
    max_intents: int = Field(default=4, ge=1, le=4)
    max_query_terms: int = Field(default=40, ge=1, le=200)
    fusion_k: int = Field(default=60, ge=1, le=200)
    exact_reference_boost: float = Field(default=1.0, ge=0, le=10)
    lexical_overlap_weight: float = Field(default=0.01, ge=0, le=1)
    expansion_seed_limit: int = Field(default=3, ge=0, le=20)
    expansion_per_seed: int = Field(default=4, ge=0, le=20)
    evaluation_k: int = Field(default=10, ge=1, le=20)
    evaluation_preview_k: int = Field(default=5, ge=1, le=20)
    minimum_holdout_recall: float = Field(default=0.95, ge=0, le=1)
    cloud_consent: bool = False

    @field_validator("database_url")
    @classmethod
    def supported_database(cls, value):
        if not value.get_secret_value().startswith(("sqlite:///", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must select SQLite or PostgreSQL.")
        return value

    @property
    def vector_path(self):
        return self.vector_path_override or self.data_dir / "qdrant"

    @property
    def models_path(self):
        return self.data_dir / "models"

    def require_cloud(self, consent: bool = False):
        if self.provider == "gemini":
            if not (consent or self.cloud_consent):
                raise ValueError("Explicit cloud consent is required before sending scenario/source context to Gemini.")
            if not self.gemini_api_key.get_secret_value():
                raise ValueError("GEMINI_API_KEY is missing. Add it to the local environment.")

    @property
    def workbench_config_path(self):
        return self.data_dir / "workbench-settings.json"

    def editable_config(self):
        return {name: getattr(self, name) for name in WORKBENCH_FIELDS}

    def config_fingerprint(self):
        raw = json.dumps(self.editable_config(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


WORKBENCH_FIELDS = (
    "provider", "model", "model_temperature", "model_review_output_tokens", "model_extract_output_tokens",
    "ollama_url", "ollama_context_tokens", "ollama_review_output_tokens", "ollama_extract_output_tokens",
    "embedding_model", "embedding_revision", "langfuse_enabled", "langfuse_project_id",
    "request_seconds", "deadline_seconds", "max_query_bytes", "max_files",
    "max_file_bytes", "max_source_bytes", "max_passages", "max_legal_bytes",
    "retrieval_limit", "stage_candidates", "max_intents", "max_query_terms", "fusion_k",
    "exact_reference_boost", "lexical_overlap_weight", "expansion_seed_limit",
    "expansion_per_seed", "evaluation_k", "evaluation_preview_k",
    "minimum_holdout_recall",
)


ENV_KEYS = {
    "AIACT_PROVIDER": "provider", "AIACT_MODEL": "model", "AIACT_OLLAMA_URL": "ollama_url",
    "DATABASE_URL": "database_url", "AIACT_DATA_DIR": "data_dir", "VECTOR_BACKEND": "vector_backend",
    "VECTOR_PATH": "vector_path_override",
    "EMBEDDING_MODEL": "embedding_model", "EMBEDDING_REVISION": "embedding_revision",
    "LANGFUSE_ENABLED": "langfuse_enabled", "LANGFUSE_HOST": "langfuse_host",
    "LANGFUSE_PUBLIC_KEY": "langfuse_public_key", "LANGFUSE_SECRET_KEY": "langfuse_secret_key",
    "LANGFUSE_PROJECT_ID": "langfuse_project_id", "AIACT_DEMO_MODE": "demo_mode",
    "AIACT_REVIEW_UNIT_PRICE": "review_unit_price", "AIACT_BILLING_CURRENCY": "billing_currency",
    "AIACT_DEMO_TENANT_NAME": "demo_tenant_name", "AIACT_DEMO_USER_EMAIL": "demo_user_email",
    "GEMINI_API_KEY": "gemini_api_key", "AIACT_CLOUD_CONSENT": "cloud_consent",
    "AIACT_REQUEST_SECONDS": "request_seconds", "AIACT_DEADLINE_SECONDS": "deadline_seconds",
}


def load_settings(overrides: dict | None = None, env: Mapping[str, str] | None = None, dotenv: Path | None = Path(".env")) -> Settings:
    values = {"demo_mode": True}
    if dotenv and dotenv.is_file():
        for line in dotenv.read_text().splitlines():
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            if len(tokens) != 1 or "=" not in tokens[0]:
                raise ValueError("Invalid .env assignment; quote values with spaces.")
            key, value = tokens[0].split("=", 1)
            if key in ENV_KEYS:
                values[ENV_KEYS[key]] = value
    values.update({field: (env if env is not None else os.environ)[key] for key, field in ENV_KEYS.items() if key in (env if env is not None else os.environ)})
    config_path = Path(values.get("data_dir", ".aiact-workbench")) / "workbench-settings.json"
    if config_path.is_file():
        saved = json.loads(config_path.read_text())
        if not isinstance(saved, dict) or set(saved) - set(WORKBENCH_FIELDS):
            raise ValueError("Local workbench settings contain unsupported fields.")
        values.update(saved)
    values.update(overrides or {})
    if values.get("provider") == "ollama" and "model" not in values:
        values["model"] = "qwen2.5:3b"
    if values.get("review_unit_price") == "":
        values["review_unit_price"] = None
    return Settings.model_validate(values)
