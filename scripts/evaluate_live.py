"""Opt-in live fixture evaluation with the explicitly selected provider; no stubs."""
import argparse
from pathlib import Path
import sys
from aiact.pipeline import scan
from aiact.providers import create_provider, default_model

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("recruitment/ranker.py", "annex-iii-4-a"),
    ("biometrics/identify.py", "annex-iii-1-a"),
    ("chatbot/assistant.py", "article-50-1"),
    ("negative_control/totals.py", None),
    ("ambiguous/score.py", "question"),
    ("recruitment/training_review.py", "multi"),
    ("recruitment/bias_audit.py", "article-4a-1"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["ollama", "gemini"], default="ollama", help="Gemini sends selected examples to Google using GEMINI_API_KEY")
    parser.add_argument("--model")
    parser.add_argument("--case", choices=[name for name,_ in CASES], help="Run one fixture instead of all seven")
    parser.add_argument("--output-dir", type=Path, help="Explicitly save result JSON including source snippets here")
    args = parser.parse_args()
    provider = create_provider(args.provider, args.model or default_model(args.provider), "http://127.0.0.1:11434")
    failed = 0
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    cases=[case for case in CASES if not args.case or case[0]==args.case]
    for filename, expected in cases:
        print(f"Reviewing {filename} with {args.provider}…", flush=True)
        result = scan(ROOT / "examples" / filename, provider)
        citations = {c.section_id for f in result.findings for c in f.citations}
        has_question = any(f.context_question and f.context_question.endswith("?") for f in result.findings)
        text = " ".join(f.explanation + " " + (f.context_question or "") for f in result.findings)
        passed = result.status == "complete" and not result.errors and "GDPR" not in text
        if expected is None:
            passed &= not result.findings
        elif expected == "multi":
            passed &= len(result.findings)>=3 and len(citations)>=3 and bool(citations & {"article-10-2","article-10-3","annex-iv-2-b","annex-iv-2-d"}) and has_question
        elif expected == "question":
            passed &= has_question
        else:
            passed &= expected in citations and has_question
        failed += not passed
        print(f"{'PASS' if passed else 'FAIL'} {filename}: {result.status}; {len(result.findings)} finding(s); {result.metadata.elapsed_ms} ms; citations={sorted(citations)}; errors={[e.code for e in result.errors]}", flush=True)
        if args.output_dir:
            (args.output_dir / (filename.replace('/', '_') + '.json')).write_text(result.model_dump_json(indent=2) + "\n")
    print(f"{len(cases)-failed}/{len(cases)} fixture checks passed. Semantic support and question quality still require review.", flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
