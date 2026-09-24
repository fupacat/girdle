"""Shared scan logic for Python toolchains (pip, Poetry, uv, Pipenv, Conda).
Tests/lint/CI detection is toolchain-agnostic; only reproducibility differs
per toolchain's lock mechanism.
"""

from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text, read_toml
from girdle.fsutil import rglob_excluding
from girdle.schema import CategoryResult, Tier

LINT_CONFIG_MARKERS = (".flake8", "ruff.toml", ".ruff.toml", "mypy.ini", "setup.cfg")


def scan_tests(root: Path) -> CategoryResult:
    evidence = []
    for marker in ("pytest.ini", "tox.ini"):
        if (root / marker).exists():
            evidence.append(marker)
    pyproject = read_toml(root / "pyproject.toml")
    if pyproject and "pytest" in pyproject.get("tool", {}):
        evidence.append("pyproject.toml#tool.pytest")
    if any(rglob_excluding(root, "test_*.py", "*_test.py")):
        evidence.append("test_*.py files present")
    if not evidence:
        return CategoryResult(
            Tier.ABSENT, reason="no pytest/tox config or test_*.py files found",
            recommendation=(
                "Add tests under a tests/ directory (`pip install pytest`, create "
                "test_*.py files)."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=evidence)


def scan_lint(root: Path) -> CategoryResult:
    evidence = [m for m in LINT_CONFIG_MARKERS if (root / m).exists()]
    pyproject = read_toml(root / "pyproject.toml")
    if pyproject:
        tools = pyproject.get("tool", {})
        for name in ("ruff", "mypy", "black", "flake8"):
            if name in tools:
                evidence.append(f"pyproject.toml#tool.{name}")
    if not evidence:
        return CategoryResult(
            Tier.ABSENT, reason="no ruff/mypy/flake8 config found",
            recommendation=(
                "Add a ruff config: `pip install ruff` and add a [tool.ruff] section to "
                "pyproject.toml, or run `ruff check --fix .`."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=evidence)


def scan_ci(root: Path) -> CategoryResult:
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            text = read_text(wf) or ""
            if re.search(r"\bpytest\b", text) or re.search(r"python\s+-m\s+pytest", text):
                return CategoryResult(
                    Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs pytest"]
                )
    for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
        p = root / f
        if p.exists() and re.search(r"\bpytest\b", read_text(p) or ""):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs pytest"])
    return CategoryResult(
        Tier.ABSENT, reason="no CI config found running pytest",
        recommendation=(
            "Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs `pytest`."
        ),
    )


def is_lockfile_gitignored(root: Path, lockfile_name: str) -> bool:
    gitignore = read_text(root / ".gitignore") or ""
    return bool(re.search(rf"^{re.escape(lockfile_name)}$", gitignore, re.MULTILINE))


def lint_command(root: Path) -> list[str] | None:
    """Pick a --run lint command matching whichever tool's config was found.
    Preference order matches nothing in particular except common adoption.
    """
    pyproject = read_toml(root / "pyproject.toml")
    tools = pyproject.get("tool", {}) if pyproject else {}
    if "ruff" in tools or (root / "ruff.toml").exists() or (root / ".ruff.toml").exists():
        return ["ruff", "check", "."]
    if "mypy" in tools or (root / "mypy.ini").exists():
        return ["mypy", "."]
    if (root / ".flake8").exists() or "flake8" in tools:
        return ["flake8"]
    return None


def test_command() -> list[str]:
    return ["pytest", "-q"]
