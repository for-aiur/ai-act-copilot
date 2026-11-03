"""Central settings for the M1 runtime. Existing adapters retain explicit inputs."""
import os
import shlex
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: Literal["gemini", "ollama"] = "gemini"
    model: str = "gemini-3.1-flash-lite"
    ollama_url: str = "http://127.0.0.1:11434"
    database_url: SecretStr = SecretStr("sqlite:///.aiact-workbench/aiact.db")
    data_dir: Path = Path(".aiact-workbench")
    vector_backend: Literal["qdrant-local"] = "qdrant-local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "file-sha256-pinned-at-build"
    langfuse_enabled: bool = False
    langfuse_host: Literal["https://cloud.langfuse.com"] = "https://cloud.langfuse.com"
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    request_seconds: int = Field(default=60, ge=1, le=60)
    deadline_seconds: int = Field(default=120, ge=1, le=120)
    max_query_bytes: int = Field(default=16000, ge=100, le=24000)
    cloud_consent: bool = False

    @field_validator("database_url")
    @classmethod
    def supported_database(cls, value):
        if not value.get_secret_value().startswith(("sqlite:///", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must select SQLite or PostgreSQL.")
        return value

    @property
    def vector_path(self):
        return self.data_dir / "qdrant"

    @property
    def models_path(self):
        return self.data_dir / "models"

    def require_cloud(self, consent: bool = False):
        if self.provider == "gemini":
            if not (consent or self.cloud_consent):
                raise ValueError("Explicit cloud consent is required before sending scenario/source context to Gemini.")
            if not self.gemini_api_key.get_secret_value():
                raise ValueError("GEMINI_API_KEY is missing. Add it to the local environment.")


ENV_KEYS = {
    "AIACT_PROVIDER": "provider", "AIACT_MODEL": "model", "AIACT_OLLAMA_URL": "ollama_url",
    "DATABASE_URL": "database_url", "AIACT_DATA_DIR": "data_dir", "VECTOR_BACKEND": "vector_backend",
    "EMBEDDING_MODEL": "embedding_model", "EMBEDDING_REVISION": "embedding_revision",
    "LANGFUSE_ENABLED": "langfuse_enabled", "LANGFUSE_HOST": "langfuse_host",
    "LANGFUSE_PUBLIC_KEY": "langfuse_public_key", "LANGFUSE_SECRET_KEY": "langfuse_secret_key",
    "GEMINI_API_KEY": "gemini_api_key", "AIACT_CLOUD_CONSENT": "cloud_consent",
    "AIACT_REQUEST_SECONDS": "request_seconds", "AIACT_DEADLINE_SECONDS": "deadline_seconds",
}


def load_settings(overrides: dict | None = None, env: Mapping[str, str] | None = None, dotenv: Path | None = Path(".env")) -> Settings:
    values = {}
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
    values.update(overrides or {})
    if values.get("provider") == "ollama" and "model" not in values:
        values["model"] = "qwen2.5:3b"
    return Settings.model_validate(values)
