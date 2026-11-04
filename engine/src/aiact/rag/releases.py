"""Content-addressed RAG bundles, explicit activation, and integrity verification."""
import gzip
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .contracts import Snapshot
from .domains import load_snapshot
from .embeddings import LocalEmbedder
from .official import checksum
from .store import Store

PIPELINE_VERSION = "hybrid-1"


def release_identity(manifest):
    content = {k: v for k, v in manifest.items() if k != "rag_release_id"}
    if content.get("schema_version") == "2":
        content.pop("git_revision", None)
    return checksum(content)


def compatibility(manifest, settings=None):
    # Build bookkeeping, evaluation and persistence changes do not change search.
    relevant = {"retriever.py", "domains.py", "embeddings.py"}
    changed = [name for name, digest in manifest.get("implementation", {}).items()
               if name in relevant and checksum(Path(__file__).with_name(name).read_bytes()) != digest]
    reason = "This candidate uses older search code. Create a candidate from this checkout to test it here." if changed else None
    if settings and manifest.get("mode") == "hybrid" and manifest.get("embedding", {}).get("model") != settings.embedding_model:
        reason = "The selected embedding model changed. Build a new candidate before running search."
    return {"compatible": reason is None, "compatibility_reason": reason}


def verify_bundle(directory: Path, allow_staging=False) -> tuple[dict, Snapshot, list]:
    if not allow_staging and not re.fullmatch(r"[a-f0-9]{64}", directory.name):
        raise ValueError("Invalid content-addressed release ID")
    manifest = json.loads((directory / "manifest.json").read_text())
    identity = manifest.pop("rag_release_id")
    if (not allow_staging and directory.name != identity) or release_identity(manifest) != identity:
        raise ValueError("RAG manifest identity mismatch")
    manifest["rag_release_id"] = identity
    if set(manifest["file_hashes"]) != {"snapshot.json", "vectors.json.gz"}:
        raise ValueError("Unexpected artifact file inventory")
    for name, digest in manifest["file_hashes"].items():
        if checksum((directory / name).read_bytes()) != digest:
            raise ValueError("RAG artifact file checksum mismatch")
    snapshot = Snapshot.model_validate_json((directory / "snapshot.json").read_bytes())
    vectors = json.loads(gzip.decompress((directory / "vectors.json.gz").read_bytes()))
    if snapshot.snapshot_id != manifest["snapshot_id"] or snapshot.domain_id != manifest["domain_id"]:
        raise ValueError("Mixed source and RAG versions")
    if vectors and (len(vectors) != len(snapshot.chunks) or any(len(v) != manifest["embedding"]["dimension"] for v in vectors)):
        raise ValueError("Vector inventory/dimension mismatch")
    if manifest["mode"] == "hybrid" and not vectors:
        raise ValueError("Hybrid release has no dense index")
    return manifest, snapshot, vectors


