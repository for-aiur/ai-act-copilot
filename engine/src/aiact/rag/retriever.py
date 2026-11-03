"""Bounded lexical + local semantic retrieval with inspectable fusion and expansion."""
import re
import threading
import time
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text

from .contracts import Candidate, RetrievalRequest, RetrievalResult, StageHit
from .domains import resolve_reference
from .embeddings import LocalEmbedder
from .releases import verify_bundle
from .store import Store
from .official import checksum
from pathlib import Path

STOPWORDS = frozenset("a an the and or of to for in on is are be with this that from as it at by".split())


def words(value):
    return set(re.findall(r"[a-z0-9]+", value.casefold())) - STOPWORDS


class VectorRetriever(Protocol):
    def search(self, vector: list[float], limit: int) -> list[tuple[str, float]]: ...
    def close(self): ...


class QdrantVectorRetriever:
    def __init__(self, path, release_id, snapshot, vectors, fingerprint, dimension):
        from qdrant_client import QdrantClient, models
        self.client = QdrantClient(path=str(path), force_disable_check_same_thread=True)
        self.collection = "rag_" + release_id
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection, vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE))
            for start in range(0, len(vectors), 64):
                self.client.upsert(self.collection, points=[
                    models.PointStruct(id=str(uuid5(NAMESPACE_URL, snapshot.snapshot_id + ":" + c.id)), vector=v,
                        payload={"chunk_id": c.id, "snapshot_id": snapshot.snapshot_id, "fingerprint": fingerprint})
                    for c, v in zip(snapshot.chunks[start:start + 64], vectors[start:start + 64])])
        info = self.client.get_collection(self.collection)
        if info.points_count != len(snapshot.chunks) or info.config.params.vectors.size != dimension:
            self.client.close()
            raise ValueError("Dense index is incomplete or mismatched; rebuild explicitly.")
        first = self.client.scroll(self.collection, limit=1, with_payload=True)[0]
        if not first or first[0].payload.get("fingerprint") != fingerprint:
            self.client.close()
            raise ValueError("Dense index fingerprint mismatch")

    def search(self, vector, limit):
        return [(point.payload["chunk_id"], float(point.score)) for point in self.client.query_points(
            self.collection, query=vector, limit=limit, with_payload=True).points]

    def close(self):
        self.client.close()


class LegalRetriever(Protocol):
    def search(self, request: RetrievalRequest) -> RetrievalResult: ...


