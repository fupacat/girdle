"""Shared file-reading helpers for detectors. Never scrapes free-text content
into evidence — callers pass back file paths / matched markers only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib

from girdle.schema import CategoryResult, Tier


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_toml(path: Path) -> dict | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def scan_ci(root: Path, run_pattern: str, run_label: str) -> CategoryResult:
    """Shared CI-gating detection used by single-toolchain detectors.

    Mirrors the equivalent helpers in js_common.py / python_common.py.
    Globs .github/workflows/*.y*ml first, then falls back to
    .gitlab-ci.yml and azure-pipelines.yml.
    """
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            text = read_text(wf) or ""
            if re.search(run_pattern, text):
                return CategoryResult(
                    Tier.CONFIGURED,
                    evidence=[f".github/workflows/{wf.name}: runs {run_label}"],
                )
    for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
        p = root / f
        if p.exists() and re.search(run_pattern, read_text(p) or ""):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs {run_label}"])
    return CategoryResult(
        Tier.ABSENT,
        reason=f"no CI config found running {run_label}",
        recommendation=(
            f"Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs `{run_label}`."
        ),
    )