def build_release(settings, domain_id="ai-act", download=False, lexical_only=False, embedder=None):
    snapshot = load_snapshot(domain_id)
    if not snapshot.complete:
        raise ValueError("Incomplete source snapshot cannot be built")
    vectors = []
    embedding = {"provider": "none", "model": "none", "revision": "none", "dimension": 0}
    if not lexical_only:
        embedder = embedder or LocalEmbedder(settings.embedding_model, settings.models_path, download)
        if settings.embedding_revision not in {"file-sha256-pinned-at-build", embedder.manifest["revision"]}:
            raise ValueError("Embedding files differ from the configured revision")
        embedding = embedder.manifest
        cache_key = checksum({"chunks": [(c.id, c.title, c.checksum) for c in snapshot.chunks], "embedding": embedding})
        cache = settings.data_dir / "embedding-cache" / (cache_key + ".json.gz")
        if cache.exists():
            vectors = json.loads(gzip.decompress(cache.read_bytes()))
        else:
            # Reuse only checksum-verified vectors with the identical input/model.
            for existing in (settings.data_dir / "releases").glob("*/manifest.json"):
                previous, previous_snapshot, previous_vectors = verify_bundle(existing.parent)
                if previous["embedding"] == embedding and [(c.id, c.title, c.checksum) for c in previous_snapshot.chunks] == [(c.id, c.title, c.checksum) for c in snapshot.chunks]:
                    vectors = previous_vectors
                    break
            if not vectors:
                vectors = embedder.passages([c.title + "\n" + c.text for c in snapshot.chunks])
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(gzip.compress(json.dumps(vectors).encode(), mtime=0))
    source_files = ["contracts.py", "domains.py", "embeddings.py", "releases.py", "retriever.py", "store.py", "official.py", "evaluation.py"]
    implementation = {name: checksum(Path(__file__).with_name(name).read_bytes()) for name in source_files if Path(__file__).with_name(name).exists()}
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3).stdout.strip() or "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        revision = "unavailable"
    snapshot_bytes = snapshot.model_dump_json().encode()
    vector_bytes = gzip.compress(json.dumps(vectors, separators=(",", ":")).encode(), mtime=0)
    manifest = {
        "schema_version": "2", "domain_id": domain_id, "snapshot_id": snapshot.snapshot_id,
        "source_version": snapshot.source_version, "parser_version": snapshot.parser_version,
        "domain_adapter_version": "1", "chunker": "official-block-offsets-1",
        "git_revision": revision, "implementation": implementation,
        "mode": "lexical" if lexical_only else "hybrid", "embedding": embedding,
        "vector_backend": settings.vector_backend, "vector_index_fingerprint": checksum(vector_bytes),
        "vector_client_version": importlib.metadata.version("qdrant-client") if not lexical_only else "not-used",
        "lexical_index": {"backend": "sqlite-fts5-bm25" if settings.database_url.get_secret_value().startswith("sqlite:") else "postgresql-tsvector",
                          "version": "1", "term_combination": "OR"},
        "query_planner": "explicit-context-intents-1", "fusion": {"algorithm": "rrf", "k": settings.fusion_k},
        "reranker": {"version": PIPELINE_VERSION, "exact_boost": settings.exact_reference_boost,
            "lexical_overlap_weight": settings.lexical_overlap_weight},
        "expansion_policy": "bounded-parent-cross-reference-1",
        "retrieval_config": {"stage_candidates": settings.stage_candidates, "max_intents": settings.max_intents,
            "max_query_terms": settings.max_query_terms,
            "max_query_bytes": settings.max_query_bytes,
            "fusion_k": settings.fusion_k, "exact_reference_boost": settings.exact_reference_boost,
            "lexical_overlap_weight": settings.lexical_overlap_weight,
            "expansion_seed_limit": settings.expansion_seed_limit, "expansion_per_seed": settings.expansion_per_seed,
            "default_limit": settings.retrieval_limit},
        "budgets": {"stage_candidates": settings.stage_candidates, "intents": settings.max_intents, "output": settings.retrieval_limit},
        "gold_dataset_version": None, "evaluation_run_id": None, "quality_status": "not_evaluated",
        "file_hashes": {"snapshot.json": checksum(snapshot_bytes), "vectors.json.gz": checksum(vector_bytes)},
    }
    identity = release_identity(manifest)
    manifest["rag_release_id"] = identity
    root = settings.data_dir / "releases"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / identity
    if destination.exists():
        manifest, _, _ = verify_bundle(destination)
    else:
        staging = Path(tempfile.mkdtemp(prefix=".candidate-", dir=root))
        try:
            (staging / "snapshot.json").write_bytes(snapshot_bytes)
            (staging / "vectors.json.gz").write_bytes(vector_bytes)
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            verify_bundle(staging, allow_staging=True)
            os.rename(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    store = Store(settings.database_url.get_secret_value())
    try:
        store.put_snapshot(snapshot)
        store.put_release(manifest)
        store.restore_release(identity)
    finally:
        store.close()
    return manifest
