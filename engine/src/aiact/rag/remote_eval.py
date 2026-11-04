"""Run evaluation through the single owning runtime, never open Qdrant twice."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


def main():
    endpoint = os.environ.get("AIACT_API_URL", "http://127.0.0.1:8000")
    url = urlsplit(endpoint)
    if url.scheme != "http" or url.hostname not in {"rag", "localhost", "127.0.0.1"} or url.username or url.password:
        raise ValueError("Evaluation endpoint must be the local workbench.")
    domain = os.environ.get("AIACT_EVAL_DOMAIN", "ai-act")
    request = Request(endpoint + "/api/rag/evaluate?" + urlencode({"domain": domain}),
        data=b"", headers={"Host": "localhost", "Content-Type": "application/json"})
    with urlopen(request, timeout=300) as response:
        report = json.loads(response.read(4_000_000))
    output = Path("/reports/evaluation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if domain == "workbench-api":
        if report["summary"]["cases"] < 2 or report["summary"]["recall"] != 1 or report["summary"]["missing_required"]:
            raise ValueError("Packaged runtime failed its approved engineering retrieval smoke fixtures")


if __name__ == "__main__":
    main()
