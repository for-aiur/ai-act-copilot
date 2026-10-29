"""Exercise launcher selection with a fake binary, never a real model server."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX helper; Windows uses the executable directly")


def project(tmp_path):
    root = tmp_path / "project with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ["start-local-model.sh", "loopback-only.sb"]:
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    return root


def binary(path, label):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\nprintf "%s\\n" "{label}" "$1" "$OLLAMA_HOST" "$OLLAMA_NO_CLOUD"\n')
    path.chmod(0o755)
    return path


def launch(root, *args, host="127.0.0.1:11434", search_path="/usr/bin:/bin"):
    env = dict(os.environ, PATH=search_path, OLLAMA_HOST=host)
    return subprocess.run(["/bin/sh", str(root / "scripts/start-local-model.sh"), *map(str, args)], env=env, capture_output=True, text=True, timeout=10)


def test_explicit_binary_and_custom_port(tmp_path):
    root = project(tmp_path)
    executable = binary(tmp_path / "local models" / "Ollama binary", "explicit")
    result = launch(root, executable, host="127.0.0.1:11435")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["explicit", "serve", "127.0.0.1:11435", "1"]


def test_system_binary_when_bundle_is_absent(tmp_path):
    root = project(tmp_path)
    executable = binary(tmp_path / "bin" / "ollama", "system")
    result = launch(root, search_path=f"{executable.parent}:/usr/bin:/bin")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == "system"


def test_local_bundle_precedes_system_default(tmp_path):
    root = project(tmp_path)
    binary(root / ".tools/ollama/ollama", "bundled")
    executable = binary(tmp_path / "bin" / "ollama", "system")
    result = launch(root, search_path=f"{executable.parent}:/usr/bin:/bin")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == "bundled"


def test_missing_binary_is_actionable(tmp_path):
    result = launch(project(tmp_path))
    assert result.returncode == 127 and "not on PATH" in result.stderr


@pytest.mark.parametrize("host", ["0.0.0.0:11434", "remote.example:11434"])
def test_nonlocal_bind_rejected_before_start(tmp_path, host):
    result = launch(project(tmp_path), host=host)
    assert result.returncode == 2 and "loopback" in result.stderr
