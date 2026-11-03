"""Opt-in Gemini REST adapter. Keys stay in headers, never URLs or errors."""
import json
import os
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .providers import ReviewFailure, SYSTEM_PROMPT, default_model

ENDPOINT = "https://generativelanguage.googleapis.com"


class NoGeminiRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReviewFailure("redirect_rejected", "Gemini requests must not redirect to another endpoint.")


def compatible_schema(value):
    """Translate equivalent schema constructs without weakening local validation."""
    if isinstance(value, list):
        return [compatible_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {("anyOf" if key == "oneOf" else key): compatible_schema(item)
              for key, item in value.items() if key != "const"}
    if "const" in value:
        result["enum"] = [value["const"]]
    if "enum" in result and "type" not in result:
        values = result["enum"]
        if values and all(isinstance(v, str) for v in values):
            result["type"] = "string"
    return result


def generation_schema(schema):
    """Keep the review grammar small; semantic choices are validated locally.

    Long question/quotation enums combined with per-passage anyOf branches
    multiply constrained-decoding states. Their content is already in the prompt.
    """
    result = compatible_schema(schema)
    definitions = result.get("$defs", {})
    if "findings" in result.get("properties", {}) and "DraftFinding" in definitions:
        citation = definitions.get("DraftCitation", {})
        branches = citation.get("anyOf", [])
        ids = [b.get("properties", {}).get("section_id", {}).get("enum", [None])[0] for b in branches]
        if ids and all(isinstance(sid, str) for sid in ids):
            definitions["DraftCitation"] = {
                "type": "object", "properties": {
                    "section_id": {"type": "string", "enum": list(dict.fromkeys(ids))},
                    "quote": {"type": "string"}}, "required": ["section_id", "quote"]}
        definitions["DraftFinding"]["properties"]["context_question"] = {"type": "string"}
    return result


def bad_request_failure(error):
    """Classify bounded Google diagnostics; never return provider-controlled text."""
    try:
        payload = json.loads(error.read(32769))
        detail = payload.get("error", {})
        message = str(detail.get("message", "")).lower()
        reasons = {str(d.get("reason", "")) for d in detail.get("details", []) if isinstance(d, dict)}
    except (ValueError, OSError, AttributeError, TypeError):
        message, reasons = "", set()
    if reasons & {"API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED"} or "api key not valid" in message:
        return "authentication", "Gemini rejected the API key (HTTP 400). Replace it using Configure Gemini."
    if any(t in message for t in ("schema", "too many states", "constraint")):
        return "configuration", "Gemini rejected the structured-output schema (HTTP 400). Update the engine; this is a request/schema compatibility error."
    if "thinking" in message:
        return "configuration", "Gemini rejected the thinking configuration (HTTP 400). Check the selected model's thinking support."
    if any(t in message for t in ("unknown name", "unknown field", "cannot find field")):
        return "configuration", "Gemini rejected an API request field (HTTP 400). Update the engine's REST request format."
    if any(t in message for t in ("location", "country", "region")):
        return "configuration", "Gemini rejected this account/location configuration (HTTP 400). Check API availability for your account."
    return "configuration", "Gemini rejected the request (HTTP 400); its cause was not recognized. Check model access and API configuration."


class Gemini:
    name = "gemini"
    endpoint = ENDPOINT

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or default_model("gemini")
        if not re.fullmatch(r"gemini-[A-Za-z0-9._-]{1,100}", self.model):
            raise ReviewFailure("configuration", "Use a Gemini model ID such as gemini-3.1-flash-lite.")
        self._api_key = (api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")).strip()
        if not self._api_key or len(self._api_key) > 4096 or any(c.isspace() for c in self._api_key):
            raise ReviewFailure("credentials_missing", "Set a Gemini API key using Configure Gemini in VS Code or GEMINI_API_KEY in the CLI environment.")
        self.opener = build_opener(ProxyHandler({}), NoGeminiRedirect())

    def request(self, body: dict | None = None, timeout: float = 5) -> dict:
        deadline = time.monotonic() + min(timeout, 60)
        for attempt in range(2):
            try:
                return self._request_once(body, deadline - time.monotonic())
            except ReviewFailure as exc:
                remaining = deadline - time.monotonic()
                if attempt or not getattr(exc, "retryable", False) or remaining <= 0.5:
                    raise
                time.sleep(0.5)
        raise ReviewFailure("provider_unavailable", "Gemini service unavailable.")

    def _request_once(self, body: dict | None = None, timeout: float = 5) -> dict:
        if timeout <= 0:
            raise ReviewFailure("timeout", "The scan deadline was reached.")
        url = f"{ENDPOINT}/v1beta/models/{self.model}" + (":generateContent" if body is not None else "")
        request = Request(url, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key})
        try:
            with self.opener.open(request, timeout=min(timeout, 60)) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ReviewFailure("invalid_response", "Gemini response exceeded the response budget.")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except HTTPError as exc:
            # Never echo the response body, URL, credentials or request text.
            if exc.code == 400:
                code, message = bad_request_failure(exc)
                raise ReviewFailure(code, message) from None
            messages = {
                400: ("configuration", "Gemini rejected the request. Check the key, model and JSON schema support."),
                401: ("authentication", "Gemini rejected the API key. Replace it using Configure Gemini."),
                403: ("authentication", "Gemini access denied. Check API key permissions and model access."),
                404: ("model_unavailable", "Gemini model unavailable. Choose a supported model in the provider settings."),
                429: ("rate_limit", "Gemini quota or rate limit reached. Check quota/billing and retry later."),
            }
            code, message = messages.get(exc.code, ("provider_unavailable", f"Gemini returned HTTP {exc.code}. The remote request failed; retry later."))
            failure = ReviewFailure(code, message)
            failure.retryable = exc.code in {500, 502, 503, 504}
            raise failure from None
        except (TimeoutError, socket.timeout):
            raise ReviewFailure("timeout", "Gemini inference timed out. Retry with a narrower input.") from None
        except URLError:
            raise ReviewFailure("provider_unavailable", "Cannot reach Gemini. Check your internet connection.") from None
        except (ValueError, UnicodeError):
            raise ReviewFailure("invalid_response", "Gemini returned malformed JSON.") from None

    def check_model(self):
        details = self.request()
        methods = details.get("supportedGenerationMethods")
        if details.get("name") != f"models/{self.model}" or not isinstance(methods, list) or "generateContent" not in methods:
            raise ReviewFailure("model_unavailable", "Selected Gemini model does not support content generation.")

    def generate_json(self, prompt: str, schema: dict, timeout: float) -> dict:
        config = {"temperature": 0, "maxOutputTokens": 4096 if "findings" in schema.get("properties", {}) else 2048,
                  "responseFormat": {"text": {"mimeType": "APPLICATION_JSON", "schema": generation_schema(schema)}}}
        if self.model.startswith("gemini-3.1-flash-lite"):
            config["thinkingConfig"] = {"thinkingLevel": "minimal"}
        result = self.request({"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                               "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                               "generationConfig": config}, timeout)
        self.usage_totals = getattr(self, "usage_totals", {})
        for source, target in [("promptTokenCount", "input_tokens"), ("candidatesTokenCount", "output_tokens"), ("totalTokenCount", "total_tokens")]:
            count = result.get("usageMetadata", {}).get(source)
            if type(count) is int and 0 <= count <= 1_000_000_000:
                self.usage_totals[target] = self.usage_totals.get(target, 0) + count
        try:
            candidates = result.get("candidates", [])
            if not candidates:
                if result.get("promptFeedback", {}).get("blockReason"):
                    raise ReviewFailure("content_blocked", "Gemini blocked this request; no review was produced.")
                raise ValueError()
            candidate = candidates[0]
            reason = candidate.get("finishReason")
            if reason in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"}:
                raise ReviewFailure("content_blocked", "Gemini blocked the response; no review was produced.")
            if reason != "STOP":
                raise ValueError()
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            raise ReviewFailure("invalid_response", "Gemini response was incomplete or invalid JSON; review unavailable.") from None
