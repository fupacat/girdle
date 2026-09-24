from __future__ import annotations

from pathlib import Path

from girdle.detectors import js_common
from girdle.detectors._util import read_json
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class JsNpmDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        pkg = root / "package.json"
        if not pkg.exists():
            return None
        # Only claim npm if no other lockfile signals a different toolchain.
        other_lockfiles = ("yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")
        if any((root / lf).exists() for lf in other_lockfiles):
            return None
        return Fingerprint(
            id="js-npm",
            language="javascript",
            toolchain="npm",
            root=root,
            variants=js_common.detect_variants(root),
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pkg_data = read_json(root / "package.json") or {}
        return {
            "tests": js_common.scan_tests(pkg_data, "npm"),
            "lint": js_common.scan_lint(root, fp, "npm"),
            "reproducibility": self._scan_reproducibility(root),
            "ci_gating": js_common.scan_ci(root, r"\bnpm (run )?(test|ci)\b", "npm test"),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        return js_common.run_commands(fp.root, "npm")

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        lockfile = root / "package-lock.json"
        if not lockfile.exists():
            return CategoryResult(
                Tier.ABSENT, reason="no package-lock.json found",
                recommendation="Run `npm install` and commit the generated package-lock.json.",
            )
        if js_common.is_lockfile_gitignored(root, "package-lock.json"):
            return CategoryResult(
                Tier.ABSENT, reason="package-lock.json exists but is gitignored (not committed)",
                recommendation="Remove package-lock.json from .gitignore and commit it.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=["package-lock.json"])