class HybridRetriever:
    def __init__(self, settings, release_id, store=None, embedder=None, vector_factory=QdrantVectorRetriever):
        self.settings = settings
        self.manifest, self.snapshot, vectors = verify_bundle(settings.data_dir / "releases" / release_id)
        if any(checksum(Path(__file__).with_name(name).read_bytes()) != digest for name, digest in self.manifest["implementation"].items()):
            raise ValueError("Runtime implementation changed. Build a new RAG candidate; historical releases are preserved.")
        self.store = store or Store(settings.database_url.get_secret_value())
        self.owns_store = store is None
        if self.store.release(release_id) != self.manifest:
            raise ValueError("Database and artifact release manifests differ")
        self.chunks = {c.id: c for c in self.snapshot.chunks}
        self.documents = {d.id: d for d in self.snapshot.documents}
        self.vector = None
        self.embedder = None
        self.lock = threading.RLock()
        if self.manifest["mode"] == "hybrid":
            self.embedder = embedder or LocalEmbedder(settings.embedding_model, settings.models_path)
            if self.embedder.manifest != self.manifest["embedding"]:
                raise ValueError("Embedding model/version mismatch; do not mix RAG builds")
            self.vector = vector_factory(settings.vector_path, release_id, self.snapshot, vectors,
                self.manifest["vector_index_fingerprint"], self.manifest["embedding"]["dimension"])

    def lexical(self, query: str, limit=30):
        terms = sorted(words(query))[:40]
        if not terms:
            return []
        with self.store.engine.connect() as db:
            if self.store.sqlite:
                rows = db.execute(text("SELECT chunk_id, bm25(rag_fts,0,0,2,1) AS score FROM rag_fts WHERE rag_fts MATCH :q AND snapshot_id=:s ORDER BY score,chunk_id LIMIT :k"),
                    {"q": " OR ".join('"' + t + '"' for t in terms), "s": self.snapshot.snapshot_id, "k": limit})
                return [(r[0], -float(r[1])) for r in rows]
            rows = db.execute(text("SELECT id, ts_rank_cd(to_tsvector('english', CAST(payload AS jsonb)->>'text'), plainto_tsquery('english', :q)) AS score FROM rag_chunks WHERE snapshot_id=:s AND to_tsvector('english',CAST(payload AS jsonb)->>'text') @@ plainto_tsquery('english',:q) ORDER BY score DESC,id LIMIT :k"),
                {"q": " ".join(terms), "s": self.snapshot.snapshot_id, "k": limit})
            return [(r[0], float(r[1])) for r in rows]

    def search(self, request):
        with self.lock:
            return self._search(request)

    def _search(self, request):
        start = time.monotonic()
        if request.domain_id != self.snapshot.domain_id:
            raise ValueError("Request and index domains differ")
        context = request.context
        query = "\n".join([request.scenario, context.actor_role, context.deployment, context.constraints])
        if len(query.encode()) > self.settings.max_query_bytes:
            raise ValueError("Query exceeds the configured byte budget")
        intents = list(dict.fromkeys([query, *request.intents]))[:4]
        stage_lists = {"lexical": [], "dense": [], "exact": [], "expansion": []}
        reference_ids = resolve_reference(request.domain_id, query + " " + " ".join(request.intents))
        exact_chunks = [c for c in self.snapshot.chunks if c.document_id in reference_ids]
        exact_chunks.sort(key=lambda c: (-len(words(query) & words(c.text)), c.id))
        for rank, chunk in enumerate(exact_chunks[:30], 1):
            stage_lists["exact"].append(StageHit(chunk_id=chunk.id, rank=rank, score=1.0, reason="Explicit reference resolved by domain adapter"))
        for intent in intents:
            for rank, (identity, score) in enumerate(self.lexical(intent), 1):
                stage_lists["lexical"].append(StageHit(chunk_id=identity, rank=rank, score=score, reason="FTS lexical rank for explicit context"))
            if self.vector:
                for rank, (identity, score) in enumerate(self.vector.search(self.embedder.query(intent), 30), 1):
                    stage_lists["dense"].append(StageHit(chunk_id=identity, rank=rank, score=score, reason="Local embedding cosine similarity"))
        scores, paths = {}, {}
        for stage in ("lexical", "dense", "exact"):
            for hit in stage_lists[stage]:
                if hit.chunk_id not in self.chunks:
                    raise ValueError("Index returned a chunk outside its pinned snapshot")
                if request.kinds and self.documents[self.chunks[hit.chunk_id].document_id].kind not in request.kinds:
                    continue
                scores.setdefault(hit.chunk_id, {})
                scores[hit.chunk_id][stage] = max(scores[hit.chunk_id].get(stage, 0), hit.score)
                scores[hit.chunk_id]["fusion"] = scores[hit.chunk_id].get("fusion", 0) + 1 / (60 + hit.rank)
                paths.setdefault(hit.chunk_id, set()).add(stage)
        for identity, values in scores.items():
            overlap = len(words(query) & words(self.chunks[identity].text)) / max(1, len(words(query)))
            values["rerank"] = values["fusion"] + (1.0 if "exact" in values else 0) + .01 * overlap
        ranking = sorted(scores, key=lambda identity: (-scores[identity]["rerank"], identity))
        # Keep parent/exception context discoverable without replacing the candidate set.
        for identity in ranking[:3]:
            chunk = self.chunks[identity]
            related = [c for c in self.snapshot.chunks if c.document_id in chunk.references or (c.document_id == chunk.document_id and c.id != identity)]
            for c in related[:4]:
                stage_lists["expansion"].append(StageHit(chunk_id=c.id, rank=len(stage_lists["expansion"]) + 1, score=0, reason="Parent sibling or declared cross-reference context"))
        chosen = ranking[:max(1, request.limit - 2)]
        for hit in stage_lists["expansion"]:
            if len(chosen) >= request.limit:
                break
            if hit.chunk_id not in chosen:
                chosen.append(hit.chunk_id)
                scores.setdefault(hit.chunk_id, {})["rerank"] = 0
                paths.setdefault(hit.chunk_id, set()).add("expansion")
        for identity in ranking:
            if len(chosen) >= request.limit:
                break
            if identity not in chosen:
                chosen.append(identity)
        candidates = tuple(Candidate(chunk=self.chunks[identity], document=self.documents[self.chunks[identity].document_id],
            rank=rank, scores=scores[identity], paths=tuple(sorted(paths[identity]))) for rank, identity in enumerate(chosen, 1))
        stage_lists["fusion"] = [StageHit(chunk_id=i, rank=n, score=scores[i]["fusion"], reason="Reciprocal rank fusion, k=60") for n, i in enumerate(ranking[:30], 1)]
        stage_lists["rerank"] = [StageHit(chunk_id=i, rank=n, score=scores[i]["rerank"], reason="Fusion + explicit reference + bounded query overlap") for n, i in enumerate(ranking[:30], 1)]
        warnings = ["Retrieval quality has not been approved for this release."]
        if self.manifest["mode"] == "lexical":
            warnings.append("Lexical baseline only. Dense retrieval was explicitly disabled for this build.")
        if not candidates:
            warnings.append("No matching sources found. This is not legal clearance.")
        return RetrievalResult(request=request, context_fingerprint=request.fingerprint(), snapshot_id=self.snapshot.snapshot_id,
            rag_release_id=self.manifest["rag_release_id"], candidates=candidates,
            stages={key: tuple(hit.model_copy(update={"document_id": self.chunks[hit.chunk_id].document_id, "text": self.chunks[hit.chunk_id].text}) for hit in value) for key, value in stage_lists.items()}, elapsed_ms=int((time.monotonic() - start) * 1000), warnings=tuple(warnings))

    def close(self):
        if self.vector:
            self.vector.close()
        if self.owns_store:
            self.store.close()
