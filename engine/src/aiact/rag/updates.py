"""Explicit official-source discovery, staging and structured version diffs."""
import gzip
import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .official import CELEX, checksum, import_official


def discover_versions():
    query = 'SELECT ?celex WHERE { ?s <http://publications.europa.eu/ontology/cdm#resource_legal_id_celex> ?celex . FILTER(STRSTARTS(STR(?celex), "02024R1689-")) } ORDER BY DESC(?celex) LIMIT 20'
    url = "https://publications.europa.eu/webapi/rdf/sparql?" + urlencode({"query": query, "format": "application/sparql-results+json"})
    with urlopen(Request(url, headers={"Accept": "application/sparql-results+json"}), timeout=20) as response:
        payload = response.read(100001)
    if len(payload) > 100000:
        raise ValueError("Official version metadata exceeded its budget")
    values = [row["celex"]["value"] for row in json.loads(payload)["results"]["bindings"]]
    if not values or CELEX not in values:
        raise ValueError("Pinned legal version was absent from official discovery metadata")
    return {"pinned": CELEX, "available": sorted(set(values), reverse=True), "newer": sorted(v for v in set(values) if v > CELEX),
            "checked_at": datetime.now(timezone.utc).isoformat(), "source": "Publications Office SPARQL"}


def sync_staging(directory: Path):
    # No writes to packaged sources, active pointers or historical reviews.
    directory.mkdir(parents=True, exist_ok=False)
    sources = json.loads(files("aiact").joinpath("data/official/sources.json").read_text())
    for source in sources:
        with urlopen(Request(source["url"], headers={"Accept": "application/xhtml+xml", "Accept-Language": "en"}), timeout=30) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000 or checksum(raw) != source["sha256"]:
            raise ValueError("Official source changed or was incomplete. Candidate is not activated; source-policy review required.")
        (directory / source["file"]).write_bytes(gzip.compress(raw, mtime=0))
    (directory / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    candidate = import_official(directory)
    (directory / "candidate.json.gz").write_bytes(gzip.compress(json.dumps(candidate, ensure_ascii=False).encode(), mtime=0))
    return {"status": "staged", "snapshot_id": candidate["snapshot_id"], "coverage": candidate["coverage"], "active_changed": False,
            "scope": "Reverification of the pinned source pack. New editions require a reviewed parser/source manifest revision."}


def diff_snapshots(before, after, reviews=()):
    def compare(old, new):
        prior = {d.id: d for d in old}
        following = {d.id: d for d in new}
        return {"added": sorted(following.keys() - prior.keys()), "removed": sorted(prior.keys() - following.keys()),
            "modified": sorted(identity for identity in prior.keys() & following.keys() if prior[identity].model_dump() != following[identity].model_dump())}
    docs = compare(before.documents, after.documents)
    chunks = compare(before.chunks, after.chunks)
    changed = set(chunks["removed"] + chunks["modified"] + docs["removed"] + docs["modified"])
    affected = []
    for review in reviews:
        citations = {c["section_id"] for finding in review.get("payload", {}).get("scan_result", {}).get("findings", []) for c in finding["citations"]}
        if citations & changed:
            affected.append({"review_id": review["id"], "changed_citations": sorted(citations & changed)})
    return {"before": before.snapshot_id, "after": after.snapshot_id, "documents": docs, "chunks": chunks, "affected_reviews": affected,
            "changed_sources": [{"id": d.id, "url": d.source_url, "checksum": d.checksum, "metadata": d.metadata.model_dump(mode="json")}
                for d in after.documents if d.id in set(docs["added"] + docs["modified"])]}


def main(argv=None):
    import argparse
    from aiact.settings import load_settings
    from .releases import verify_bundle
    from .store import Store
    parser = argparse.ArgumentParser(prog="aiact corpus")
    parser.add_argument("action", choices=["check", "sync", "diff", "promote"])
    parser.add_argument("--staging", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--before")
    parser.add_argument("--after")
    parser.add_argument("--approval-note")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        if args.action == "check":
            report = discover_versions()
        elif args.action == "sync":
            if not args.staging:
                raise ValueError("Sync requires --staging; automatic activation is disabled.")
            output = args.output or settings.data_dir / "staging" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            report = sync_staging(output)
        else:
            store = Store(settings.database_url.get_secret_value())
            try:
                if not args.after:
                    raise ValueError("--after must be a content-addressed RAG release ID")
                after_manifest, after, _ = verify_bundle(settings.data_dir / "releases" / args.after)
                if args.action == "diff":
                    if not args.before:
                        raise ValueError("--before is required for a diff")
                    _, before, _ = verify_bundle(settings.data_dir / "releases" / args.before)
                    report = diff_snapshots(before, after, store.list_records("review", after.domain_id, limit=1000))
                else:
                    if not args.approval_note or not args.approval_note.strip():
                        raise ValueError("Explicit --approval-note is required")
                    from .benchmark import benchmark
                    evaluation = benchmark(settings, after.domain_id, args.after, include_holdout=True)
                    if evaluation["quality_gate"]["status"] != "pass":
                        raise ValueError("Promotion blocked by the expert-gold quality gate. Local tooling activation is a separate explicit command.")
                    store.activate(after.domain_id, args.after)
                    store.append("promotion", args.after, after.domain_id, {"approval_note": args.approval_note, "evaluation": evaluation})
                    report = {"status": "promoted", "rag_release_id": args.after}
            finally:
                store.close()
        print(json.dumps(report))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "active_changed": False, "error": type(exc).__name__,
            "message": str(exc) if isinstance(exc, ValueError) else "Official source operation failed; last active version preserved."}))
        return 1
