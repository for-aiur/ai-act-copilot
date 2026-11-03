"""Explicit domain adapters. Core ranking/evaluation does not interpret legal IDs."""
import gzip
import json
import re
from importlib.resources import files

from .contracts import Chunk, Document, KnowledgeDomain, Snapshot, SourceMetadata, DateRule
from .official import checksum, CELEX

DOMAINS = (
    KnowledgeDomain(id="ai-act", name="EU AI Act", description="Full pinned official 2026 source inventory", reference_hint="Article 10, Annex III, recital 26"),
    KnowledgeDomain(id="workbench-api", name="Workbench API guide", description="Small authored technical reference domain", reference_hint="health, drafts, corpus"),
)


def load_snapshot(domain_id="ai-act") -> Snapshot:
    if domain_id == "ai-act":
        raw = json.loads(gzip.decompress(files("aiact").joinpath("data/full-act.json.gz").read_bytes()))
        identity = raw.pop("snapshot_id")
        if checksum(raw) != identity:
            raise ValueError("Official snapshot integrity mismatch")
        timing = next(d["text"] for d in raw["documents"] if d["id"] == "article-113")
        rules = (
            DateRule(condition="High-risk under Article 6(2) and Annex III; Article 113(c) scope and exceptions apply", date="2027-12-02", source_id="article-113", quote="2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III; and"),
            DateRule(condition="High-risk under Article 6(1) and Annex I; Article 113(c) scope and exceptions apply", date="2028-08-02", source_id="article-113", quote="2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I;"),
        )
        if any(rule.quote not in timing for rule in rules):
            raise ValueError("Reviewed date rule no longer matches the official source")
        return Snapshot(domain_id=domain_id, snapshot_id=identity, source_version=CELEX, parser_version=raw["parser_version"],
            documents=tuple(Document(id=d["id"], title=d["title"], text=d["text"], source_url=d["source_url"], kind=d["kind"], checksum=d["checksum"],
                metadata=SourceMetadata(origin=d["origin"], binding=d["binding"], chapter=d["chapter"], celex=d["source_celex"],
                    publication_date=d["publication_date"], consolidated_date=d["consolidated_date"],
                    entry_into_force="2024-08-01" if d["origin"] == "original" else "2026-07-27" if d["origin"] == "amendment" else None,
                    applicability_rules=rules if d["kind"] == "article" and d["id"].split("-")[1].isdigit() and 6 <= int(d["id"].split("-")[1]) <= 27 else (),
                    applicability_status=d["applicability"]["status"], applicability_sources=tuple(d["applicability"]["source_ids"]))) for d in raw["documents"]),
            chunks=tuple(Chunk(**c) for c in raw["chunks"]), source_hashes=tuple(s["sha256"] for s in raw["sources"]), scope_limits=tuple(raw["scope_limits"]), complete=raw["coverage"]["complete"])
    if domain_id != "workbench-api":
        raise ValueError("Unknown knowledge domain")
    contents = [
        ("health", "Readiness checks", "GET /api/health checks corpus integrity and database availability. It does not run inference or download models."),
        ("drafts", "Scenario draft persistence", "POST /api/drafts saves a local scenario draft with context and pinned source references. GET /api/drafts lists the newest 100 saved drafts. Saving does not approve a golden test."),
        ("corpus", "Source library", "GET /api/corpus searches packaged source documents. Official source links are opened only when selected by the user."),
    ]
    docs = tuple(Document(id=i, title=t, text=body, source_url="https://github.com/for-aiur/ai-act-copilot/blob/main/docs/WORKBENCH.md",
        kind="guide", checksum=checksum(body.encode()), metadata=SourceMetadata(origin="authored_technical_fixture")) for i, t, body in contents)
    chunks = tuple(Chunk(id=d.id + "-1", document_id=d.id, title=d.title, text=d.text, start=0, end=len(d.text), checksum=d.checksum) for d in docs)
    return Snapshot(domain_id=domain_id, snapshot_id=checksum([d.model_dump(mode="json") for d in docs]), source_version="api-guide-1",
        parser_version="authored-1", documents=docs, chunks=chunks, source_hashes=tuple(d.checksum for d in docs),
        scope_limits=("Authored technical fixture, not legal content.",), complete=True)


def resolve_reference(domain_id: str, query: str) -> tuple[str, ...]:
    if domain_id == "workbench-api":
        return tuple(i for i in ("health", "drafts", "corpus") if re.search(r"(?:/api/|\breference\s+|\bdocument\s+)" + i + r"\b", query, re.I))
    found = ["article-" + n.lower() for n in re.findall(r"\barticle\s+(\d+[a-z]?)\b", query, re.I)]
    found += ["annex-" + n.lower() for n in re.findall(r"\bannex\s+([ivx]+)\b", query, re.I)]
    found += ["recital-" + n for n in re.findall(r"\brecital\s+(\d+)\b", query, re.I)]
    return tuple(dict.fromkeys(found))
