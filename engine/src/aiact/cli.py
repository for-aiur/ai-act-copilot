"""Portable CLI boundary. JSON mode always emits one structured document."""
import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .context import Budgets
from .contracts import ScanError, ScanResult
from .corpus import default_cache, update_corpus
from .pipeline import scan
from .providers import create_provider, default_model, ReviewFailure
from .doctor import HealthResult, inspect_setup


class UsageError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def parser():
    result = Parser(prog="aiact", description="AI Act engineering review; choose local Ollama or opt-in Gemini")
    result.add_argument("--version", action="version", version=__version__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("rag", help="Build, inspect and activate versioned full-corpus RAG artifacts")
    review = sub.add_parser("scan", help="Review explicitly selected Python input")
    review.add_argument("path", type=Path)
    review.add_argument("--json", action="store_true")
    review.add_argument("--rag-release", help="Explicit full-corpus RAG release ID (requires rag extra)")
    review.add_argument("--cloud-consent", action="store_true", help="Allow full-corpus review to send selected source/context to Gemini")
    review.add_argument("--context", default="", help="Explicit purpose/deployment facts; no automatic README ingestion")
    review.add_argument("--max-files", type=int, default=10)
    review.add_argument("--max-source-bytes", type=int, default=24_000)
    review.add_argument("--timeout", type=float, default=60, help="Seconds per inference request (max 60)")
    review.add_argument("--deadline", type=float, default=120, help="Total scan deadline in seconds")
    doctor = sub.add_parser("doctor", help="Check setup without installing or downloading")
    doctor.add_argument("--json", action="store_true", help="Structured, read-only health checks for editor integrations")
    update = sub.add_parser("update", help="Explicitly verify official subset and atomically refresh local cache")
    for command in [review, doctor]:
        command.add_argument("--provider", choices=["ollama", "gemini"], default=os.environ.get("AIACT_PROVIDER", "ollama"), help="Gemini sends selected code/context to Google; requires GEMINI_API_KEY")
        command.add_argument("--model", default=os.environ.get("AIACT_MODEL"), help="Model ID; defaults depend on the selected provider")
        command.add_argument("--endpoint", default=os.environ.get("AIACT_OLLAMA_URL", "http://127.0.0.1:11434"))
    for command in [review, doctor, update]:
        command.add_argument("--corpus", type=Path, default=os.environ.get("AIACT_CORPUS"), help="Explicit cache path; defaults to verified user cache or bundled subset")
    return result


def present(result: ScanResult, json_mode: bool):
    if json_mode:
        print(result.model_dump_json())
        return
    print(f"Review {result.status}: {len(result.findings)} finding(s), {len(result.coverage.scanned_files)} Python file(s)")
    print("Engineering review only; zero findings does not certify compliance.")
    for finding in result.findings:
        ev = finding.evidence
        print(f"\n{'Needs context' if finding.kind == 'context_question' else 'Potential concern'} [{finding.priority}]: {finding.title}")
        print(f"  {ev.path}:{ev.start_line}-{ev.end_line}\n  {finding.explanation}")
        for citation in finding.citations:
            print(f"  {citation.section_id}: {citation.quote}\n  {citation.url}")
        print(f"  Next: {finding.suggested_next_action}")
        if finding.context_question:
            print(f"  Question: {finding.context_question}")
    for skipped in result.coverage.skipped_files:
        print(f"Skipped {skipped.path}: {skipped.reason}")
    for error in result.errors:
        print(f"{error.code}: {error.message}", file=sys.stderr)
    print(f"\nModel: {result.metadata.model_id}; corpus: {result.metadata.corpus_version}; {result.metadata.elapsed_ms} ms")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "rag":
        from .rag.cli import main as rag_main
        return rag_main(argv[1:])
    json_mode = bool(argv and argv[0] in {"scan", "doctor"} and "--json" in argv)
    doctor_mode = bool(argv and argv[0] == "doctor")

    def emit_error(code, message):
        if json_mode:
            error = ScanError(code=code, message=message)
            if doctor_mode:
                print(HealthResult(errors=[error]).model_dump_json())
            else:
                present(ScanResult(status="failed", errors=[error]), True)
    try:
        args = parser().parse_args(argv)
        if args.command == "update":
            data = update_corpus(args.corpus or default_cache())
            print(f"Verified {len(data['sections'])} reviewed official passages; saved {args.corpus or default_cache()}.")
            print("Refresh verifies the reviewed subset; changed/new law requires manual corpus review.")
            return 0
        model = args.model or default_model(args.provider)
        if args.command == "doctor":
            health = inspect_setup(model, args.endpoint, args.corpus, args.provider)
            if args.json:
                print(health.model_dump_json())
            else:
                for check in health.checks:
                    print(f"{check.id}: {check.status} · {check.detail}")
            return 2 if any(e.code == "configuration" for e in health.errors) else 0 if health.status == "ready" else 1
        budgets = Budgets(files=args.max_files, source_bytes=args.max_source_bytes,
                          request_seconds=min(args.timeout, 60), total_seconds=args.deadline)
        if args.rag_release:
            from .settings import load_settings
            from .rag.retriever import HybridRetriever
            from .rag.review import review_python
            settings = load_settings({"provider": args.provider, "model": model})
            settings.require_cloud(args.cloud_consent or ("--provider" in argv and args.provider == "gemini"))
            if args.provider == "gemini":
                from .gemini import Gemini
                provider = Gemini(model, api_key=settings.gemini_api_key.get_secret_value())
            else:
                provider = create_provider(args.provider, model, args.endpoint)
            retriever = HybridRetriever(settings, args.rag_release)
            try:
                result = ScanResult.model_validate(review_python(args.path, provider, retriever, args.context, budgets)["scan_result"])
            finally:
                retriever.close()
        else:
            provider = create_provider(args.provider, model, args.endpoint)
            result = scan(args.path, provider, args.corpus, args.context, budgets)
        present(result, args.json)
        return 2 if any(e.code == "configuration" for e in result.errors) else 0 if result.status == "complete" else 1
    except (UsageError, ValueError) as exc:
        emit_error("configuration", str(exc))
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except ReviewFailure as exc:
        emit_error(exc.code, str(exc))
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2 if exc.code == "configuration" else 1
    except Exception:
        emit_error("internal_error", "Unexpected engine error; review unavailable.")
        print("Unexpected engine error; review unavailable.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
