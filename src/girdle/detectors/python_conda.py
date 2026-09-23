from __future__ import annotations

from pathlib import Path

from girdle.detectors import python_common
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

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        # environment.yml alone isn't reproducible: no pinned builds/channels snapshot.
        # conda-lock.yml is the actual reproducibility artifact.
        if (root / "conda-lock.yml").exists():
            return CategoryResult(Tier.CONFIGURED, evidence=["conda-lock.yml"])
        return CategoryResult(
            Tier.ABSENT,
            evidence=["environment.yml"],
            reason="environment.yml present but no conda-lock.yml (unpinned builds/channels)",
        )
