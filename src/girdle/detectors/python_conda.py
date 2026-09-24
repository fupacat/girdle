from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors import python_common
from girdle.detectors._util import read_text
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class PythonCondaDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "environment.yml").exists() and not (root / "environment.yaml").exists():
            return None
        return Fingerprint(
            id="python-conda", language="python", toolchain="conda", root=root, variants=[]
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
        # Requires the named env to already exist and be activatable; skip
        # entirely if we can't resolve an env name from environment.yml.
        env_file = fp.root / "environment.yml"
        if not env_file.exists():
            env_file = fp.root / "environment.yaml"
        match = re.search(r"^name:\s*(\S+)", read_text(env_file) or "", re.MULTILINE)
        if not match:
            return {}
        env_name = match.group(1)
        commands = {"tests": ["conda", "run", "-n", env_name, "pytest", "-q"]}
        lint_cmd = python_common.lint_command(fp.root)
        if lint_cmd:
            commands["lint"] = ["conda", "run", "-n", env_name, *lint_cmd]
        return commands

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        # environment.yml alone isn't reproducible: no pinned builds/channels snapshot.
        # conda-lock.yml is the actual reproducibility artifact.
        if (root / "conda-lock.yml").exists():
            return CategoryResult(Tier.CONFIGURED, evidence=["conda-lock.yml"])
        return CategoryResult(
            Tier.ABSENT,
            evidence=["environment.yml"],
            reason="environment.yml present but no conda-lock.yml (unpinned builds/channels)",
            recommendation=(
                "Generate a conda-lock.yml: `pip install conda-lock && "
                "conda-lock -f environment.yml`."
            ),
        )
