"""Opt-in metadata-only OTLP/HTTP export to the fixed Langfuse EU endpoint."""
import base64
import contextvars
import json
import queue
import secrets
import threading
import time
from contextlib import contextmanager
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

CURRENT = contextvars.ContextVar("aiact_trace", default=None)
PENDING = queue.Queue(maxsize=16)
WORKER_LOCK = threading.Lock()
WORKER = None
ALLOWED = {"provider", "model", "prompt_version", "corpus_version", "corpus_checksum", "rag_release_id",
           "status", "error_code", "input_tokens", "output_tokens", "total_tokens"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Tracing redirects are disabled")


def _send(settings, payload):
    key = settings.langfuse_public_key.get_secret_value() + ":" + settings.langfuse_secret_key.get_secret_value()
    request = Request("https://cloud.langfuse.com/api/public/otel/v1/traces", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-langfuse-ingestion-version": "4",
                 "Authorization": "Basic " + base64.b64encode(key.encode()).decode()})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=2) as response:
        response.read(4096)


def _worker():
    while True:
        settings, payload = PENDING.get()
        try:
            _send(settings, payload)
        except Exception:
            pass  # Observability must never change review outcome or log secrets.
        finally:
            PENDING.task_done()


def submit(settings, payload):
    global WORKER
    with WORKER_LOCK:
        if WORKER is None:
            WORKER = threading.Thread(target=_worker, name="aiact-trace-export", daemon=True)
            WORKER.start()
    try:
        PENDING.put_nowait((settings, payload))
    except queue.Full:
        pass


class Trace:
    def __init__(self, settings=None):
        self.settings = settings
        self.id = secrets.token_hex(16)
        self.root_id = secrets.token_hex(8)
        self.started = time.time_ns()
        self.steps = []
        self.attributes = {}

    @contextmanager
    def span(self, name):
        start = time.time_ns()
        status = "complete"
        try:
            yield
        except Exception:
            status = "failed"
            raise
        finally:
            self.steps.append({"stage": name, "start_ns": start, "end_ns": time.time_ns(), "status": status})

    def payload(self):
        def attrs(values):
            return [{"key": key, "value": {"stringValue": str(value)}} for key, value in values.items() if key in ALLOWED and value is not None]
        spans = [{"traceId": self.id, "spanId": self.root_id, "name": "ai-act-review",
            "startTimeUnixNano": str(self.started), "endTimeUnixNano": str(time.time_ns()), "attributes": attrs(self.attributes)}]
        spans.extend({"traceId": self.id, "spanId": secrets.token_hex(8), "parentSpanId": self.root_id,
            "name": step["stage"], "startTimeUnixNano": str(step["start_ns"]), "endTimeUnixNano": str(step["end_ns"]),
            "attributes": attrs({"status": step["status"]})} for step in self.steps)
        return {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "ai-act-copilot"}}]},
            "scopeSpans": [{"scope": {"name": "aiact.metadata-only"}, "spans": spans}]}]}

    def finish(self, result, rag_release_id=None):
        self.attributes.update({"provider": result.metadata.provider, "model": result.metadata.model_id,
            "prompt_version": result.metadata.prompt_version, "corpus_version": result.metadata.corpus_version,
            "corpus_checksum": result.metadata.corpus_checksum, "rag_release_id": rag_release_id, "status": result.status,
            "error_code": result.errors[0].code if result.errors else None})
        settings = self.settings
        if settings and settings.langfuse_enabled and settings.langfuse_public_key.get_secret_value() and settings.langfuse_secret_key.get_secret_value():
            try:
                submit(settings, self.payload())
            except Exception:
                pass


def traced_call(name, function, *args, **kwargs):
    trace = CURRENT.get()
    if trace:
        with trace.span(name):
            return function(*args, **kwargs)
    return function(*args, **kwargs)
