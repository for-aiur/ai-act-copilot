import json
import subprocess
from pathlib import Path

import jsonschema
from aiact.contracts import ScanResult

ROOT = Path(__file__).resolve().parents[2]


def test_export_and_example():
    schema = json.loads((ROOT / "schemas/scan-result.schema.json").read_text())
    assert schema == ScanResult.model_json_schema()
    for name in ["example-result.json", "example-complete-result.json"]:
        example = json.loads((ROOT / "schemas" / name).read_text())
        jsonschema.validate(example, schema)
        ScanResult.model_validate(example)


def test_failed_cli_is_single_json():
    import sys
    process = subprocess.run([sys.executable, "-m", "aiact.cli", "scan", "missing.py", "--json"], capture_output=True, text=True)
    assert process.returncode == 1
    assert ScanResult.model_validate_json(process.stdout).status == "failed"
