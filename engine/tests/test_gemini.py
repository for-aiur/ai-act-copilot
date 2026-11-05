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
    assert 0 < timeout <= 12 and request.full_url.endswith("gemini-3.1-flash-lite:generateContent")
    assert request.full_url.startswith("https://generativelanguage.googleapis.com/") and KEY not in request.full_url
    assert dict((k.lower(), v) for k, v in request.header_items())["x-goog-api-key"] == KEY
    body = json.loads(request.data)
    config = body["generationConfig"]
    assert config["maxOutputTokens"] == 2048 and config["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert config["responseFormat"]["text"]["schema"]["properties"]["answer"] == {"enum": ["yes"], "type": "string"}
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


@pytest.mark.parametrize("message,reason,code,fragment", [
    ("API key not valid", "API_KEY_INVALID", "authentication", "API key"),
    ("properties.x.type schema missing", "", "configuration", "schema"),
    ("Unknown name responseFormat", "", "configuration", "request field"),
    ("Unsupported thinking level", "", "configuration", "thinking"),
])
def test_bad_request_diagnostics_are_specific_and_redacted(monkeypatch,message,reason,code,fragment):
    provider=Gemini(api_key=KEY)
    payload={"error":{"message":message+" "+KEY,"details":[{"reason":reason}]}}
    error=HTTPError("https://example.test/"+KEY,400,KEY,{},io.BytesIO(json.dumps(payload).encode()))
    mock_http(monkeypatch,provider,error=error)
    with pytest.raises(ReviewFailure) as caught: provider.generate_json("data",{},3)
    assert caught.value.code==code and fragment in str(caught.value) and KEY not in str(caught.value)


def test_review_transport_schema_avoids_long_enum_cross_product():
    from aiact.gemini import generation_schema
    from aiact.validation import DraftReview
    schema=DraftReview.model_json_schema()
    schema['$defs']['DraftCitation']={'anyOf':[{'type':'object','properties':{'section_id':{'const':'article-10-2'},'quote':{'enum':['A long exact supporting quotation']}}}]}
    schema['$defs']['DraftFinding']['properties']['context_question']={'enum':['A long exact reviewed question?']}
    output=generation_schema(schema)
    citation=output['$defs']['DraftCitation']
    assert 'anyOf' not in citation
    assert citation['properties']['section_id']=={'type':'string','enum':['article-10-2']}
    assert citation['properties']['quote']=={'type':'string'}
    assert output['$defs']['DraftFinding']['properties']['context_question']=={'type':'string'}
    assert schema['$defs']['DraftFinding']['properties']['context_question']['enum']


def test_review_transport_schema_drops_dynamic_quote_enum_but_keeps_source_ids():
    from aiact.gemini import generation_schema
    from aiact.validation import DraftReview
    schema=DraftReview.model_json_schema()
    citation=schema['$defs']['DraftCitation']['properties']
    citation['section_id']={'type':'string','enum':[f'article-{i}' for i in range(6)]}
    citation['quote']['enum']=[f'Exact legal text option {i}' for i in range(48)]
    output=generation_schema(schema)
    generated=output['$defs']['DraftCitation']['properties']
    assert generated['section_id']['enum']==[f'article-{i}' for i in range(6)]
    assert generated['quote']['type']=='string'
    assert 'enum' not in generated['quote']
    assert len(schema['$defs']['DraftCitation']['properties']['quote']['enum'])==48


def test_exact_passage_quote_does_not_need_to_match_compact_quote_choices():
    from aiact.contracts import Evidence
    from aiact.validation import (DraftReview, bind_exact_citations,
        citation_quote_sources, validate_review)
    from aiact.providers import ReviewFailure
    import pytest

    passage={"id":"article-10-2","text":"".join(chr(65+(index%26)) for index in range(450)),"url":"https://eur-lex.europa.eu/"}
    quote=passage['text'][180:280]
    choices=citation_quote_sources([passage])
    assert quote not in choices
    draft=DraftReview.model_validate({"findings":[{"title":"Check safeguards",
        "explanation":"The wider process needs review.","kind":"context_question","priority":"medium",
        "evidence_id":"E1","citations":[{"section_id":passage['id'],"quote":quote}],
        "suggested_next_action":"Inspect the process.","context_question":"Who can access the data?"}]})
    bound=bind_exact_citations(draft,choices,{passage['id']})
    evidence={"E1":Evidence(path="review.py",start_line=1,end_line=1,quote="model.generate()")}
    findings=validate_review(bound,evidence,{"review.py":"model.generate()"},[passage])
    assert findings[0].citations[0].quote==quote

    invented=draft.model_copy(update={"findings":[draft.findings[0].model_copy(update={
        "citations":[draft.findings[0].citations[0].model_copy(update={"quote":"Invented source words here."})]})]})
    with pytest.raises(ReviewFailure,match="not in the retrieved passages"):
        validate_review(invented,evidence,{"review.py":"model.generate()"},[passage])


def test_transient_service_error_retries_once_with_shared_budget(monkeypatch):
    import aiact.gemini as module
    provider=Gemini(api_key=KEY);calls=[]
    monkeypatch.setattr(module.time,"sleep",lambda _:None)
    def open_request(request,timeout):
        calls.append(timeout)
        if len(calls)==1:raise HTTPError("https://example.test",503,"",{},io.BytesIO(b""))
        return io.BytesIO(json.dumps(response({"ok":True})).encode())
    monkeypatch.setattr(provider.opener,"open",open_request)
    assert provider.generate_json("data",{},4)=={"ok":True}
    assert len(calls)==2 and 0<calls[1]<=calls[0]<=4


def test_persistent_service_failure_reports_status_after_one_retry(monkeypatch):
    import aiact.gemini as module
    provider=Gemini(api_key=KEY)
    monkeypatch.setattr(module.time,"sleep",lambda _:None)
    calls=mock_http(monkeypatch,provider,error=HTTPError("https://example.test",503,"",{},io.BytesIO(b"")))
    with pytest.raises(ReviewFailure,match="HTTP 503"):provider.generate_json("data",{},4)
    assert len(calls)==2
