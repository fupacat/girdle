from __future__ import annotations

from pathlib import Path

from girdle.detectors import python_common
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class PythonPipenvDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "Pipfile").exists():
            return None
        return Fingerprint(
            id="python-pipenv", language="python", toolchain="pipenv", root=root, variants=[]
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        return {
            "tests": python_common.scan_tests(root),
            "lint": python_common.scan_lint(root),
            "reproducibility": self._scan_reproducibility(root),
            "ci_gating": python_common.scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        commands = {"tests": ["pipenv", "run", "pytest", "-q"]}
        lint_cmd = python_common.lint_command(fp.root)
        if lint_cmd:
            commands["lint"] = ["pipenv", "run", *lint_cmd]
        return commands

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        if not (root / "Pipfile.lock").exists():
            return CategoryResult(
                Tier.ABSENT, reason="no Pipfile.lock found",
                recommendation="Run `pipenv lock` and commit the generated Pipfile.lock.",
            )
        if python_common.is_lockfile_gitignored(root, "Pipfile.lock"):
            return CategoryResult(
                Tier.ABSENT, reason="Pipfile.lock exists but is gitignored",
                recommendation="Remove Pipfile.lock from .gitignore and commit it.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=["Pipfile.lock"])
