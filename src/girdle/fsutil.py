"""Shared filesystem-walking helpers: exclude vendor/build directories
consistently across detectors and the structural indexer, so neither
mistakes a dependency's own test files (e.g. inside .venv/site-packages,
node_modules, vendor/) for the scanned repo's own test suite.
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "bin", "obj", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "vendor", ".idea", ".vscode", ".egg-info",
}


def walk_excluding(root: Path) -> Iterator[tuple[str, list[str], list[str]]]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
        yield dirpath, dirnames, filenames


def rglob_excluding(root: Path, *patterns: str) -> Iterator[Path]:
    """Like Path.rglob, but pruning vendor/build directories first. Accepts
    one or more fnmatch-style patterns (e.g. "test_*.py", "*_test.py").
    """
    for dirpath, _dirnames, filenames in walk_excluding(root):
        for name in filenames:
            if any(fnmatch.fnmatch(name, p) for p in patterns):
                yield Path(dirpath) / name
