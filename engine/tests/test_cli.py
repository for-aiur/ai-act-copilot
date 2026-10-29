import subprocess
import sys
import pytest
from aiact.contracts import ScanResult


@pytest.mark.parametrize("arguments,code", [(["scan", "--json"], 2), (["scan", "missing.py", "--json", "--endpoint", "https://remote.test"], 2), (["scan", "missing.py", "--json"], 1), (["scan", "missing.py", "--json", "--max-files", "0"], 2)])
def test_json_error_boundary(arguments, code):
    process = subprocess.run([sys.executable, "-m", "aiact.cli", *arguments], capture_output=True, text=True)
    assert process.returncode == code
    assert ScanResult.model_validate_json(process.stdout).status == "failed"
