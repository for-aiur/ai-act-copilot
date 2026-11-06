"""Explicit one-command setup. Embedding download is an announced setup operation."""
import os

from aiact.rag.benchmark import seed_fixtures
from aiact.rag.domains import load_snapshot
from aiact.rag.releases import build_release
from aiact.rag.store import Store
from aiact.settings import load_settings


def main():
    settings = load_settings()
    allow_download = os.environ.get("AIACT_DOWNLOAD_MODEL", "false").lower() == "true"
    cache_exists = settings.models_path.exists() and any(settings.models_path.rglob("*.onnx"))
    for domain in ("ai-act", "workbench-api"):
        print(f"{domain}: building local source and embedding indexes. This may take several minutes.", flush=True)
        passage_count = None

        def indexing_progress(done, _batch_count):
            nonlocal passage_count
            # FastEmbed emits one result per passage. Use the source snapshot's
            # passage count as the denominator for the startup log.
            if passage_count is None:
                passage_count = len(load_snapshot(domain).chunks)
            if done == 1 or done % 50 == 0 or done == passage_count:
                print(f"{domain}: embedded {done}/{passage_count} passages.", flush=True)

        manifest = build_release(settings, domain, download=allow_download and not cache_exists,
            progress=indexing_progress)
        store = Store(settings.database_url.get_secret_value())
        try:
            current = store.pointer(domain)
            if current is None:
                store.activate(domain, manifest["rag_release_id"])
            elif current != manifest["rag_release_id"]:
                print(f"{domain}: new candidate staged. Existing active release preserved; activate explicitly in Versions.", flush=True)
        finally:
            store.close()
        seed_fixtures(settings, domain, manifest["rag_release_id"])
        cache_exists = True
        print(f"{domain}: local tooling candidate ready; quality acceptance remains separate.", flush=True)
    print("Setup complete. Open the dashboard at http://127.0.0.1:8000 when its container is healthy.", flush=True)


if __name__ == "__main__":
    main()
