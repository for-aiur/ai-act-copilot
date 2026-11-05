"""Explicit setup downloads; query-time embedding is local and cache-only."""
import importlib.metadata
import math
from pathlib import Path
from typing import Protocol

from .official import checksum


class Embedder(Protocol):
    manifest: dict
    def passages(self, texts: list[str]) -> list[list[float]]: ...
    def query(self, text: str) -> list[float]: ...


class LocalEmbedder:
    def __init__(self, model: str, cache_dir: Path, download: bool = False):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name=model, cache_dir=str(cache_dir), threads=2,
            local_files_only=not download, providers=["CPUExecutionProvider"])
        model_dir = Path(self.model.model._model_dir)
        # Hash actual inference files, not mutable repository aliases or cache locks.
        files = {str(p.relative_to(model_dir)): checksum(p.read_bytes()) for p in sorted(model_dir.rglob("*")) if p.is_file() and ".cache" not in p.parts and not p.name.startswith(".")}
        self.manifest = {"provider": "fastembed-local", "model": model, "revision": checksum(files),
                         "files": files, "dimension": self.model.model.model_description.dim, "normalization": "l2",
                         "source_revision": model_dir.name,
                         "runtime": importlib.metadata.version("fastembed"), "max_input_tokens": 512,
                         "onnxruntime": importlib.metadata.version("onnxruntime"), "numpy": importlib.metadata.version("numpy"),
                         "privacy": "CPU only; query/source text is never sent to an embedding service"}

    def passages(self, texts):
        return [vector.tolist() for vector in self.model.passage_embed(texts, batch_size=32)]

    def passages_with_progress(self, texts, progress):
        total = max(1, math.ceil(len(texts) / 32))
        vectors = []
        for batch, vector in enumerate(self.model.passage_embed(texts, batch_size=32), 1):
            vectors.append(vector.tolist())
            progress(batch, total)
        return vectors

    def query(self, text):
        return list(self.model.query_embed([text]))[0].tolist()
