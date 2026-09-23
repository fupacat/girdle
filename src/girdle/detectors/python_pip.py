"""Python detector covering plain pip/requirements.txt and Poetry, since both
key off similar markers (pyproject.toml presence/absence) and share most
scan logic. uv/Conda/Pipenv are separate detectors, added later against the
same base.Fingerprint contract.
"""

from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text, read_toml
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

LINT_CONFIG_MARKERS = (".flake8", "ruff.toml", ".ruff.toml", "mypy.ini", "setup.cfg")


class PythonPipDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        pyproject = root / "pyproject.toml"
        requirements = root / "requirements.txt"
        setup_py = root / "setup.py"
        data = read_toml(pyproject) if pyproject.exists() else None

        if data is not None and "poetry" in data.get("tool", {}):
            return Fingerprint(
                id="python-poetry", language="python", toolchain="poetry", root=root, variants=[]
            )
        if data is not None and "uv" in data.get("tool", {}) and (root / "uv.lock").exists():
            return None  # let a future uv detector claim this
        if not requirements.exists() and not setup_py.exists() and data is None:
            return None
        return Fingerprint(
            id="python-pip", language="python", toolchain="pip", root=root, variants=[]
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        return {
            "tests": self._scan_tests(root),
            "lint": self._scan_lint(root),
            "reproducibility": self._scan_reproducibility(root, fp),
            "ci_gating": self._scan_ci(root),
        }

    def _scan_tests(self, root: Path) -> CategoryResult:
        evidence = []
        for marker in ("pytest.ini", "tox.ini"):
            if (root / marker).exists():
                evidence.append(marker)
        pyproject = read_toml(root / "pyproject.toml")
        if pyproject and "pytest" in pyproject.get("tool", {}):
            evidence.append("pyproject.toml#tool.pytest")
        if any(root.rglob("test_*.py")) or any(root.rglob("*_test.py")):
            evidence.append("test_*.py files present")
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no pytest/tox config or test_*.py files found"
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_lint(self, root: Path) -> CategoryResult:
        evidence = [m for m in LINT_CONFIG_MARKERS if (root / m).exists()]
        pyproject = read_toml(root / "pyproject.toml")
        if pyproject:
            tools = pyproject.get("tool", {})
            for name in ("ruff", "mypy", "black", "flake8"):
                if name in tools:
                    evidence.append(f"pyproject.toml#tool.{name}")
        if not evidence:
            return CategoryResult(Tier.ABSENT, reason="no ruff/mypy/flake8 config found")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_reproducibility(self, root: Path, fp: Fingerprint) -> CategoryResult:
        if fp.toolchain == "poetry":
            lock = root / "poetry.lock"
            if not lock.exists():
                return CategoryResult(Tier.ABSENT, reason="no poetry.lock found")
            gitignore = read_text(root / ".gitignore") or ""
            if re.search(r"^poetry\.lock$", gitignore, re.MULTILINE):
                return CategoryResult(Tier.ABSENT, reason="poetry.lock exists but is gitignored")
            return CategoryResult(Tier.CONFIGURED, evidence=["poetry.lock"])

        req = root / "requirements.txt"
        if not req.exists():
            pyproject = read_toml(root / "pyproject.toml")
            if pyproject and "dependencies" in pyproject.get("project", {}):
                return CategoryResult(
                    Tier.ABSENT,
                    evidence=["pyproject.toml#project.dependencies"],
                    reason=(
                        "PEP 621 dependencies are unpinned in pyproject.toml and no "
                        "lock mechanism (requirements.txt, uv.lock, pip-compile output) "
                        "was found"
                    ),
                )
            return CategoryResult(Tier.ABSENT, reason="no requirements.txt found")
        text = read_text(req) or ""
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        pinned = [ln for ln in lines if "==" in ln]
        if lines and len(pinned) == len(lines):
            return CategoryResult(
                Tier.CONFIGURED, evidence=["requirements.txt (all deps pinned with ==)"]
            )
        if lines:
            return CategoryResult(
                Tier.ABSENT,
                evidence=["requirements.txt"],
                reason=f"{len(lines) - len(pinned)}/{len(lines)} dependencies unpinned",
            )
        return CategoryResult(Tier.ABSENT, reason="requirements.txt is empty")

    def _scan_ci(self, root: Path) -> CategoryResult:
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
        return CategoryResult(Tier.ABSENT, reason="no CI config found running pytest")
