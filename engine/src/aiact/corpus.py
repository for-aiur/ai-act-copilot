"""Reviewed official subset; updates reverify it, never silently invent new law."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .providers import ReviewFailure

OFFICIAL = "https://ai-act-service-desk.ec.europa.eu/en/ai-act/"
SECTION_PAGES = {"annex-iii-4-a": "annex-3", "annex-iii-1-a": "annex-3", "article-6-2": "article-6", "article-6-3": "article-6", "article-50-1": "article-50", "article-50-2": "article-50"}


def normalize(text: str) -> str:
    return " ".join(text.split())


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self.current is not None:
            self.paragraphs.append(normalize("".join(self.current)))
            self.current = None


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def default_cache() -> Path:
    return Path.home() / ".cache" / "aiact" / "corpus.json"


def validate_corpus(data: dict) -> dict:
    try:
        if data["checksum"] != digest(data["sections"]) or not data["version"] or not data["scope_limits"]:
            raise ValueError()
        ids = set()
        for section in data["sections"]:
            sid = section["id"]
            if sid in ids or section["url"] != OFFICIAL + SECTION_PAGES[sid] or not section["text"]:
                raise ValueError()
            if section["checksum"] != hashlib.sha256(section["text"].encode()).hexdigest():
                raise ValueError()
            if not section["supporting_quotes"] or any(q not in section["text"] for q in section["supporting_quotes"]):
                raise ValueError()
            ids.add(sid)
        if ids != set(SECTION_PAGES):
            raise ValueError()
        return data
    except (KeyError, TypeError, ValueError):
        raise ReviewFailure("corpus_invalid", "Legal cache failed integrity/provenance checks. Run aiact update with a verified bundled subset.") from None


def load_corpus(path: Path | None = None) -> dict:
    try:
        if path is not None:
            text = path.read_text()
        elif default_cache().exists():
            text = default_cache().read_text()
        else:
            text = files("aiact").joinpath("data/corpus.json").read_text()
        return validate_corpus(json.loads(text))
    except (OSError, ValueError):
        raise ReviewFailure("corpus_unavailable", "Verified legal corpus is absent or unreadable. Check --corpus or reinstall the package.") from None


class NoOfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReviewFailure("update_failed", "Official source redirected; review the source change before updating.")


def fetch_official(url: str) -> bytes:
    if url not in {OFFICIAL + page for page in SECTION_PAGES.values()}:
        raise ReviewFailure("update_failed", "Unrecognized official source URL.")
    with build_opener(ProxyHandler({}), NoOfficialRedirect()).open(Request(url, headers={"User-Agent": "AIActCopilot/0.1 reviewed-subset-verifier"}), timeout=20) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ReviewFailure("update_failed", "Official source exceeded download budget.")
        return raw


def update_corpus(target: Path, fetch=fetch_official) -> dict:
    """Validate whole candidate in memory, then replace one cache file atomically."""
    try:
        candidate = validate_corpus(json.loads(files("aiact").joinpath("data/corpus.json").read_text()))
        sources = {}
        for url in sorted({s["url"] for s in candidate["sections"]}):
            raw = fetch(url)
            parser = Paragraphs()
            parser.feed(raw.decode("utf-8"))
            source_text = normalize(" ".join(parser.paragraphs))
            for section in candidate["sections"]:
                if section["url"] == url and normalize(section["text"]) not in source_text:
                    raise ReviewFailure("update_failed", f"Reviewed passage {section['id']} changed or is missing. Last good cache preserved; manual legal review required.")
            sources[url] = hashlib.sha256(raw).hexdigest()
        candidate["verified_at"] = datetime.now(timezone.utc).isoformat()
        candidate["source_checksums"] = sources
        validate_corpus(candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False, encoding="utf-8") as handle:
                name = handle.name
                json.dump(candidate, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, target)
        finally:
            if name and Path(name).exists():
                Path(name).unlink()
        return candidate
    except ReviewFailure:
        raise
    except (OSError, ValueError) as exc:
        raise ReviewFailure("update_failed", f"Official-source verification failed ({type(exc).__name__}); last good cache preserved.") from None
