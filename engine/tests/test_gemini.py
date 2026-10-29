import io
import json
from urllib.error import HTTPError, URLError

import pytest

from aiact.gemini import Gemini, NoGeminiRedirect
from aiact.providers import ReviewFailure, create_provider, default_model

KEY = "test-only-api-key"


def response(value, reason="STOP"):
    return {"candidates": [{"finishReason": reason, "content": {"parts": [{"text": json.dumps(value)}]}}]}


def mock_http(monkeypatch, provider, payload=None, error=None):
    calls = []
    def open_request(request, timeout):
        calls.append((request, timeout))
        if error:
            raise error
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(provider.opener, "open", open_request)
    return calls


def test_structured_request_key_header_and_schema(monkeypatch):
    provider = Gemini(api_key=KEY)
    calls = mock_http(monkeypatch, provider, response({"answer": "yes"}))
    schema = {"type": "object", "properties": {"answer": {"const": "yes"}}, "required": ["answer"]}
    assert provider.generate_json("untrusted source data", schema, 12) == {"answer": "yes"}
    request, timeout = calls[0]
    assert timeout == 12 and request.full_url.endswith("gemini-3.1-flash-lite:generateContent")
    assert request.full_url.startswith("https://generativelanguage.googleapis.com/") and KEY not in request.full_url
    assert dict((k.lower(), v) for k, v in request.header_items())["x-goog-api-key"] == KEY
    body = json.loads(request.data)
    config = body["generationConfig"]
    assert config["maxOutputTokens"] == 2048 and config["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert config["responseFormat"]["text"]["schema"]["properties"]["answer"] == {"enum": ["yes"]}
    assert schema["properties"]["answer"] == {"const": "yes"}
    assert "tools" not in body


@pytest.mark.parametrize("status,code", [(400,"configuration"),(401,"authentication"),(403,"authentication"),(404,"model_unavailable"),(429,"rate_limit"),(503,"provider_unavailable")])
def test_http_failures_never_echo_key_or_raw_body(monkeypatch, status, code):
    provider = Gemini(api_key=KEY)
    error = HTTPError("https://example.test/" + KEY, status, KEY, {}, io.BytesIO(KEY.encode()))
    mock_http(monkeypatch, provider, error=error)
    with pytest.raises(ReviewFailure) as caught:
        provider.generate_json("data", {}, 3)
    assert caught.value.code == code and KEY not in str(caught.value)


@pytest.mark.parametrize("error,code", [(TimeoutError(KEY),"timeout"),(URLError(KEY),"provider_unavailable")])
def test_transport_failures_are_sanitized(monkeypatch, error, code):
    provider = Gemini(api_key=KEY)
    mock_http(monkeypatch, provider, error=error)
    with pytest.raises(ReviewFailure) as caught:
        provider.generate_json("data", {}, 3)
    assert caught.value.code == code and KEY not in str(caught.value)


@pytest.mark.parametrize("payload,code", [
    ({"promptFeedback":{"blockReason":"SAFETY"}},"content_blocked"),
    (response({}, "SAFETY"),"content_blocked"),
    (response({}, "MAX_TOKENS"),"invalid_response"),
    ({"candidates":[]},"invalid_response"),
    ({"candidates":[None]},"invalid_response"),
    ({"candidates":[{"finishReason":"STOP","content":{"parts":[None]}}]},"invalid_response"),
    (response(["not an object"]),"invalid_response"),
])
def test_blocked_and_incomplete_results_fail(monkeypatch, payload, code):
    provider = Gemini(api_key=KEY)
    mock_http(monkeypatch, provider, payload)
    with pytest.raises(ReviewFailure) as caught:
        provider.generate_json("data", {}, 3)
    assert caught.value.code == code


def test_model_check_does_not_run_inference(monkeypatch):
    provider = Gemini(api_key=KEY)
    calls = mock_http(monkeypatch, provider, {"name": "models/"+provider.model, "supportedGenerationMethods":["generateContent"]})
    provider.check_model()
    assert calls[0][0].data is None and ":generateContent" not in calls[0][0].full_url


def test_missing_key_invalid_model_and_redirect(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ReviewFailure) as caught:
        create_provider("gemini", None, "http://127.0.0.1:11434")
    assert caught.value.code == "credentials_missing"
    with pytest.raises(ReviewFailure):
        Gemini("gemini-x/../../somewhere", KEY)
    with pytest.raises(ReviewFailure, match="redirect"):
        NoGeminiRedirect().redirect_request(None, None, 302, "", {}, "https://other.test")
    assert default_model("gemini") == "gemini-3.1-flash-lite"


def test_missing_key_cli_is_one_structured_failure(monkeypatch, capsys):
    from aiact.cli import main
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert main(["scan", "missing.py", "--provider", "gemini", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed" and result["errors"][0]["code"] == "credentials_missing"


def test_malformed_model_metadata_is_an_explicit_failure(monkeypatch):
    provider = Gemini(api_key=KEY)
    mock_http(monkeypatch, provider, {"name": "models/"+provider.model, "supportedGenerationMethods": None})
    with pytest.raises(ReviewFailure) as caught:
        provider.check_model()
    assert caught.value.code == "model_unavailable"
