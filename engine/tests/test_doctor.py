import json
from pathlib import Path

import jsonschema
import pytest

from aiact import doctor
from aiact.cli import main
from aiact.doctor import HealthResult, inspect_setup
from aiact.providers import ReviewFailure


class LocalProvider:
    def __init__(self, model, endpoint):
        self.model = model
        self.endpoint = endpoint

    def available_models(self):
        return [self.model]

    def ensure_local_model(self):
        pass

    def generate_json(self, *args):
        pytest.fail("Health checks must not run inference")


def test_ready_health_json_and_schema(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "Ollama", LocalProvider)
    assert main(["doctor", "--json"]) == 0
    output = capsys.readouterr()
    result = HealthResult.model_validate_json(output.out)
    assert result.status == "ready" and len(result.checks) == 4
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas/health.schema.json").read_text())
    assert schema == HealthResult.model_json_schema()
    jsonschema.validate(json.loads(output.out), schema)
    assert output.err == ""


def test_stopped_service_does_not_hide_corpus(monkeypatch):
    class Stopped(LocalProvider):
        def available_models(self):
            raise ReviewFailure("model_unavailable", "Local service is stopped")
    monkeypatch.setattr(doctor, "Ollama", Stopped)
    result = inspect_setup("local", "http://127.0.0.1:11434")
    checks = {c.id: c.status for c in result.checks}
    assert result.status == "unavailable"
    assert checks == {"engine": "ready", "corpus": "ready", "ollama": "unavailable", "model": "unknown"}


def test_missing_model_and_corpus_are_separate(monkeypatch, tmp_path):
    class Missing(LocalProvider):
        def available_models(self):
            return []
    monkeypatch.setattr(doctor, "Ollama", Missing)
    result = inspect_setup("missing", "http://127.0.0.1:11434", tmp_path / "absent.json")
    checks = {c.id: c.status for c in result.checks}
    assert checks["ollama"] == "ready" and checks["model"] == "unavailable" and checks["corpus"] == "unavailable"


def test_remote_configuration_is_structured_and_never_contacted(monkeypatch, capsys):
    from aiact.providers import Ollama
    monkeypatch.setattr(Ollama, "available_models", lambda _: pytest.fail("Remote endpoint was contacted"))
    assert main(["doctor", "--json", "--endpoint", "https://remote.example"]) == 2
    result = HealthResult.model_validate_json(capsys.readouterr().out)
    assert result.status == "unavailable" and result.endpoint is None
    assert any(e.code == "configuration" for e in result.errors)


def test_doctor_json_usage_error_is_one_document(capsys):
    assert main(["doctor", "--json", "--unknown-flag"]) == 2
    result = HealthResult.model_validate_json(capsys.readouterr().out)
    assert result.errors[0].code == "configuration"
