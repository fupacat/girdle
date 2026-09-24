from __future__ import annotations

from pathlib import Path

from girdle.detectors import js_common
from girdle.detectors._util import read_json
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class JsBunDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "package.json").exists():
            return None
        if not ((root / "bun.lockb").exists() or (root / "bun.lock").exists()):
            return None
        return Fingerprint(
            id="js-bun",
            language="javascript",
            toolchain="bun",
            root=root,
            variants=js_common.detect_variants(root),
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pkg_data = read_json(root / "package.json") or {}
        return {
            "tests": js_common.scan_tests(pkg_data, "bun"),
            "lint": js_common.scan_lint(root, fp, "bun"),
            "reproducibility": self._scan_reproducibility(root),
            "ci_gating": js_common.scan_ci(root, r"\bbun (run )?test\b", "bun test"),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        return js_common.run_commands(fp.root, "bun")

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        # bun.lockb is binary: existence-only check, can't diff or content-scan it.
        if (root / "bun.lockb").exists():
            return CategoryResult(Tier.CONFIGURED, evidence=["bun.lockb (binary, presence-only)"])
        if (root / "bun.lock").exists():
            return CategoryResult(Tier.CONFIGURED, evidence=["bun.lock"])
        return CategoryResult(
            Tier.ABSENT, reason="no bun.lockb/bun.lock found",
            recommendation="Run `bun install` and commit the generated bun.lock(b).",
        )
