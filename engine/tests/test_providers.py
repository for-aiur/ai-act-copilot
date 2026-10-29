import pytest
from aiact.providers import Ollama, ReviewFailure, local_endpoint, NoRedirect


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.1.2:11434", "http://localhost@evil.test", "http://localhost/api", "http://localhost?x=1", "file:///tmp/test"])
def test_remote_endpoint_rejected(url):
    with pytest.raises(ReviewFailure, match="loopback"):
        local_endpoint(url)


def test_localhost_is_pinned_and_proxy_disabled():
    assert local_endpoint("http://localhost:1234") == "http://127.0.0.1:1234"
    with pytest.raises(ReviewFailure, match="redirect"):
        NoRedirect().redirect_request(None, None, 302, "", {}, "http://evil.test")


def test_model_missing_and_remote(monkeypatch):
    provider = Ollama()
    monkeypatch.setattr(provider, "available_models", lambda: [])
    with pytest.raises(ReviewFailure, match="not installed"):
        provider.ensure_local_model()
    with pytest.raises(ReviewFailure, match="cloud"):
        Ollama("some:cloud")


def test_bad_response(monkeypatch):
    provider = Ollama()
    monkeypatch.setattr(provider, "request", lambda *args, **kwargs: {"done": True, "response": "not json"})
    with pytest.raises(ReviewFailure, match="invalid JSON"):
        provider.generate_json("data", {}, 1)
