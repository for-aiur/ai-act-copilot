"""Explicit one-command setup. Embedding download is an announced setup operation."""
import os

from aiact.rag.benchmark import seed_fixtures
from aiact.rag.releases import build_release
from aiact.rag.store import Store
from aiact.settings import load_settings


def main():
    settings = load_settings()
    allow_download = os.environ.get("AIACT_DOWNLOAD_MODEL", "false").lower() == "true"
    cache_exists = settings.models_path.exists() and any(settings.models_path.rglob("*.onnx"))
    for domain in ("ai-act", "workbench-api"):
        manifest = build_release(settings, domain, download=allow_download and not cache_exists)
        store = Store(settings.database_url.get_secret_value())
        try:
            current = store.pointer(domain)
            if current != manifest["rag_release_id"]:
                store.activate(domain, manifest["rag_release_id"])
        finally:
            store.close()
        seed_fixtures(settings, domain, manifest["rag_release_id"])
        cache_exists = True
        print(f"{domain}: local tooling candidate ready; quality acceptance remains separate.", flush=True)


if __name__ == "__main__":
    main()
