"""Bounded explicit Python source collection. Never executes the reviewed code."""
import ast
import hashlib
import json
import math
import os
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import Coverage, ScanError, SkippedFile

EXCLUDED = {"node_modules", "vendor", "build", "dist", "__pycache__", "site-packages", "venv", "env"}


@dataclass(frozen=True)
class Budgets:
    files: int = 10
    file_bytes: int = 100_000
    source_bytes: int = 24_000
    passages: int = 6
    legal_bytes: int = 12_000
    request_seconds: float = 60
    total_seconds: float = 120

    def __post_init__(self):
        values = (self.files, self.file_bytes, self.source_bytes, self.passages, self.legal_bytes, self.request_seconds, self.total_seconds)
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("All budgets must be positive")


@dataclass
class Source:
    path: str
    text: str
    ranges: list[tuple[int, int]]
    potential_model_calls: list[str] = field(default_factory=list)

    def numbered(self):
        return {"path": self.path, "lines": [{"line": i, "text": line} for i, line in enumerate(self.text.splitlines(), 1)], "ast_ranges": self.ranges, "potential_model_calls": self.potential_model_calls}


@dataclass
class Context:
    root: Path
    sources: list[Source] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    errors: list[ScanError] = field(default_factory=list)
    fingerprint: str = ""


def repository_root(path: Path) -> Path:
    directory = path if path.is_dir() else path.parent
    try:
        run = subprocess.run(["git", "-C", str(directory), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=2)
        if run.returncode == 0:
            return Path(run.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return directory.resolve()


def collect(path: Path, explicit_context: str = "", budgets: Budgets = Budgets()) -> Context:
    path = path.absolute()
    root = repository_root(path)
    context = Context(root=root)
    base = path if path.is_dir() and not path.is_symlink() else path.parent
    base = base.resolve()

    def relative(item):
        try:
            return item.relative_to(root).as_posix()
        except ValueError:
            return item.name

    def skip(item, reason, truncated=False):
        context.coverage.skipped_files.append(SkippedFile(path=relative(item), reason=reason))
        context.coverage.truncated |= truncated

    if not path.exists():
        context.errors.append(ScanError(code="input_missing", message="Input path does not exist.", path=relative(path)))
        return context
    candidates = []
    if path.is_dir() and not path.is_symlink():
        visited = 0
        for directory, dirs, names in os.walk(path, followlinks=False):
            dirs.sort()
            names.sort()
            for name in list(dirs):
                item = Path(directory) / name
                if name.startswith(".") or name in EXCLUDED or item.is_symlink():
                    skip(item, "excluded directory or symlink")
                    dirs.remove(name)
            for name in names:
                visited += 1
                if visited > 1000:
                    skip(path, "enumeration budget exceeded", True)
                    break
                item = Path(directory) / name
                if item.suffix == ".py":
                    candidates.append(item)
            if visited > 1000:
                break
    else:
        candidates = [path]
    used = len(explicit_context.encode())
    if used > budgets.source_bytes:
        context.errors.append(ScanError(code="context_budget", message="Explicit context exceeds total source/context budget."))
        context.coverage.truncated = True
        return context
    for item in candidates:
        rel = relative(item)
        if any(p.startswith(".") or p in EXCLUDED for p in Path(rel).parts) or item.suffix != ".py":
            skip(item, "not in visible Python source allowlist")
            continue
        if item.is_symlink():
            skip(item, "symlink source is excluded")
            continue
        if not item.resolve().is_relative_to(base):
            skip(item, "path escapes scan root")
            continue
        try:
            ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "--", rel], capture_output=True, timeout=2)
            if ignored.returncode == 0:
                skip(item, "gitignored")
                continue
        except (OSError, subprocess.TimeoutExpired):
            skip(item, "could not verify gitignore")
            continue
        if len(context.sources) >= budgets.files:
            skip(item, "file count budget", True)
            continue
        try:
            if item.stat().st_size > budgets.file_bytes:
                skip(item, "per-file byte budget", True)
                continue
            # O_NOFOLLOW protects against a symlink swap between inspection and read.
            fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    skip(item, "non-regular file")
                    continue
                raw = stream.read(budgets.file_bytes + 1)
            if len(raw) > budgets.file_bytes or len(raw) + used > budgets.source_bytes:
                skip(item, "source byte budget", True)
                continue
            if b"\0" in raw:
                skip(item, "binary input")
                continue
            text = raw.decode("utf-8")
            tree = ast.parse(text)
            ranges = [(node.lineno, node.end_lineno) for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            calls = []
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.attr in {"predict", "predict_proba", "generate", "encode", "invoke"}
                        and ("model" in node.func.value.id.lower() or node.func.value.id.lower() in {"llm", "classifier", "pipeline"})):
                    calls.append(ast.get_source_segment(text, node) or node.func.attr)
            context.sources.append(Source(rel, text, ranges or [(1, max(1, len(text.splitlines())))], calls))
            context.coverage.scanned_files.append(rel)
            used += len(raw)
        except (SyntaxError, UnicodeDecodeError):
            skip(item, "invalid Python or UTF-8")
            context.errors.append(ScanError(code="parse_error", message="Python source could not be parsed.", path=rel))
        except OSError:
            skip(item, "unreadable or changed source")
            context.errors.append(ScanError(code="read_error", message="Source could not be read safely.", path=rel))
    if not context.sources and not context.errors:
        context.errors.append(ScanError(code="unsupported_input", message="No allowed Python files were available for review."))
    context.fingerprint = hashlib.sha256(json.dumps({"sources": [(s.path, s.text) for s in context.sources], "context": explicit_context}, sort_keys=True).encode()).hexdigest()
    return context
