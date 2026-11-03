"""Protected release acceptance. Missing expert gold or live credentials fails closed."""
import json
import os
from pathlib import Path

from aiact.gemini import Gemini
from aiact.rag.benchmark import benchmark
from aiact.rag.releases import build_release
from aiact.rag.retriever import HybridRetriever
from aiact.rag.review import review_python
from aiact.settings import load_settings


def main():
    output = Path(".aiact-results/release")
    output.mkdir(parents=True, exist_ok=True)
    gold = Path("evaluation/gold/ai-act.json")
    blockers = []
    if not gold.is_file():
        blockers.append("Versioned expert-approved AI Act gold has not been published in evaluation/gold/ai-act.json.")
    if not os.environ.get("GEMINI_API_KEY"):
        blockers.append("Protected Gemini CI credentials are missing.")
    if blockers:
        (output / "acceptance.json").write_text(json.dumps({"status": "blocked", "reasons": blockers}, indent=2) + "\n")
        print("Release blocked: expert-gold or protected live-model prerequisites are missing.")
        return 1
    settings = load_settings()
    settings.require_cloud()
    manifest = build_release(settings, download=True)
    rebuilt = build_release(settings)
    if manifest != rebuilt:
        raise ValueError("Release artifact is not reproducible")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report = benchmark(settings, "ai-act", manifest["rag_release_id"], gold, include_holdout=True)
    (output / "retrieval.json").write_text(json.dumps(report, indent=2) + "\n")
    if report["quality_gate"]["status"] != "pass":
        print("Release blocked by the expert-gold retrieval policy.")
        return 1
    retriever = HybridRetriever(settings, manifest["rag_release_id"])
    scenarios = [
        ("credit", "Assess a consumer credit score; confirm actor role and intended deployment.", "predict"),
        ("education", "Assist an educational institution with student admission decisions.", "predict"),
        ("medical", "Support clinical triage; safety role and deployment are unknown.", "predict"),
        ("infrastructure", "Support safety decisions in electricity infrastructure.", "predict"),
        ("workplace", "Infer employee emotions from video; purpose and exceptions need context.", "predict"),
        ("general-purpose", "Distribute a general-purpose model with technical documentation.", "generate"),
        ("negative", "Ordinary arithmetic, with no AI use.", None),
    ]
    results = []
    try:
        for name, context, method in scenarios:
            source = output / (name + ".py")
            source.write_text(f"def run(model, record):\n    return model.{method}(record)\n" if method else "def add(a, b):\n    return a + b\n")
            payload = review_python(source, Gemini(settings.model, settings.gemini_api_key.get_secret_value()), retriever, context)
            result = payload["scan_result"]
            results.append({"case": name, **payload})
            if result["status"] != "complete" or (method is None and result["findings"]) or (method and not result["findings"]):
                (output / "live.json").write_text(json.dumps(results, indent=2) + "\n")
                print("Release blocked by a live synthetic review failure.")
                return 1
    finally:
        retriever.close()
    (output / "live.json").write_text(json.dumps(results, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Retrieval gate and synthetic live review checks passed. Semantic expert review remains recorded separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
