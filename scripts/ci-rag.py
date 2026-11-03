"""RAG CI: repeatable artifacts/metrics, and an intentionally failing gate fixture."""
import argparse
import json
import tempfile
import hashlib
from importlib.resources import files
from pathlib import Path

from aiact.rag.benchmark import benchmark, seed_fixtures
from aiact.rag.releases import build_release, verify_bundle
from aiact.settings import Settings
from aiact.rag.contracts import GoldenCase, GoldLabel, RetrievalRequest
from aiact.rag.retriever import HybridRetriever
from aiact.rag.evaluation import score_case, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force-failure", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reports = {}
    with tempfile.TemporaryDirectory(prefix="aiact-ci-rag-") as temporary:
        root = Path(temporary)
        settings = Settings(data_dir=root, database_url="sqlite:///" + str(root / "db.sqlite"))
        for domain in ["ai-act", "workbench-api"]:
            release = build_release(settings, domain, lexical_only=True)
            rebuilt = build_release(settings, domain, lexical_only=True)
            if release != rebuilt:
                raise ValueError("Identical RAG inputs did not reproduce the same manifest")
            verify_bundle(root / "releases" / release["rag_release_id"])
            seed_fixtures(settings, domain, release["rag_release_id"])
            reports[domain] = benchmark(settings, domain, release["rag_release_id"])
            if args.force_failure and domain == "workbench-api":
                retriever = HybridRetriever(settings, release["rag_release_id"])
                query = RetrievalRequest(domain_id=domain, scenario="/api/health readiness", limit=1)
                case = GoldenCase(id="deliberate-critical-miss", title="Intentional failing fixture", request=query,
                    snapshot_id=retriever.snapshot.snapshot_id, rag_release_id=release["rag_release_id"], author="CI gate fixture",
                    labels=(GoldLabel(document_id="health", label="must_retrieve", rationale="Expected endpoint"),
                            GoldLabel(document_id="drafts", label="must_retrieve", rationale="Deliberate known false negative")))
                score = score_case(case, retriever.search(query))
                retriever.close()
                reports[domain]["scores"].append(score)
                reports[domain]["summary"] = summarize(reports[domain]["scores"])
    baseline = json.loads(files("aiact").joinpath("data/evaluation/technical-baseline.json").read_text())
    raw_fixture = files("aiact").joinpath("data/evaluation/technical.json").read_bytes()
    if hashlib.sha256(raw_fixture).hexdigest() != baseline["fixture_sha256"]:
        raise ValueError("Engineering fixtures changed without a reviewed baseline revision")
    technical = reports[baseline["domain_id"]]
    technical["baseline_comparison"] = {"scope": baseline["scope"], "deltas": {
        key: technical["summary"][key] - value for key, value in baseline["summary"].items()}}
    regression = any(technical["summary"][key] < baseline["summary"][key] for key in ("recall", "mean_precision", "mean_mrr", "mean_ndcg"))
    (args.output / "metrics.json").write_text(json.dumps(reports, indent=2) + "\n")
    lines = ["# Retrieval baseline", "", "AI Act cases are model-authored drafts. Final expert-gold acceptance is blocked.", "",
        "| Domain | Cases | Recall | Missing | Approved |", "| --- | ---: | ---: | ---: | ---: |"]
    for domain, report in reports.items():
        summary = report["summary"]
        lines.append(f"| {domain} | {summary['cases']} | {summary['recall']} | {summary['missing_required']} | {report['approved_count']} |")
    lines += ["", "Technical baseline deltas:", "", "```json", json.dumps(reports["workbench-api"]["baseline_comparison"], indent=2), "```"]
    (args.output / "metrics.md").write_text("\n".join(lines) + "\n")
    technical = reports["workbench-api"]["summary"]
    if regression or technical["recall"] != 1 or technical["missing_required"]:
        if args.force_failure:
            return 3
        raise ValueError("Technical approved retrieval fixture regressed")
    if args.force_failure:
        raise ValueError("The intentionally failing fixture unexpectedly passed")
    if reports["ai-act"]["quality_gate"]["status"] != "blocked":
        raise ValueError("Unreviewed model-authored legal drafts must not pass the final quality gate")
    print(json.dumps({"status": "tooling_checks_passed", "legal_quality_gate": "blocked", "reports": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
