from __future__ import annotations

from pathlib import Path

from girdle.detectors import python_common
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

PIPFILE_LOCK = "Pipfile.lock"


class PythonPipenvDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "Pipfile").exists():
            return None
        return Fingerprint(
            id="python-pipenv", language="python", toolchain="pipenv", root=root, variants=[]
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "coverage", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        return {
            "tests": python_common.scan_tests(root),
            "lint": python_common.scan_lint(root),
            "coverage": python_common.scan_coverage(root),
            "reproducibility": self._scan_reproducibility(root),
            "ci_gating": python_common.scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        commands = {"tests": ["pipenv", "run", "pytest", "-q"]}
        lint_cmd = python_common.lint_command(fp.root)
        if lint_cmd:
            commands["lint"] = ["pipenv", "run", *lint_cmd]
        commands["coverage"] = ["pipenv", "run", *python_common.coverage_command()]
        return commands

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        if not (root / PIPFILE_LOCK).exists():
            return CategoryResult(
                Tier.ABSENT, reason=f"no {PIPFILE_LOCK} found",
                recommendation=f"Run `pipenv lock` and commit the generated {PIPFILE_LOCK}.",
            )
        if python_common.is_lockfile_gitignored(root, PIPFILE_LOCK):
            return CategoryResult(
                Tier.ABSENT, reason=f"{PIPFILE_LOCK} exists but is gitignored",
                recommendation=f"Remove {PIPFILE_LOCK} from .gitignore and commit it.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=[PIPFILE_LOCK])
