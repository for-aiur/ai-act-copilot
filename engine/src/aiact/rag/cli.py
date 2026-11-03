"""Explicit local RAG build and activation commands."""
import argparse
import json
import sys

from aiact.settings import load_settings
from .releases import build_release, verify_bundle
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aiact rag")
    parser.add_argument("action", choices=["build", "status", "activate", "rollback", "seed-drafts", "eval"])
    parser.add_argument("--domain", choices=["ai-act", "workbench-api"], default="ai-act")
    parser.add_argument("--release")
    parser.add_argument("--download-model", action="store_true", help="Explicit setup operation: download local embedding model")
    parser.add_argument("--lexical-only", action="store_true", help="Build a labelled lexical baseline, not a hybrid release")
    parser.add_argument("--allow-unapproved", action="store_true", help="Activate for local tooling tests without claiming quality acceptance")
    parser.add_argument("--dataset", help="Explicit versioned GoldenCase JSON bundle")
    parser.add_argument("--output", help="Write a versioned evaluation JSON report")
    parser.add_argument("--include-holdout", action="store_true", help="Explicit release evaluation only; do not tune on held-out cases")
    parser.add_argument("--require-quality", action="store_true", help="Fail unless the final M1 expert-gold policy passes")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        if args.action in {"seed-drafts", "eval"}:
            store = Store(settings.database_url.get_secret_value())
            identity = args.release or store.pointer(args.domain)
            store.close()
            if not identity:
                raise ValueError("An explicit or active release is required.")
            from .benchmark import seed_fixtures, benchmark
            report = seed_fixtures(settings, args.domain, identity) if args.action == "seed-drafts" else benchmark(settings, args.domain, identity, args.dataset, args.include_holdout)
            if args.output:
                from pathlib import Path
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report))
            return 1 if args.require_quality and report.get("quality_gate", {}).get("status") != "pass" else 0
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
