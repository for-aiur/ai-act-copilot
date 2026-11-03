"""Explicit local RAG build and activation commands."""
import argparse
import json
import sys

from aiact.settings import load_settings
from .releases import build_release, verify_bundle
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aiact rag")
    parser.add_argument("action", choices=["build", "status", "activate", "rollback"])
    parser.add_argument("--domain", choices=["ai-act", "workbench-api"], default="ai-act")
    parser.add_argument("--release")
    parser.add_argument("--download-model", action="store_true", help="Explicit setup operation: download local embedding model")
    parser.add_argument("--lexical-only", action="store_true", help="Build a labelled lexical baseline, not a hybrid release")
    parser.add_argument("--allow-unapproved", action="store_true", help="Activate for local tooling tests without claiming quality acceptance")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        if args.action == "build":
            print(json.dumps(build_release(settings, args.domain, args.download_model, args.lexical_only)))
            return 0
        store = Store(settings.database_url.get_secret_value())
        try:
            if args.action == "status":
                identity = store.pointer(args.domain)
                print(json.dumps({"domain_id": args.domain, "active": identity, "previous": store.pointer(args.domain, "previous"),
                    "manifest": store.release(identity) if identity else None}))
                return 0
            identity = store.pointer(args.domain, "previous") if args.action == "rollback" else args.release
            if not identity:
                raise ValueError("Specify --release, or ensure a previous release exists for rollback.")
            manifest, snapshot, _ = verify_bundle(settings.data_dir / "releases" / identity)
            if manifest["quality_status"] != "approved" and not args.allow_unapproved:
                raise ValueError("Quality acceptance is pending. For local tooling only, use --allow-unapproved explicitly.")
            store.activate(args.domain, identity)
            print(json.dumps({"active": identity, "domain_id": args.domain, "quality_status": manifest["quality_status"]}))
            return 0
        finally:
            store.close()
    except Exception as exc:
        # No provider errors, URLs containing credentials or raw source in diagnostics.
        print(json.dumps({"status": "failed", "error": type(exc).__name__,
            "message": str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else "RAG operation failed. Check local dependencies, model cache and storage."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
