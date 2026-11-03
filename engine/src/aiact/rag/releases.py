"""Content-addressed RAG bundles, explicit activation, and integrity verification."""
import gzip
import json
import os
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


def verify_bundle(directory: Path) -> tuple[dict, Snapshot, list]:
    manifest = json.loads((directory / "manifest.json").read_text())
    identity = manifest.pop("rag_release_id")
    if checksum(manifest) != identity:
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
    source_files = ["contracts.py", "domains.py", "embeddings.py", "releases.py", "retriever.py"]
    implementation = {name: checksum(Path(__file__).with_name(name).read_bytes()) for name in source_files if Path(__file__).with_name(name).exists()}
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3).stdout.strip() or "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        revision = "unavailable"
    snapshot_bytes = snapshot.model_dump_json().encode()
    vector_bytes = gzip.compress(json.dumps(vectors, separators=(",", ":")).encode(), mtime=0)
    manifest = {
        "schema_version": "1", "domain_id": domain_id, "snapshot_id": snapshot.snapshot_id,
        "source_version": snapshot.source_version, "parser_version": snapshot.parser_version,
        "domain_adapter_version": "1", "chunker": "official-block-offsets-1",
        "git_revision": revision, "implementation": implementation,
        "mode": "lexical" if lexical_only else "hybrid", "embedding": embedding,
        "vector_backend": settings.vector_backend, "vector_index_fingerprint": checksum(vector_bytes),
        "lexical_index": "sqlite-fts5-bm25-or-postgres-tsvector-1",
        "query_planner": "explicit-context-intents-1", "fusion": {"algorithm": "rrf", "k": 60},
        "reranker": {"version": PIPELINE_VERSION, "exact_boost": 1.0, "lexical_overlap_weight": 0.01},
        "expansion_policy": "bounded-parent-cross-reference-1",
        "budgets": {"stage_candidates": 30, "intents": 4, "output": 20},
        "gold_dataset_version": None, "evaluation_run_id": None, "quality_status": "not_evaluated",
        "file_hashes": {"snapshot.json": checksum(snapshot_bytes), "vectors.json.gz": checksum(vector_bytes)},
    }
    identity = checksum(manifest)
    manifest["rag_release_id"] = identity
    root = settings.data_dir / "releases"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / identity
    if destination.exists():
        verify_bundle(destination)
    else:
        staging = Path(tempfile.mkdtemp(prefix=".candidate-", dir=root))
        try:
            (staging / "snapshot.json").write_bytes(snapshot_bytes)
            (staging / "vectors.json.gz").write_bytes(vector_bytes)
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            verify_bundle(staging)
            os.rename(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    store = Store(settings.database_url.get_secret_value())
    try:
        store.put_snapshot(snapshot)
        store.put_release(manifest)
    finally:
        store.close()
    return manifest
