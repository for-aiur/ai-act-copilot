"""Opt-in live local fixture evaluation; no stubs or external network fetches."""
import argparse
from pathlib import Path
import sys
from aiact.pipeline import scan
from aiact.providers import Ollama

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("recruitment/ranker.py", "annex-iii-4-a"),
    ("biometrics/identify.py", "annex-iii-1-a"),
    ("chatbot/assistant.py", "article-50-1"),
    ("negative_control/totals.py", None),
    ("ambiguous/score.py", "question"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--output-dir", type=Path, help="Explicitly save result JSON including source snippets here")
    args = parser.parse_args()
    provider = Ollama(args.model)
    failed = 0
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, expected in CASES:
        print(f"Reviewing {filename} locally…", flush=True)
        result = scan(ROOT / "examples" / filename, provider)
        citations = {c.section_id for f in result.findings for c in f.citations}
        has_question = any(f.context_question and f.context_question.endswith("?") for f in result.findings)
        text = " ".join(f.explanation + " " + (f.context_question or "") for f in result.findings)
        passed = result.status == "complete" and not result.errors and "GDPR" not in text
        if expected is None:
            passed &= not result.findings
        elif expected == "question":
            passed &= has_question
        else:
            passed &= expected in citations and has_question
        failed += not passed
        print(f"{'PASS' if passed else 'FAIL'} {filename}: {result.status}; {len(result.findings)} finding(s); {result.metadata.elapsed_ms} ms; citations={sorted(citations)}; errors={[e.code for e in result.errors]}", flush=True)
        if args.output_dir:
            (args.output_dir / (filename.split('/')[0] + '.json')).write_text(result.model_dump_json(indent=2) + "\n")
    print(f"{len(CASES)-failed}/{len(CASES)} fixture checks passed. Semantic support and question quality still require review.", flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
