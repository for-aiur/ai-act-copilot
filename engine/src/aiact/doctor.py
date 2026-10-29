"""Read-only setup checks shared by terminal users and the editor adapter."""
import platform
from pathlib import Path
from typing import Literal

from pydantic import Field

from . import __version__
from .contracts import Contract, ScanError
from .corpus import load_corpus
from .providers import Ollama, ReviewFailure
from .gemini import Gemini, ENDPOINT


class HealthCheck(Contract):
    id: Literal["engine", "ollama", "gemini", "model", "corpus"]
    status: Literal["ready", "unavailable", "unknown"]
    detail: str


class HealthResult(Contract):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["ready", "unavailable"] = "unavailable"
    engine_version: str = __version__
    python_version: str = Field(default_factory=platform.python_version)
    provider: Literal["ollama", "gemini"] = "ollama"
    endpoint: str | None = None
    model_id: str | None = None
    checks: list[HealthCheck] = Field(default_factory=list)
    errors: list[ScanError] = Field(default_factory=list)


def inspect_setup(model: str, endpoint: str, corpus_path: Path | None = None, provider_name: str = "ollama") -> HealthResult:
    result = HealthResult(model_id=model, provider=provider_name)
    result.checks.append(HealthCheck(id="engine", status="ready", detail=f"AI Act Copilot {__version__}; Python {platform.python_version()}"))
    try:
        corpus = load_corpus(corpus_path)
        result.checks.append(HealthCheck(id="corpus", status="ready", detail=f"{corpus['version']} · {len(corpus['sections'])} reviewed passages · SHA-256 {corpus['checksum']}"))
    except ReviewFailure as exc:
        result.checks.append(HealthCheck(id="corpus", status="unavailable", detail=str(exc)))
        result.errors.append(ScanError(code=exc.code, message=str(exc)))
    if provider_name == "gemini":
        result.endpoint = ENDPOINT
        try:
            Gemini(model).check_model()
            result.checks.extend([
                HealthCheck(id="gemini", status="ready", detail="Google API key and model access verified; reviews send code/context to Google."),
                HealthCheck(id="model", status="ready", detail=model),
            ])
        except ReviewFailure as exc:
            result.checks.extend([
                HealthCheck(id="gemini", status="unavailable", detail=str(exc)),
                HealthCheck(id="model", status="unknown", detail="Fix Gemini credentials/access to verify the model."),
            ])
            result.errors.append(ScanError(code=exc.code, message=str(exc)))
        result.status = "ready" if not result.errors else "unavailable"
        return result
    try:
        provider = Ollama(model, endpoint)
        result.endpoint = provider.endpoint
        installed = provider.available_models()
        result.checks.append(HealthCheck(id="ollama", status="ready", detail=f"Reachable at {provider.endpoint}"))
    except ReviewFailure as exc:
        result.checks.extend([
            HealthCheck(id="ollama", status="unavailable", detail=str(exc)),
            HealthCheck(id="model", status="unknown", detail="Start the local service to check the selected model."),
        ])
        result.errors.append(ScanError(code=exc.code, message=str(exc)))
    else:
        try:
            if model not in installed:
                raise ReviewFailure("model_unavailable", f"Local model {model} is not installed. Download it explicitly during setup; the health check never downloads models.")
            provider.ensure_local_model()
            result.checks.append(HealthCheck(id="model", status="ready", detail=f"{model} is installed locally"))
        except ReviewFailure as exc:
            result.checks.append(HealthCheck(id="model", status="unavailable", detail=str(exc)))
            result.errors.append(ScanError(code=exc.code, message=str(exc)))
    result.status = "ready" if not result.errors else "unavailable"
    return result
