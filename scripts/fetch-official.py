"""Explicitly redownload the pinned official source pack, without activation."""
import argparse
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen

from aiact.rag.official import checksum, import_official

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True, help="New empty staging directory")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
manifest = Path(__file__).resolve().parents[1] / "engine/src/aiact/data/official/sources.json"
sources = json.loads(manifest.read_text())
for source in sources:
    request = Request(source["url"], headers={"Accept": "application/xhtml+xml", "Accept-Language": "en", "User-Agent": "AIActCopilot/official-corpus-import"})
    with urlopen(request, timeout=30) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000 or checksum(raw) != source["sha256"]:
        raise SystemExit("Official source differs from pinned manifest. Staging only, manual review required.")
    (args.output / source["file"]).write_bytes(gzip.compress(raw, mtime=0))
(args.output / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
snapshot = import_official(args.output)
print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "coverage": snapshot["coverage"]}))
