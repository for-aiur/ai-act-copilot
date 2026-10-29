from pathlib import Path
import subprocess
from aiact.context import Budgets, collect
import pytest


def test_privacy_ranges_and_coverage(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored.py\n")
    (tmp_path / "ignored.py").write_text("SECRET = True")
    (tmp_path / ".secret.py").write_text("SECRET = True")
    (tmp_path / "good.py").write_text("def f():\n    return 1\n")
    (tmp_path / "bad.py").write_text("def broken(")
    (tmp_path / "escape.py").symlink_to(Path(__file__).resolve())
    result = collect(tmp_path)
    assert [s.path for s in result.sources] == ["good.py"]
    assert result.sources[0].ranges == [(1, 2)]
    assert len(result.coverage.skipped_files) >= 4
    assert result.errors[0].code == "parse_error"


def test_bounds_and_unsupported(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n")
    (tmp_path / "b.py").write_text("x=2\n")
    result = collect(tmp_path, budgets=Budgets(files=1))
    assert len(result.sources) == 1 and result.coverage.truncated
    result = collect(tmp_path, budgets=Budgets(source_bytes=2))
    assert not result.sources and result.coverage.truncated
    (tmp_path / "x.js").write_text("console.log('x')")
    assert collect(tmp_path / "x.js").errors[0].code == "unsupported_input"


def test_fingerprint_changes_with_context(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n")
    assert collect(tmp_path).fingerprint != collect(tmp_path, "purpose unknown").fingerprint


@pytest.mark.parametrize("deadline", [0, -1, float("nan"), float("inf")])
def test_invalid_budgets(deadline):
    with pytest.raises(ValueError):
        Budgets(total_seconds=deadline)
