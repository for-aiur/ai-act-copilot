import json
from aiact.contracts import Metadata, ScanError, ScanResult
from aiact.settings import Settings
from aiact.telemetry import Trace


def test_trace_payload_has_no_source_context_keys_prompts_or_answers(monkeypatch):
    captured = []
    monkeypatch.setattr("aiact.telemetry.submit", lambda settings, payload: captured.append(payload))
    settings = Settings(langfuse_enabled=True, langfuse_public_key="test-public", langfuse_secret_key="secret-key")
    trace = Trace(settings)
    trace.attributes["source"] = "PRIVATE_SOURCE"
    trace.attributes["prompt"] = "PRIVATE_PROMPT"
    with trace.span("purpose_extraction"):
        pass
    result = ScanResult(status="failed", errors=[ScanError(code="timeout", message="PRIVATE_ANSWER")],
        metadata=Metadata(provider="gemini", model_id="gemini-test"))
    trace.finish(result, "rag-1")
    serialized = json.dumps(captured)
    assert all(secret not in serialized for secret in ["PRIVATE_SOURCE", "PRIVATE_PROMPT", "PRIVATE_ANSWER", "secret-key"])
    assert "purpose_extraction" in serialized and "rag-1" in serialized
    assert len(trace.id) == 32


def test_disabled_and_broken_export_cannot_affect_result(monkeypatch):
    monkeypatch.setattr("aiact.telemetry.submit", lambda *args: (_ for _ in ()).throw(RuntimeError("offline")))
    result = ScanResult(status="complete")
    Trace(Settings()).finish(result)
    Trace(Settings(langfuse_enabled=True, langfuse_public_key="test-public", langfuse_secret_key="secret-key")).finish(result)
    assert result.status == "complete"
